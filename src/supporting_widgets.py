# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Siegfried Gevatter <siegfried@gevatter.com>
# Copyright © 2010 Markus Korn <thekorn@gmx.de>
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement
import cairo
import os
import gtk
import gettext
import datetime
import math
import time
import gobject
import pango
import gio
import threading
from dbus.exceptions import DBusException
try:
    import gst
except ImportError:
    gst = None

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType

from common import shade_gdk_color, combine_gdk_color, is_command_available, \
    launch_command
from config import BASE_PATH, VERSION, settings, get_icon_path, get_data_path
from sources import Source, SUPPORTED_SOURCES
from gio_file import GioFile, SIZE_NORMAL, SIZE_LARGE
from bookmarker import bookmarker

import content_objects
import common

CLIENT = ZeitgeistClient()
ITEMS = []


class DayLabel(gtk.DrawingArea):


    _events = (
        gtk.gdk.ENTER_NOTIFY_MASK | gtk.gdk.LEAVE_NOTIFY_MASK |
        gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON_MOTION_MASK |
        gtk.gdk.POINTER_MOTION_HINT_MASK | gtk.gdk.BUTTON_RELEASE_MASK |
        gtk.gdk.BUTTON_PRESS_MASK
    )

    def __init__(self,date=None):
        super(DayLabel, self).__init__()
        self.set_events(self._events)
        self.connect("expose_event", self.expose)
        if date:
            self.date = date
        else:
            self.date = datetime.date.today()
        self.set_size_request(100, 60)

    @property
    def date_string(self):
        return self.date.strftime("%x")

    @property
    def weekday_string(self):
        return self.date.strftime("%A")

    @property
    def leading(self):
        if self.date == datetime.date.today():
            return True

    def set_date(self, date):
        self.date = date
        self.queue_draw()

    def expose(self, widget, event):
        context = widget.window.cairo_create()
        self.context = context

        bg = self.style.bg[0]
        red, green, blue = bg.red/65535.0, bg.green/65535.0, bg.blue/65535.0
        self.font_name = self.style.font_desc.get_family()

        widget.style.set_background(widget.window, gtk.STATE_NORMAL)

        # set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()
        self.draw(widget, event, context)
        self.day_text(widget, event, context)
        return False

    def day_text(self, widget, event, context):
        actual_y = self.get_size_request()[1]
        if actual_y > event.area.height:
            y = actual_y
        else:
            y = event.area.height
        x = event.area.width
        gc = self.style.fg_gc[gtk.STATE_SELECTED if self.leading else gtk.STATE_NORMAL]
        layout = widget.create_pango_layout(self.weekday_string)
        layout.set_font_description(pango.FontDescription(self.font_name + " Bold 15"))
        w, h = layout.get_pixel_size()
        widget.window.draw_layout(gc, (x-w)/2, (y)/2 - h + 5, layout)
        self.date_text(widget, event, context, (y)/2 + 5)

    def date_text(self, widget, event, context, lastfontheight):
        gc = self.style.fg_gc[gtk.STATE_SELECTED if self.leading else gtk.STATE_INSENSITIVE]
        layout = widget.create_pango_layout(self.date_string)
        layout.set_font_description(pango.FontDescription(self.font_name + " 10"))
        w, h = layout.get_pixel_size()
        widget.window.draw_layout(gc, (event.area.width-w)/2, lastfontheight, layout)

    def draw(self, widget, event, context):
        if self.leading:
            bg = self.style.bg[gtk.STATE_SELECTED]
            red, green, blue = bg.red/65535.0, bg.green/65535.0, bg.blue/65535.0
        else:
            bg = self.style.bg[gtk.STATE_NORMAL]
            red = (bg.red * 125 / 100)/65535.0
            green = (bg.green * 125 / 100)/65535.0
            blue = (bg.blue * 125 / 100)/65535.0
        x = 0; y = 0
        r = 5
        w, h = event.area.width, event.area.height
        context.set_source_rgba(red, green, blue, 1)
        context.new_sub_path()
        context.arc(r+x, r+y, r, math.pi, 3 * math.pi /2)
        context.arc(w-r, r+y, r, 3 * math.pi / 2, 0)
        context.close_path()
        context.rectangle(0, r, w, h)
        context.fill_preserve()


