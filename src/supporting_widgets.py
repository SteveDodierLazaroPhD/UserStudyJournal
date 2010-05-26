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
import gobject
import gtk
import gettext
import datetime
import math
import time
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

import content_objects
from common import shade_gdk_color, combine_gdk_color, is_command_available, \
    launch_command, get_gtk_rgba, SIZE_NORMAL, SIZE_LARGE, GioFile
from config import BASE_PATH, VERSION, settings, PluginManager, get_icon_path, get_data_path, bookmarker, SUPPORTED_SOURCES
from store import STORE, get_related_events_for_uri, CLIENT
from external import TRACKER


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
    def __init__(self, side = 0, sensitive=True):
        super(DayButton, self).__init__()
        self.set_events(self._events)
        self.set_flags(gtk.CAN_FOCUS)
        self.side = side
        self.connect("button_press_event", self.on_press)
        self.connect("button_release_event", self.clicked_sender)
        self.connect("key_press_event", self.keyboard_clicked_sender)
        self.connect("motion_notify_event", self.on_hover)
        self.connect("leave_notify_event", self._enter_leave_notify, False)
        self.connect("expose_event", self.expose)
        self.connect("style-set", self.change_style)
        self.set_size_request(20, -1)
        self.set_sensitive(sensitive)

    def set_leading(self, leading):
        self.leading = leading

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
        self.bg_color = get_gtk_rgba(self.style, "bg", 0)
        self.header_color = get_gtk_rgba(self.style, "bg", 0, 1.25)
        self.leading_header_color = get_gtk_rgba(self.style, "bg", 3)
        self.internal_color = get_gtk_rgba(self.style, "bg", 0, 1.02)
        self.arrow_color = get_gtk_rgba(self.style, "text", 0, 0.6)
        self.arrow_color_selected = get_gtk_rgba(self.style, "bg", 3)
        self.arrow_color_insensitive = get_gtk_rgba(self.style, "text", 4)

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


class SearchBox(gtk.ToolItem):

    __gsignals__ = {
        "clear" : (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   ()),
        "search" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_PYOBJECT,))
    }

    def __init__(self):
        gtk.ToolItem.__init__(self)

        self.text = ""
        self.callback = None
        self.set_border_width(3)
        self.hbox = gtk.HBox()
        self.add(self.hbox)
        self.results = []
        self.search = SearchEntry()
        self.hbox.pack_start(self.search)
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

    def do_search(self, text, callback=None, interpretation=None):
        if not callback: return
        if TRACKER and 1==2: #DISABLED FOR NOW. Causes a crash in zeitgeist
            self.do_search_tracker(text, callback, interpretation)
        else:
            self.do_search_objs(text, callback, interpretation)

    @staticmethod
    def do_search_tracker(text, callback, interpretation=None):
        TRACKER.search(text, interpretation, callback)

    @staticmethod
    def do_search_objs(text, callback, interpretation=None):
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

    def do_search_using_zeitgeist(self, text, callback=None, interpretation=""):
        if not text: return
        self.callback = callback
        templates = [
            Event.new_for_values(subject_text="*"+text+"*", subject_interpretation=interpretation),
            Event.new_for_values(subject_uri="*"+text+"*", subject_interpretation=interpretation)
        ]
        CLIENT.find_event_ids_for_templates(templates, self._search_callback, storage_state=2, num_events=20, result_type=0)

    def _search_callback(self, ids):
        objs = []
        for id_ in ids:
            try:
                obj.append(STORE[id_])
            except KeyError:
                continue
        if self.callback:
            self.callback(objs)

    def toggle_visibility(self):
        if self.get_property("visible"):
            self.hide()
            return False
        self.show()
        return True

    def __search(self, this, results):
        content_objects.ContentObject.clear_search_matches()
        for obj in results:
            setattr(obj, "matches_search", True)


