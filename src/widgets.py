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
import os
import gtk
import gettext
import datetime
import time
import gobject
import pango
import gio
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
from config import BASE_PATH, VERSION, settings, get_icon_path
from sources import Source, SUPPORTED_SOURCES
from gio_file import GioFile, SIZE_NORMAL, SIZE_LARGE
from bookmarker import bookmarker
try:
    from tracker_wrapper import tracker
except DBusException:
    print "Tracker disabled."

CLIENT = ZeitgeistClient()
ITEMS = []

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

    def clear(self, widget):
        if self.text.strip() != "" and self.text.strip() != self.search.default_text:
            self.text = ""
            self.results = []
            self.emit("clear")

    def _init_combobox(self):

        self.clearbtn = gtk.Button()
        #label = gtk.Label()
        #label.set_markup("<span><b>X</b></span>")

        img = gtk.image_new_from_stock("gtk-close", gtk.ICON_SIZE_MENU)
        self.clearbtn.add(img)
        self.clearbtn.set_focus_on_click(False)
        self.clearbtn.set_relief(gtk.RELIEF_NONE)
        self.hbox.pack_end(self.clearbtn, False, False)
        self.clearbtn.connect("clicked", lambda button: self.hide())
        self.clearbtn.connect("clicked", lambda button: self.search.set_text(""))

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
                self.results = [s[1] for s in results]
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
            if "tracker" in globals().keys():
                tracker.search(text, interpretation, callback)

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

class CategoryButton(gtk.HBox):

    __gsignals__ = {
        "toggle" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_BOOLEAN,)),
    }

    def __init__(self, category, count):
        gtk.HBox.__init__(self)
        self.label = gtk.Label()
        self.label.set_alignment(0.0, 0.5)
        hbox = gtk.HBox()

        self.btn = gtk.Button()
        self.btn.set_relief(gtk.RELIEF_NONE)

        self.btn.set_focus_on_click(False)
        self.btn.add(hbox)
        self.img = gtk.Label()
        self.img.set_markup("<span><b>+</b></span>")
        self.img.set_size_request(8, 8)
        btn = gtk.Button()
        #btn.set_sensitive(False)
        btn.add(self.img)
        hbox.pack_start(gtk.Label(""), False, False, 1)
        hbox.pack_start(btn, False, False, 0)
        hbox.pack_start(gtk.Label(""), False, False, 3)
        self.active = False

        self.pack_start(self.btn)
        #self.pack_start(self.img, False, False)
        if category:
            if category in SUPPORTED_SOURCES:
                label = SUPPORTED_SOURCES[category].group_label(count)
            else:
                label = "Unknown (%s)" % category
            self.label.set_markup("<span>%s</span>" % label)
        self.label.set_ellipsize(pango.ELLIPSIZE_END)
        hbox.pack_start(self.label, True, True, 0)

        label = gtk.Label()
        label.set_markup("<span>(%d)</span>" % count)
        label.set_alignment(1.0,0.5)
        hbox.pack_end(label, False, False, 2)
        self.show_all()

        self.btn.connect("clicked", self.toggle)

        def change_style(widget, style):
            rc_style = self.style

            color = rc_style.bg[gtk.STATE_NORMAL]
            fcolor = rc_style.fg[gtk.STATE_NORMAL]
            color = combine_gdk_color(color, fcolor)
            label.modify_fg(gtk.STATE_NORMAL, color)
            self.img.modify_fg(gtk.STATE_NORMAL, color)

        self.connect("style-set", change_style)


    def toggle(self, widget):
        self.active = not self.active
        if self.active:
            self.img.set_markup("<span><b>-</b></span>")
        else:
            self.img.set_markup("<span><b>+</b></span>")
        self.emit("toggle", self.active)


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