class DayButton(gtk.DrawingArea):
    leading = False
    pressed = False
    sensitive = True
    hover = False
    header_size = 60
    bg_color = (0, 0, 0, 0)
    header_color = (1, 1, 1, 1)
    leading_header_color = (1, 1, 1, 1)
    internal_color = (0, 1, 0, 1)
    arrow_color = (1,1,1,1)
    arrow_color_selected = (1, 1, 1, 1)

    __gsignals__ = {
        "clicked":  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,()),
        }
    _events = (
        gtk.gdk.ENTER_NOTIFY_MASK | gtk.gdk.LEAVE_NOTIFY_MASK |
        gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.BUTTON_PRESS_MASK |
        gtk.gdk.MOTION_NOTIFY |   gtk.gdk.POINTER_MOTION_MASK
    )
    def __init__(self, side = 0, leading = False):
        super(DayButton, self).__init__()
        self.set_events(self._events)
        self.set_flags(gtk.CAN_FOCUS)
        self.leading = leading
        self.side = side
        self.connect("button_press_event", self.on_press)
        self.connect("button_release_event", self.clicked_sender)
        self.connect("key_press_event", self.keyboard_clicked_sender)
        self.connect("motion_notify_event", self.on_hover)
        self.connect("leave_notify_event", self._enter_leave_notify, False)
        self.connect("expose_event", self.expose)
        self.connect("style-set", self.change_style)
        self.set_size_request(20, -1)

    def set_sensitive(self, case):
        self.sensitive = case
        self.queue_draw()

    def _enter_leave_notify(self, widget, event, bol):
        self.hover = bol
        self.queue_draw()

    def on_hover(self, widget, event):
        if event.y > self.header_size:
            if not self.hover:
                self.hover = True
                self.queue_draw()
        else:
            if self.hover:
                self.hover = False
                self.queue_draw()
        return False

    def on_press(self, widget, event):
        if event.y > self.header_size:
            self.pressed = True
            self.queue_draw()

    def keyboard_clicked_sender(self, widget, event):
        if event.keyval in (gtk.keysyms.Return, gtk.keysyms.space):
            if self.sensitive:
                self.emit("clicked")
            self.pressed = False
            self.queue_draw()
            return True
        return False

    def clicked_sender(self, widget, event):
        if event.y > self.header_size:
            if self.sensitive:
                self.emit("clicked")
        self.pressed = False
        self.queue_draw()
        return True

    def change_style(self, *args, **kwargs):
        self.bg_color = common.get_gtk_rgba(self.style, "bg", 0)
        self.header_color = common.get_gtk_rgba(self.style, "bg", 0, 1.25)
        self.leading_header_color = common.get_gtk_rgba(self.style, "bg", 3)
        self.internal_color = common.get_gtk_rgba(self.style, "bg", 0, 1.02)
        self.arrow_color = common.get_gtk_rgba(self.style, "text", 0, 0.6)
        self.arrow_color_selected = common.get_gtk_rgba(self.style, "bg", 3)
        self.arrow_color_insensitive = common.get_gtk_rgba(self.style, "text", 4)

    def expose(self, widget, event):
        context = widget.window.cairo_create()

        context.set_source_rgba(*self.bg_color)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()

        x = 0; y = 0
        r = 5
        w, h = event.area.width, event.area.height
        size = 20
        if self.sensitive:
            context.set_source_rgba(*(self.leading_header_color if self.leading else self.header_color))
            context.new_sub_path()
            context.move_to(x+r,y)
            context.line_to(x+w-r,y)
            context.curve_to(x+w,y,x+w,y,x+w,y+r)
            context.line_to(x+w,y+h-r)
            context.curve_to(x+w,y+h,x+w,y+h,x+w-r,y+h)
            context.line_to(x+r,y+h)
            context.curve_to(x,y+h,x,y+h,x,y+h-r)
            context.line_to(x,y+r)
            context.curve_to(x,y,x,y,x+r,y)
            context.set_source_rgba(*(self.leading_header_color if self.leading else self.header_color))
            context.close_path()
            context.rectangle(0, r, w,  self.header_size)
            context.fill()
            context.set_source_rgba(*self.internal_color)
            context.rectangle(0, self.header_size, w,  h)
            context.fill()
            if self.hover:
                widget.style.paint_box(widget.window, gtk.STATE_PRELIGHT, gtk.SHADOW_OUT,
                                         event.area, widget, "button",
                                         event.area.x, self.header_size,
                                         w, h-self.header_size)
        size = 10
        if not self.sensitive:
            state = gtk.STATE_INSENSITIVE
        elif self.is_focus() or self.pressed:
            widget.style.paint_focus(widget.window, gtk.STATE_ACTIVE, event.area,
                                     widget, None, event.area.x, self.header_size,
                                     w, h-self.header_size)
            state = gtk.STATE_SELECTED
        else:
            state = gtk.STATE_NORMAL
        arrow = gtk.ARROW_RIGHT if self.side else gtk.ARROW_LEFT
        self.style.paint_arrow(widget.window, state, gtk.SHADOW_NONE, None,
                               self, "arrow", arrow, True,
                               w/2-size/2, h/2 + size/2, size, size)