class SearchEntry(gtk.Entry):

    __gsignals__ = {
        "clear" : (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   ()),
        "search" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_STRING,)),
        "close" : (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   ()),
    }

    default_text = _("Type here to search...")
    # TODO: What is this?
    search_timeout = 0

    def __init__(self, accel_group = None):
        gtk.Entry.__init__(self)

        self.set_width_chars(30)
        self.set_text(self.default_text)
        self.connect("changed", lambda w: self._queue_search())
        self.connect("focus-in-event", self._entry_focus_in)
        self.connect("focus-out-event", self._entry_focus_out)
        self.set_icon_from_stock(0, gtk.STOCK_CANCEL)
        self.set_icon_from_stock(1, gtk.STOCK_CLEAR)
        self.connect("icon-press", self._icon_press)
        self.show_all()

    def _icon_press(self, widget, pos, event):
        if int(pos) == 1 and not self.get_text() == self.default_text:
            self._entry_clear_no_change_handler()
        elif event.button == 1 and pos == 0:
            self.emit("close")

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


class ToolButton(gtk.ToolButton):
    def __init__(self, *args, **kwargs):
        super(ToolButton, self).__init__(*args, **kwargs)

    def set_label(self, text):
        super(ToolButton, self).set_label(text)
        self.set_tooltip_text(text)

    def set_tooltip_text(self, text):
        gtk.Widget.set_tooltip_text(self, text)


class Toolbar(gtk.Toolbar):
    @staticmethod
    def get_toolbutton(path, label_string):
        button = ToolButton()
        pixbuf = gtk.gdk.pixbuf_new_from_file(path)
        image = gtk.Image()
        image.set_from_pixbuf(pixbuf)
        button.set_icon_widget(image)
        button.set_label(label_string)
        return button

    def __init__(self):
        super(Toolbar, self).__init__()
        #self.set_style(gtk.TOOLBAR_BOTH)
        self.multiview_button = mv = self.get_toolbutton(
            get_data_path("multiview_icon.png"),
            _("Switch to MultiView"))
        self.thumbview_button = tbv = self.get_toolbutton(
            get_data_path("thumbview_icon.png"),
            _("Switch to ThumbView"))
        self.timelineview_button = tlv = self.get_toolbutton(
            get_data_path("timelineview_icon.png"),
            _("Switch to TimelineView"))
        #
        self.view_buttons = [mv, tbv, tlv]
        #self.append_space()
        self.pin_button = pin = self.get_toolbutton(
            get_icon_path("hicolor/24x24/status/pin.png"),
            _("Show Pinned Pane"))
        self.search_button = sb = gtk.ToolButton(gtk.STOCK_FIND)
        self.search_dialog = sdialog = SearchBox
        self.search_dialog.search.connect("close", self.toggle_searchbox_visibility)
        self.search_button.connect("clicked", self.toggle_searchbox_visibility)

        sep1 = gtk.SeparatorToolItem()
        sep2 = gtk.SeparatorToolItem()
        for item in (sdialog, sb, sep2, pin, sep1, tlv, tbv, mv):
            self.insert(item, 0)
        #
        self.pref = gtk.ToolButton(gtk.STOCK_PREFERENCES)
        separator = gtk.SeparatorToolItem()
        separator.set_expand(True)
        separator.set_draw(False)
        self.goto_today_button = today = gtk.ToolButton(gtk.STOCK_GOTO_LAST)
        today.set_label( _("Goto Today"))
        self.throbber = Throbber()
        for item in (separator, today, self.pref, self.throbber):
            self.insert(item, -1)
        self.pref.connect("clicked", self.show_settings)
        self.view_buttons[0].set_sensitive(False)

        self.preferences_dialog = PreferencesDialog()

    def show_settings(self, *args):
        self.preferences_dialog.show_all()

    def do_throb(self):
        self.throbber.image.animate_for_seconds(1)

    def toggle_searchbox_visibility(self, w):
        result = self.search_dialog.toggle_visibility()
        if result:
            self.search_button.hide()
        else:
            self.search_button.show()