class Item(gtk.HBox):

    def __init__(self, event, allow_pin = False):

        gtk.HBox.__init__(self)
        self.set_border_width(2)
        self.allow_pin = allow_pin
        self.btn = gtk.Button()
        self.search_results = []
        self.in_search = False
        self.event = event
        self.subject = event.subjects[0]
        self.gio_file = GioFile.create(self.subject.uri)
        self.time = float(event.timestamp) / 1000
        self.time =  time.strftime("%H:%M", time.localtime(self.time))



        if self.gio_file is not None:
            self.icon = self.gio_file.get_icon(
                can_thumb=settings.get('small_thumbnails', False), border=0)
        else:
            self.icon = None
        self.btn.set_relief(gtk.RELIEF_NONE)
        self.btn.set_focus_on_click(False)
        self.__init_widget()
        self.show_all()
        self.markup = None

        ITEMS.append(self)

    def highlight(self):
        #print len(searchbox.results)
        if self.search_results != searchbox.results:
            self.search_results = searchbox.results
            rc_style = self.style
            if self.subject.uri in searchbox.results:
                self.label.set_markup("<span><b>"+self.subject.text+"</b></span>")
                self.in_search = True
                color = rc_style.base[gtk.STATE_SELECTED]
                self.label.modify_fg(gtk.STATE_NORMAL, color)
            else:
                self.label.set_markup("<span>"+self.subject.text+"</span>")
                self.in_search = False
                color = rc_style.text[gtk.STATE_NORMAL]
                self.label.modify_fg(gtk.STATE_NORMAL, color)

    def __init_widget(self):
        self.label = gtk.Label(self.subject.text)
        self.label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self.label.set_alignment(0.0, 0.5)

        img = gtk.image_new_from_pixbuf(self.icon)
        hbox = gtk.HBox()
        hbox.pack_start(img, False, False, 1)
        hbox.pack_start(self.label, True, True, 4)

        if self.allow_pin:
            # TODO: get the name "pin" from theme when icons are properly installed
            img = gtk.image_new_from_file(get_icon_path("hicolor/24x24/status/pin.png"))
            self.pin = gtk.Button()
            self.pin.add(img)
            self.pin.set_tooltip_text(_("Remove Pin"))
            self.pin.set_focus_on_click(False)
            self.pin.set_relief(gtk.RELIEF_NONE)
            self.pack_end(self.pin, False, False)
            self.pin.connect("clicked", lambda x: self.set_bookmarked(False))
        #hbox.pack_end(img, False, False)
        evbox = gtk.EventBox()
        self.btn.add(hbox)
        evbox.add(self.btn)
        self.pack_start(evbox)

        self.btn.connect("clicked", self.launch)
        self.btn.connect("button_press_event", self._show_item_popup)

        def realize_cb(widget):
            evbox.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))

        self.btn.connect("realize", realize_cb)


        def change_style(widget, style):
            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL]
            fcolor = rc_style.fg[gtk.STATE_NORMAL]
            color = combine_gdk_color(color, fcolor)

            if self.in_search:
                color = rc_style.bg[gtk.STATE_SELECTED]
                self.label.modify_text(gtk.STATE_NORMAL, color)
            else:
                color = rc_style.text[gtk.STATE_NORMAL]
                self.label.modify_text(gtk.STATE_NORMAL, color)
            self.highlight()

            color = rc_style.bg[gtk.STATE_NORMAL]
            color = shade_gdk_color(color, 102/100.0)
            evbox.modify_bg(gtk.STATE_NORMAL, color)

        self.connect("style-set", change_style)

        self.init_multimedia_tooltip()

    def init_multimedia_tooltip(self):
        """add multimedia tooltip to multimedia files
        multimedia tooltip is shown for all images, all videos and pdfs

        TODO: make loading of multimedia thumbs async
        """
        if self.gio_file is not None and self.gio_file.has_preview():
            icon_names = self.gio_file.icon_names
            self.set_property("has-tooltip", True)
            self.connect("query-tooltip", self._handle_tooltip)
            if "video-x-generic" in icon_names and gst is not None:
                self.set_tooltip_window(VideoPreviewTooltip)
            else:
                self.set_tooltip_window(StaticPreviewTooltip)

    def _handle_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        # nothing to do here, we always show the multimedia tooltip
        # if we like video/sound preview later on we can start them here
        tooltip_window = self.get_tooltip_window()
        return tooltip_window.preview(self.gio_file)

    def _show_item_popup(self, widget, ev):
        if ev.button == 3:
            items = [self.subject.uri]
            ContextMenu.do_popup(ev.time, items)

    def set_bookmarked(self, bool_):
        uri = unicode(self.subject.uri)
        if bool_:
            bookmarker.bookmark(uri)
        else:
            bookmarker.unbookmark(uri)


    def launch(self, *discard):
        if self.gio_file is not None:
            self.gio_file.launch()


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

    def __init__(self):
        super(ContextMenu, self).__init__()
        self.menuitems = {
            "open" : gtk.ImageMenuItem(gtk.STOCK_OPEN),
            "unpin" : gtk.MenuItem(_("Remove Pin")),
            "pin" : gtk.MenuItem(_("Pin to Today")),
            "delete" : gtk.MenuItem(_("Delete item from Journal")),
            "related" : gtk.MenuItem(_("Most used with...")),
            }
        callbacks = {
            "open" : self.do_open,
            "unpin" : self.do_unbookmark,
            "pin" : self.do_bookmark,
            "delete" : self.do_delete,
            "related" : self.do_get_related,
            }
        names = ["open", "unpin", "pin", "delete", "related"]
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
        for uri in self.subjects:
            gfile = GioFile(uri)
            gfile.launch()

    def do_get_related(self, menuitem):
        def handler(uris):
            print "........"
            print "***", uri, "***"
            print "--- related to ---"
            for uri_ in uris:
                print uri_
            print "........"

        for uri in self.subjects:
            end = time.time() * 1000
            start = end - 60*60*14*1000
            CLIENT.find_related_uris_for_uris([uri], handler)

    def do_bookmark(self, menuitem):
        for uri in self.subjects:
            uri = unicode(uri)
            isbookmarked = bookmarker.is_bookmarked(uri)
            if not isbookmarked:
                bookmarker.bookmark(uri)

    def do_unbookmark(self, menuitem):
        for uri in self.subjects:
            uri = unicode(uri)
            isbookmarked = bookmarker.is_bookmarked(uri)
            if isbookmarked:
                bookmarker.unbookmark(uri)

    def do_delete(self, menuitem):
        for uri in self.subjects:
            CLIENT.find_event_ids_for_template(
                Event.new_for_values(subject_uri=uri),
                lambda ids: CLIENT.delete_events(map(int, ids)))
    
    def do_send_to(self, menuitem):
        launch_command("nautilus-sendto", self.subjects)


searchbox = SearchBox()
if gst is not None:
    VideoPreviewTooltip = VideoPreviewTooltip()
else:
    VideoPreviewTooltip = None
StaticPreviewTooltip = StaticPreviewTooltip()
ContextMenu = ContextMenu()