class SearchBox(gtk.EventBox):

    __gsignals__ = {
        "clear" : (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   ()),
        "search" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_PYOBJECT,))
    }

    def __init__(self):
        gtk.EventBox.__init__(self)

        self.text = ""

        self.set_border_width(3)
        self.hbox = gtk.HBox()
        self.add(self.hbox)

        self.results = []

        self.search = SearchEntry()

        self.hbox.pack_start(self.search)
        self.hbox.set_border_width(6)

        self.category = {}

        for source in SUPPORTED_SOURCES.keys():
            s = SUPPORTED_SOURCES[source]._desc_pl
            self.category[s] = source

        self._init_combobox()
        self.show_all()

        def change_style(widget, style):

            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL]
            color = shade_gdk_color(color, 102/100.0)
            self.modify_bg(gtk.STATE_NORMAL, color)

            color = rc_style.bg[gtk.STATE_NORMAL]
            fcolor = rc_style.fg[gtk.STATE_NORMAL]
            color = combine_gdk_color(color, fcolor)

            self.search.modify_text(gtk.STATE_NORMAL, color)

        self.hbox.connect("style-set", change_style)
        self.search.connect("search", self.set_search)
        self.search.connect("clear", self.clear)
        self.connect("search", self.__search)

    def clear(self, widget):
        if self.text.strip() != "" and self.text.strip() != self.search.default_text:
            self.text = ""
            self.results = []
            self.emit("clear")

    def _init_combobox(self):
        self.combobox = gtk.combo_box_new_text()
        self.combobox.set_focus_on_click(False)
        self.hbox.pack_end(self.combobox, False, False, 6)
        self.combobox.append_text("All activities")
        self.combobox.set_active(0)
        for cat in self.category.keys():
            self.combobox.append_text(cat)

    def set_search(self, widget, text=None):
        if not self.text.strip() == text.strip():
            self.text = text
            def callback(results):
                self.results = results
                self.emit("search", results)

            if not text:
                text = self.search.get_text()
            if text == self.search.default_text or text.strip() == "":
                pass
            else:
                cat = self.combobox.get_active()
                if cat == 0:
                    interpretation = None
                else:
                    cat = self.category[self.combobox.get_active_text()]
                    interpretation = self.category[self.combobox.get_active_text()]
            if interpretation:
                return self.do_search(text, callback, interpretation)
            return self.do_search(text, callback)

    @staticmethod
    def do_search(text, callback, interpretation=None):
        def _search(text, callback):
            matching = []
            for obj in content_objects.Object.instances:
                subject = obj.event.subjects[0]
                if text.lower() in subject.text.lower() or text in subject.uri:
                    if interpretation:
                        try:
                            if subject.interpretation != interpretation:
                                continue
                        except: continue
                    matching.append(obj)
            gtk.gdk.threads_enter()
            callback(matching)
            gtk.gdk.threads_leave()
        thread = threading.Thread(target=_search, args=(text, callback))
        thread.start()

    def toggle_visibility(self):
        if self.get_property("visible"):
            self.hide()
        else:
            self.show()

    def __search(self, this, results):
        for obj in content_objects.ContentObject.instances:
            setattr(obj, "matches_search", False)
        for obj in results:
            setattr(obj, "matches_search", True)