class TagCloud(gtk.VBox):
    __gsignals__ = {
        "add-tag":  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,(gobject.TYPE_STRING,)),
        "remove-tag":  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,(gobject.TYPE_STRING,)),
    }

    max_font_size = 11000.0
    min_font_size = 6000.0
    mid_font_size = 8500.0
    _size_diff = max_font_size - min_font_size

    class SelectTagMenu(gtk.Menu):
        def clear(self):
            for item in self.get_children():
                self.remove(item)
                item.destroy()

        def set_tags(self, tags, callback):
            self.clear()
            for tag in tags:
                item = gtk.MenuItem(label=tag)
                self.add(item)
                item.connect("activate", callback, tag)
            self.show_all()

    def __init__(self):
        super(TagCloud, self).__init__()
        self.tag_dict = {}
        self.label = gtk.Label()
        self.pack_start(self.label, True, True)
        self.label.set_line_wrap(True)
        self.label.set_line_wrap_mode(pango.WRAP_WORD)
        self.label.set_justify(gtk.JUSTIFY_CENTER)
        self.label.connect( "size-allocate", self.size_allocate )
        self.button_box = box = gtk.HBox()
        self.entry_box = entry_box = gtk.HBox()
        self.pack_end(self.button_box, False, False)
        self.add_button = add = StockIconButton(gtk.STOCK_CANCEL)
        self.finish_button = finish = StockIconButton(gtk.STOCK_OK)
        self.remove_button = remove = StockIconButton(gtk.STOCK_REMOVE)
        self.entry = entry = gtk.Entry()
        box.pack_start(add, False, False)
        box.pack_start(entry_box)
        box.pack_end(remove, False, False)
        entry_box.pack_start(entry)
        entry_box.pack_end(finish, False, False)
        finish.connect("clicked", self._add_tag)
        entry.connect("activate", self._add_tag)
        self.add_button.connect("clicked", self.toggle_tag_entry_box)
        self.remove_button.connect("button-press-event", self.show_remove_menu)
        entry_box.show_all()
        entry_box.set_no_show_all(True)
        # Remove tags
        self.tag_menu = tag_menu = self.SelectTagMenu()
        tag_menu.attach_to_widget(remove, lambda *args:None)
        ##
        self.toggle_tag_entry_box()
        self.label.connect("activate-link", self.on_tag_activated)

    def show_remove_menu(self, w, event):
        if event.button == 1 and self.tag_dict:
            self.tag_menu.set_tags(self.tag_dict.keys(), self.remove_tag)
            self.tag_menu.popup(None, None, None, event.button, event.time)

    def toggle_tag_entry_box(self, *args):
        if self.entry_box.get_property("visible"):
            self.entry_box.hide()
            self.entry.set_text("")
            self.add_button.set_stock(gtk.STOCK_ADD)
        else:
            self.entry_box.show()
            self.add_button.set_stock(gtk.STOCK_CANCEL)

    def remove_tag(self, w, tag):
        if tag:
            self.emit("remove-tag", tag)

    def _add_tag(self, *args):
        tag = self.entry.get_text()
        if tag:
            self.emit("add-tag", tag)
        self.toggle_tag_entry_box()

    def get_text(self):
        return self.label.get_text()

    def set_text(self, text):
        return self.label.set_text(text)

    def set_markup(self, markup):
        return self.label.set_markup(markup)

    def size_allocate(self, label, alloc):
        label.set_size_request(alloc.width - 2, -1 )

    def clear(self):
        self.set_text("")

    def make_tag(self, tag, value, min_value, max_value):
        if (min_value+max_value+value)/3 == value:
            size = self.mid_font_size
        else:
            value = (value-min_value)/(max_value-min_value)
            size = (value * self._size_diff) + self.min_font_size
        return "<a href='" + tag + "'><span size='" + str(int(size)) + "'>" + tag + "</span></a>"

    def on_tag_activated(self, widget, tag):
        if TRACKER:
            def _thread():
                files = TRACKER.get_uris_for_tag(tag)
                if files:
                    results = []
                    for obj in content_objects.Object.instances:
                        if obj.uri in files:
                            results.append(obj)
                    SearchBox.emit("search", results)
            thread = threading.Thread(target=_thread)
            thread.start()
        return True

    def set_tags(self, tag_dict):
        self.tag_dict = tag_dict
        if not tag_dict: return self.set_text("")
        text_lst = []
        min_value = min(float(min(1, *tag_dict.values())), 1)
        max_value = max(float(max(1, *tag_dict.values())), 1)
        for tag in tag_dict.keys():
            text_lst.append(self.make_tag(tag, tag_dict[tag], min_value, max_value))
        self.set_markup("  ".join(text_lst))


class StockIconButton(gtk.Button):
    def __init__(self, stock_id, size=gtk.ICON_SIZE_BUTTON):
        super(StockIconButton, self).__init__()
        self.size = size
        self.set_alignment(0, 0)
        self.set_relief(gtk.RELIEF_NONE)
        self.image = gtk.image_new_from_stock(stock_id, size)
        self.add(self.image)

    def set_stock(self, stock_id):
        self.image.set_from_stock(stock_id, self.size)


class Pane(gtk.Frame):
    """
    A pane container
    """
    def __init__(self):
        super(Pane, self).__init__()
        #self.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        self.close_button = close_button = StockIconButton(gtk.STOCK_CLOSE)
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


#######################
# More Information Pane
##

class InformationBox(gtk.VBox):
    """
    Holds widgets which display information about a uri
    """
    obj = None

    class _ImageDisplay(gtk.Image):
        """
        A display based on GtkImage to display a uri's thumb or icon using GioFile
        """
        def set_content_object(self, obj):
            if obj:
                if isinstance(obj, GioFile) and obj.has_preview():
                    pixbuf = obj.get_thumbnail(size=SIZE_NORMAL, border=3)
                else:
                    pixbuf = obj.get_icon(size=64)
                self.set_from_pixbuf(pixbuf)

    def __init__(self):
        super(InformationBox, self).__init__()
        vbox = gtk.VBox()
        self.box = gtk.Frame()
        self.label = gtk.Label()
        self.pathlabel = gtk.Label()
        self.pathlabel.modify_font(pango.FontDescription("Monospace 7"))
        labelvbox = gtk.VBox()
        labelvbox.pack_start(self.label)
        labelvbox.pack_end(self.pathlabel)
        self.pack_start(labelvbox, True, True, 5)
        self.box.set_shadow_type(gtk.SHADOW_NONE)
        vbox.pack_start(self.box, True, True)
        self.pathlabel.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self.label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self.add(vbox)
        self.display_widget = self._ImageDisplay()
        self.box.add(self.display_widget)
        self.show_all()

    def set_displaytype(self, obj):
        """
        Determines the ContentDisplay to use for a given uri
        """
        self.display_widget.set_content_object(obj)
        self.show_all()

    def set_content_object(self, obj):
        self.obj = obj
        self.set_displaytype(obj)
        self.label.set_markup("<span size='10336'>" + obj.text.replace("&", "&amp;") + "</span>")
        self.pathlabel.set_markup("<span color='#979797'>" + obj.uri.replace("&", "&amp;") + "</span>")


class _RelatedPane(gtk.TreeView):
    """
    . . . . .
    .       .
    .       . <--- Related files
    .       .
    . . . . .

    Displays related events using a widget based on gtk.TreeView
    """
    def __init__(self):
        super(_RelatedPane, self).__init__()
        self.popupmenu = ContextMenu
        self.connect("button-press-event", self.on_button_press)
        self.connect("row-activated", self.row_activated)
        pcolumn = gtk.TreeViewColumn(_("Related Items"))
        pixbuf_render = gtk.CellRendererPixbuf()
        pcolumn.pack_start(pixbuf_render, False)
        pcolumn.set_cell_data_func(pixbuf_render, self.celldatamethod, "pixbuf")
        text_render = gtk.CellRendererText()
        text_render.set_property("ellipsize", pango.ELLIPSIZE_MIDDLE)
        pcolumn.pack_end(text_render, True)
        pcolumn.set_cell_data_func(text_render, self.celldatamethod, "text")
        self.append_column(pcolumn)
        #self.set_headers_visible(False)

    def celldatamethod(self, column, cell, model, iter_, user_data):
        if model:
            obj = model.get_value(iter_, 0)
            if user_data == "text":
                cell.set_property("text", obj.text.replace("&", "&amp;"))
            elif user_data == "pixbuf":
                cell.set_property("pixbuf", obj.icon)

    def _set_model_in_thread(self, structs):
        """
        A threaded which generates pixbufs and emblems for a list of structs.
        It takes those properties and appends them to the view's model
        """
        lock = threading.Lock()
        self.active_list = []
        liststore = gtk.ListStore(gobject.TYPE_PYOBJECT)
        gtk.gdk.threads_enter()
        self.set_model(liststore)
        gtk.gdk.threads_leave()
        for struct in structs:
            if not struct.content_object: continue
            gtk.gdk.threads_enter()
            lock.acquire()
            self.active_list.append(False)
            liststore.append((struct.content_object,))
            lock.release()
            gtk.gdk.threads_leave()

    def set_model_from_list(self, structs):
        self.last_active = -1
        if not structs:
            self.set_model(None)
            return
        thread = threading.Thread(target=self._set_model_in_thread, args=(structs,))
        thread.start()

    def on_button_press(self, widget, event):
        if event.button == 3:
            path = self.get_path_at_pos(int(event.x), int(event.y))
            if path:
                model = self.get_model()
                obj = model[path[0]][0]
                self.popupmenu.do_popup(event.time, [obj])
        return False

    def row_activated(self, widget, path, col, *args):
        if path:
            model = self.get_model()
            if model:
                obj = model[path[0]][0]
                obj.launch()