class SearchEntry(gtk.Entry):

    __gsignals__ = {
        "clear" : (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   ()),
        "search" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_STRING,))
    }

    default_text = _("Type here to search...")

    # The font style of the text in the entry.
    #font_style = None

    # TODO: What is this?
    search_timeout = 0

    def __init__(self, accel_group = None):
        gtk.Entry.__init__(self)

        self.set_width_chars(30)
        self.set_text(self.default_text)
        self.set_size_request(-1, 32)
        self.connect("changed", lambda w: self._queue_search())
        self.connect("focus-in-event", self._entry_focus_in)
        self.connect("focus-out-event", self._entry_focus_out)
        #self.connect("icon-press", self._icon_press)
        self.show_all()

    def _icon_press(self, widget, pos, event):
        # Note: GTK_ENTRY_ICON_SECONDARY does not seem to be bound in PyGTK.
        if int(pos) == 1 and not self.get_text() == self.default_text:
            self._entry_clear_no_change_handler()

    def _entry_focus_in(self, widget, x):
        if self.get_text() == self.default_text:
            self.set_text("")
            #self.modify_font(self.font_style)

    def _entry_focus_out(self, widget, x):
        if self.get_text() == "":
            self.set_text(self.default_text)
            #self.modify_font(self.font_style)

    def _entry_clear_no_change_handler(self):
        if not self.get_text() == self.default_text:
            self.set_text("")

    def _queue_search(self):
        if self.search_timeout != 0:
            gobject.source_remove(self.search_timeout)
            self.search_timeout = 0

        if self.get_text() == self.default_text or len(self.get_text()) == 0:
            self.emit("clear")
        else:
            self.search_timeout = gobject.timeout_add(200, self._typing_timeout)

    def _typing_timeout(self):
        if len(self.get_text()) > 0:
            self.emit("search", self.get_text())

        self.search_timeout = 0
        return False


class PreviewTooltip(gtk.Window):

    # per default we are using thumbs at a size of 128 * 128 px
    # in tooltips. For preview of text files we are using 256 * 256 px
    # which is dynamically defined in StaticPreviewTooltip.preview()
    TOOLTIP_SIZE = SIZE_NORMAL

    def __init__(self):
        gtk.Window.__init__(self, type=gtk.WINDOW_POPUP)

    def preview(self, gio_file):
        return False


class StaticPreviewTooltip(PreviewTooltip):

    def __init__(self):
        super(StaticPreviewTooltip, self).__init__()
        self.__current = None
        self.__monitor = None

    def replace_content(self, content):
        children = self.get_children()
        if children:
            self.remove(children[0])
            # hack to force the tooltip to have the exact same size
            # as the child image
            self.resize(1,1)
        self.add(content)

    def preview(self, gio_file):
        if gio_file == self.__current:
            return bool(self.__current)
        if self.__monitor is not None:
            self.__monitor.cancel()
        self.__current = gio_file
        self.__monitor = gio_file.get_monitor()
        self.__monitor.connect("changed", self._do_update_preview)
        # for text previews we are always using SIZE_LARGE
        if "text-x-generic" in gio_file.icon_names or "text-x-script" in gio_file.icon_names:
            size = SIZE_LARGE
        else:
            size = self.TOOLTIP_SIZE
        if not isinstance(gio_file, GioFile): return False
        pixbuf = gio_file.get_thumbnail(size=size, border=1)
        if pixbuf is None:
            self.__current = None
            return False
        img = gtk.image_new_from_pixbuf(pixbuf)
        img.set_alignment(0.5, 0.5)
        img.show_all()
        self.replace_content(img)
        del pixbuf, size
        return True

    def _do_update_preview(self, monitor, file, other_file, event_type):
        if event_type == gio.FILE_MONITOR_EVENT_CHANGES_DONE_HINT:
            if self.__current is not None:
                self.__current.refresh()
            self.__current = None
            gtk.tooltip_trigger_tooltip_query(gtk.gdk.display_get_default())