class InformationContainer(Pane):
    """
    . . . . .
    .  URI  .
    . Info  .
    .       .
    . Tags  .
    . . . . .
    . . . . .
    .       .
    .       . <--- Related files
    .       .
    . . . . .

    A pane which holds the information pane and related pane
    """

    class _InformationToolbar(gtk.Toolbar):
        def __init__(self):
            gtk.Toolbar.__init__(self)
            self.set_icon_size(gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.open_button = ob = ToolButton(gtk.STOCK_OPEN)
            ob.set_label(_("Launch this subject"))
            self.delete_button = del_ = ToolButton(gtk.STOCK_DELETE)
            del_.set_label(_("Delete this subject"))
            self.pin_button = pin = Toolbar.get_toolbutton(
                get_icon_path("hicolor/24x24/status/pin.png"),
                _("Add Pin"))
            sep = gtk.SeparatorToolItem()
            for item in (del_, pin, sep, ob):
                if item:
                    self.insert(item, 0)

    def __init__(self):
        #super(InformationContainer, self).__init__()
        super(Pane, self).__init__()
        self.close_button = close_button = ToolButton()
        close_button.set_stock_id(gtk.STOCK_CLOSE)
        close_button.set_label(_("Close"))
        self.connect("delete-event", self.hide_on_delete)
        close_button.connect("clicked", self.hide_on_delete)
        self.set_label_align(1, 0)
        box1 = gtk.VBox()
        box2 = gtk.VBox()
        vbox = gtk.VBox()
        self.toolbar = self._InformationToolbar()
        self.infopane = InformationBox()
        if TRACKER:
            self.tag_cloud_frame = frame = gtk.Frame()
            frame.set_label( _("Tags"))
            self.tag_cloud = TagCloud()
            frame.add(self.tag_cloud)
        self.relatedpane = _RelatedPane()
        scrolledwindow = gtk.ScrolledWindow()
        box2.set_border_width(5)
        box1.pack_start(self.toolbar, False, False)
        box2.pack_start(self.infopane, False, False, 4)
        if TRACKER:
            box2.pack_start(frame, False, False, 4)
        scrolledwindow.set_shadow_type(gtk.SHADOW_IN)
        scrolledwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolledwindow.add(self.relatedpane)
        vbox.pack_end(scrolledwindow, True, True)
        box2.pack_end(vbox, True, True, 10)
        box1.add(box2)
        self.add(box1)
        def _launch(w):
            self.obj.launch()
        self.toolbar.open_button.connect("clicked", _launch)
        self.toolbar.delete_button.connect("clicked", self.do_delete_events_with_shared_uri)
        self.toolbar.pin_button.connect("clicked", self.do_toggle_bookmark)
        if TRACKER:
            self.tag_cloud.connect("add-tag", self.on_add_tag)
            self.tag_cloud.connect("remove-tag", self.on_remove_tag)
        self.connect("size-allocate", self.size_allocate)
        # Remove the close button
        separator = gtk.SeparatorToolItem()
        separator.set_expand(True)
        separator.set_draw(False)
        self.toolbar.insert(separator, -1)
        self.toolbar.insert(close_button, -1)

    def size_allocate(self, widget, allocation):
        if allocation.height < 400:
            self.infopane.display_widget.hide()
        else:
            self.infopane.display_widget.show()


    def do_toggle_bookmark(self, *args):
        if bookmarker.is_bookmarked(self.obj.uri):
            bookmarker.unbookmark(self.obj.uri)
        else:
            bookmarker.bookmark(self.obj.uri)

    def on_remove_tag(self, w, text):
        if TRACKER:
            TRACKER.remove_tag_from_uri(text, self.obj.uri)
        self.set_tags(self.obj)

    def on_add_tag(self, w, text):
        if TRACKER:
            TRACKER.add_tag_to_uri(text, self.obj.uri)
        self.set_tags(self.obj)

    def do_delete_events_with_shared_uri(self, *args):
        CLIENT.find_event_ids_for_template(
            Event.new_for_values(subject_uri=self.obj.uri),
            lambda ids: CLIENT.delete_events(map(int, ids)))
        self.hide()

    def set_content_object(self, obj):
        self.obj = obj
        def _callback(events):
            self.relatedpane.set_model_from_list(events)
        get_related_events_for_uri(obj.uri, _callback)
        self.infopane.set_content_object(obj)
        if TRACKER:
            self.set_tags(obj)
        self.show()

    def set_tags(self, obj):
        tag_dict = {}
        tags = TRACKER.get_tag_dict_for_uri(obj.uri)
        self.tag_cloud.set_tags(tags)

    def hide_on_delete(self, widget, *args):
        super(InformationContainer, self).hide_on_delete(widget)
        return True


class PreferencesDialog(gtk.Dialog):
    class _PluginTreeView(gtk.TreeView):
        def __init__(self):
            gtk.TreeView.__init__(self)
            self.set_headers_visible(False)
            pcolumn = gtk.TreeViewColumn("")
            toggle_render = gtk.CellRendererToggle()
            pcolumn.pack_start(toggle_render, False)
            pcolumn.add_attribute(toggle_render, "active", 1)
            text_render = gtk.CellRendererText()
            text_render.set_property("ellipsize", pango.ELLIPSIZE_MIDDLE)
            pcolumn.pack_end(text_render, True)
            pcolumn.add_attribute(text_render, "markup", 0)
            self.append_column(pcolumn)
            self.connect("row-activated" , self.on_activate)

        def set_state(self, entry, state):
            PluginManager.plugin_settings._gconf.set_bool(entry.key, state)

        def on_activate(self, widget, path, column):
            model = self.get_model()
            model[path][1] = not model[path][1]
            self.set_state(model[path][2], model[path][1])
            #try:
            if True:
                bname = os.path.basename(model[path][2].key)
                #module = self.manager.plugins[bname]
                if model[path][1]:
                    self.manager.activate(name=bname)
                else:
                    self.manager.deactivate(name=bname)
            #except: pass

        def set_items(self, manager):
            entries = manager.plugin_settings._gconf.all_entries(PluginManager.plugin_settings._root)
            store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_BOOLEAN, gobject.TYPE_PYOBJECT)
            for entry in entries:
                bname = os.path.basename(entry.key)
                if manager.plugins.has_key(bname):
                    # Load the plugin if the plugin is found
                    module = manager.plugins[bname]
                    name = module.__plugin_name__
                    desc = "\n<span size='7000'>" + module.__description__ + "</span>"
                    store.append( [name+desc, False if entry.value is None else entry.value.get_bool(), entry])
                else:
                    # Remove the key if no plugin is found
                    manager.plugin_settings._gconf.unset(entry.key)
            self.manager = manager
            self.set_model(store)

    def __init__(self):
        super(PreferencesDialog, self).__init__()
        self.set_title(_("Preferences"))
        self.set_size_request(400, 500)
        area = self.get_content_area()
        notebook = gtk.Notebook()
        area.pack_start(notebook)
        plugbox = gtk.VBox()
        plugbox.set_border_width(10)
        self.plug_tree = self._PluginTreeView()
        scroll_win = gtk.ScrolledWindow()
        scroll_win.set_shadow_type(gtk.SHADOW_IN)
        scroll_win.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll_win.add(self.plug_tree)
        plugbox.add(scroll_win)
        plugbox.pack_end(gtk.Label(_("Changing plugin states requires Journal to be restarted")), False, False, 5)
        notebook.append_page(plugbox, gtk.Label( _("Plugins")))
        self.connect("delete-event", lambda *args: (True, self.hide())[0])


###

if gst is not None:
    VideoPreviewTooltip = VideoPreviewTooltip()
else:
    VideoPreviewTooltip = None
StaticPreviewTooltip = StaticPreviewTooltip()
ContextMenu = ContextMenu()
SearchBox = SearchBox()