class VideoPreviewTooltip(PreviewTooltip):

    def __init__(self):
        PreviewTooltip.__init__(self)
        hbox = gtk.HBox()
        self.movie_window = gtk.DrawingArea()
        hbox.pack_start(self.movie_window)
        self.add(hbox)
        self.player = gst.element_factory_make("playbin", "player")
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)
        self.connect("hide", self._handle_hide)
        self.connect("show", self._handle_show)
        self.set_default_size(*self.TOOLTIP_SIZE)

    def _handle_hide(self, widget):
        self.player.set_state(gst.STATE_NULL)

    def _handle_show(self, widget):
        self.player.set_state(gst.STATE_PLAYING)

    def preview(self, gio_file):
        if gio_file.uri == self.player.get_property("uri"):
            return True
        self.player.set_property("uri", gio_file.uri)
        return True

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
            self.hide_all()
        elif t == gst.MESSAGE_ERROR:
            self.player.set_state(gst.STATE_NULL)
            err, debug = message.parse_error()
            print "Error: %s" % err, debug

    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            gtk.gdk.threads_enter()
            try:
                self.show_all()
                imagesink.set_xwindow_id(self.movie_window.window.xid)
            finally:
                gtk.gdk.threads_leave()


class AnimatedImage(gtk.Image):
    animating = None
    mod = 7
    i = 0
    speed = 100
    def __init__(self, uri, speed = 0):
        super(AnimatedImage, self).__init__()
        if speed: self.speed = speed
        self.frames = []
        for i in (6, 5, 4, 3, 2, 1, 0):
            self.frames.append(gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(uri % i), 16, 16))
        self.set_from_pixbuf(self.frames[0])

    def next(self):
        """
        Move to next frame
        """
        self.set_from_pixbuf(self.frames[self.i % self.mod])
        self.i += 1
        return True

    def start(self):
        """
        start the image's animation
        """
        if self.animating: gobject.source_remove(self.animating)
        self.animating = gobject.timeout_add(self.speed, self.next)

    def stop(self):
        """
        stop the image's animation
        """
        if self.animating: gobject.source_remove(self.animating)
        self.animating = None
        return False

    def animate_for_seconds(self, seconds):
        """
        :param seconds: int seconds for the amount of time when you want
        animate the throbber
        """
        self.start()
        gobject.timeout_add_seconds(seconds, self.stop)


class Throbber(gtk.ToolButton):
    def __init__(self):
        super(Throbber, self).__init__()
        self.image = AnimatedImage(get_data_path("zlogo/zg%d.png"), 150)
        self.image.set_tooltip_text(_("Powered by Zeitgeist"))
        #self.image.set_alignment(0.9, 0.98)
        self.set_icon_widget(self.image)


class AboutDialog(gtk.AboutDialog):
    name = "Activity Journal"
    authors = (
        "Seif Lotfy <seif@lotfy.com>",
        "Randal Barlow <email.tehk@gmail.com>",
        "Siegfried-Angel Gevatter <siegfried@gevatter.com>",
        "Peter Lund <peterfirefly@gmail.com>",
        "Hylke Bons <hylkebons@gmail.com>",
        "Markus Korn <thekorn@gmx.de>",
        "Mikkel Kamstrup <mikkel.kamstrup@gmail.com>"
        )
    artists = (
               "Hylke Bons <hylkebons@gmail.com>",
               "Thorsten Prante <thorsten@prante.eu>"
                )
    copyright_ = "Copyright © 2009-2010 Activity Journal authors"
    comment = "A viewport into the past powered by Zeitgeist"
    version = VERSION
    def __init__(self):
        super(AboutDialog, self).__init__()
        self.set_name(self.name)
        self.set_version(self.version)
        self.set_comments(self.comment)
        self.set_copyright(self.copyright_)
        self.set_authors(self.authors)
        self.set_artists(self.artists)

        license = None
        for name in ("/usr/share/common-licenses/GPL",
            os.path.join(BASE_PATH, "COPYING")):
            if os.path.isfile(name):
                with open(name) as licensefile:
                    license = licensefile.read()
                    break
        if not license:
            license = "GNU General Public License, version 3 or later."

        self.set_license(license)
        #self.set_logo_icon_name("gnome-activity-journal")
        self.set_logo(gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(
            "hicolor/scalable/apps/gnome-activity-journal.svg"), 48, 48))


class ContextMenu(gtk.Menu):
    subjects = []# A list of Zeitgeist event uris
    informationwindow = None
    def __init__(self):
        super(ContextMenu, self).__init__()
        self.menuitems = {
            "open" : gtk.ImageMenuItem(gtk.STOCK_OPEN),
            "unpin" : gtk.MenuItem(_("Remove Pin")),
            "pin" : gtk.MenuItem(_("Add Pin")),
            "delete" : gtk.MenuItem(_("Delete item from Journal")),
            "delete_uri" : gtk.MenuItem(_("Delete all events with this URI")),
            "info" : gtk.MenuItem(_("More Information")),
            }
        callbacks = {
            "open" : self.do_open,
            "unpin" : self.do_unbookmark,
            "pin" : self.do_bookmark,
            "delete" : self.do_delete,
            "delete_uri" : self.do_delete_events_with_shared_uri,
            "info" : self.do_show_info,
            }
        names = ["open", "unpin", "pin", "delete", "delete_uri", "info"]
        if is_command_available("nautilus-sendto"):
            self.menuitems["sendto"] = gtk.MenuItem(_("Send To..."))
            callbacks["sendto"] = self.do_send_to
            names.append("sendto")
        for name in names:
            item = self.menuitems[name]
            self.append(item)
            item.connect("activate", callbacks[name])
        self.show_all()

    def do_popup(self, time, subjects):
        """
        Call this method to popup the context menu

        :param time: the event time from the button press event
        :param subjects: a list of uris
        """
        self.subjects = subjects
        if len(subjects) == 1:
            uri = subjects[0]
            if bookmarker.is_bookmarked(uri):
                self.menuitems["pin"].hide()
                self.menuitems["unpin"].show()
            else:
                self.menuitems["pin"].show()
                self.menuitems["unpin"].hide()

        self.popup(None, None, None, 3, time)

    def do_open(self, menuitem):
        for obj in self.subjects:
            obj.launch()

    def do_show_info(self, menuitem):
        if self.subjects and self.informationwindow:
            self.informationwindow.set_content_object(self.subjects[0])

    def do_bookmark(self, menuitem):
        for obj in self.subjects:
            uri = obj.uri
            uri = unicode(uri)
            isbookmarked = bookmarker.is_bookmarked(uri)
            if not isbookmarked:
                bookmarker.bookmark(uri)

    def do_unbookmark(self, menuitem):
        for obj in self.subjects:
            uri = obj.uri
            uri = unicode(uri)
            isbookmarked = bookmarker.is_bookmarked(uri)
            if isbookmarked:
                bookmarker.unbookmark(uri)

    def do_delete(self, menuitem):
        for obj in self.subjects:
            CLIENT.delete_events([obj.event.id])

    def do_delete_events_with_shared_uri(self, menuitem):
        for uri in map(lambda obj: obj.uri, self.subjects):
            CLIENT.find_event_ids_for_template(
                Event.new_for_values(subject_uri=uri),
                lambda ids: CLIENT.delete_events(map(int, ids)))


    def do_send_to(self, menuitem):
        launch_command("nautilus-sendto", map(lambda obj: obj.uri, self.subjects))


class Toolbar(gtk.Toolbar):
    @staticmethod
    def get_toolbutton(path, label_string):
        button = gtk.ToolButton()
        pixbuf = gtk.gdk.pixbuf_new_from_file(path)
        image = gtk.Image()
        image.set_from_pixbuf(pixbuf)
        button.set_icon_widget(image)
        button.set_label(label_string)
        return button

    def __init__(self):
        """"""
        super(Toolbar, self).__init__()
        #self.set_style(gtk.TOOLBAR_BOTH)
        self.multiview_button = mv = self.get_toolbutton(
            get_data_path("multiview_icon.png"),
            _("MultiView"))
        self.thumbview_button = tbv = self.get_toolbutton(
            get_data_path("thumbview_icon.png"),
            _("ThumbView"))
        self.timelineview_button = tlv = self.get_toolbutton(
            get_data_path("timelineview_icon.png"),
            _("TimelineView"))
        #
        #self.append_space()
        self.pin_button = pin = self.get_toolbutton(
            get_icon_path("hicolor/24x24/status/pin.png"),
            _("Show Pinned Pane"))
        self.search_button = sb = gtk.ToolButton(gtk.STOCK_FIND)
        separator = gtk.SeparatorToolItem()
        for item in (pin, sb, separator, tlv, tbv, mv):
            self.insert(item, 0)
        #
        separator = gtk.SeparatorToolItem()
        separator.set_expand(True)
        separator.set_draw(False)
        self.goto_today_button = today = gtk.ToolButton(gtk.STOCK_GOTO_LAST)
        today.set_label( _("Goto Today"))
        self.throbber = Throbber()
        for item in (separator, today, self.throbber):
            self.insert(item, -1)

    def do_throb(self):
        self.throbber.image.animate_for_seconds(1)


class StockIconButton(gtk.Button):
    def __init__(self, stock_id, size=gtk.ICON_SIZE_BUTTON):
        super(StockIconButton, self).__init__()
        self.set_alignment(0, 0)
        self.set_relief(gtk.RELIEF_NONE)
        image = gtk.image_new_from_stock(stock_id, size)
        self.add(image)


class Pane(gtk.Frame):
    """
    A pane container
    """
    def __init__(self):
        super(Pane, self).__init__()
        #self.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        close_button = StockIconButton(gtk.STOCK_CLOSE)
        self.set_label_widget(close_button)#, False, False)
        self.connect("delete-event", self.hide_on_delete)
        close_button.connect("clicked", self.hide_on_delete)
        self.set_label_align(0,0)


    def hide_on_delete(self, widget, *args):
        self.hide()
        return True


class HandleBox(gtk.HandleBox):
    def __init__(self, position=gtk.POS_TOP, snap=gtk.POS_TOP):
        super(HandleBox, self).__init__()
        self.set_handle_position(position)
        self.set_snap_edge(snap)
        self.set_shadow_type(gtk.SHADOW_NONE)
        self.connect("child-attached", self.child_attached)
        self.connect("child-detached", self.child_detached)

    def child_attached(self, handlebox, widget):
        self.set_size_request(-1, -1)

    def child_detached(self, handlebox, widget):
        if widget.window:
            x, y, width, height, depth = widget.window.get_geometry()
            child = self.get_child()
            child.set_size_request(width, height)
        self.set_size_request(-1,-1)


if gst is not None:
    VideoPreviewTooltip = VideoPreviewTooltip()
else:
    VideoPreviewTooltip = None
StaticPreviewTooltip = StaticPreviewTooltip()
ContextMenu = ContextMenu()
SearchBox = SearchBox()