# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Siegfried Gevatter <siegfried@gevatter.com>
# Copyright © 2010 Markus Korn <thekorn@gmx.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gtk
import gettext
import datetime
import gobject
import pango
import gio
try:
    import gst
except ImportError:
    gst = None
from ui_utils import *
#from teamgeist import TeamgeistInterface
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType
    
from bookmarker import bookmarker

from dbus.exceptions import DBusException
try:
    from tracker_wrapper import tracker
except DBusException:
    print "Tracker disabled."

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
            
            if color.red * 102/100 > 65535.0:
                color.red = 65535.0
            else:
                color.red = color.red * 102 / 100
                
            if color.green * 102/100 > 65535.0:
                color.green = 65535.0
            else:
                color.green = color.green * 102 / 100
                
            if color.blue * 102/100 > 65535.0:
                color.blue = 65535.0
            else:
                color.blue = color.blue * 102 / 100
                
            self.modify_bg(gtk.STATE_NORMAL, color)
            
            color = rc_style.bg[gtk.STATE_NORMAL]
            fcolor = rc_style.fg[gtk.STATE_NORMAL] 
            color.red = (2*color.red + fcolor.red)/3
            color.green = (2*color.green + fcolor.green)/3
            color.blue = (2*color.blue + fcolor.blue)/3
            
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
        self.img = gtk.Image()
        self.img.set_from_stock("gtk-add", 24)
        hbox.pack_start(gtk.Label(""), False, False, 1)
        hbox.pack_start(self.img, False, False, 0)
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
            color.red = (2*color.red + fcolor.red)/3
            color.green = (2*color.green + fcolor.green)/3
            color.blue = (2*color.blue + fcolor.blue)/3
            label.modify_fg(gtk.STATE_NORMAL, color)
            self.img.modify_fg(gtk.STATE_NORMAL, color)
            
        self.connect("style-set", change_style)
        

    def toggle(self, widget):
        self.active = not self.active
        if self.active:
            self.img.set_from_stock("gtk-remove", 24)
        else:
            self.img.set_from_stock("gtk-add", 24)
        self.emit("toggle", self.active)
        

class PreviewTooltip(gtk.Window):
    
    def __init__(self):
        gtk.Window.__init__(self, type=gtk.WINDOW_POPUP)
        
    def preview(self, subject, icon_factory=None):
        return True
        
class StaticPreviewTooltip(PreviewTooltip):
    
    def __init__(self):
        super(StaticPreviewTooltip, self).__init__()
        self.__current = None
        
    def preview(self, subject, icon_factory=None):
        if subject.uri == self.__current:
            return bool(self.__current)
        self.__current = subject.uri
        children = self.get_children()
        if children:
            self.remove(children[0])
            # hack to force the tooltip to have the exact same size
            # as the child image
            self.resize(1,1)
        pixbuf = thumbnailer.get_icon(subject, 200, icon_factory=icon_factory)
        if pixbuf is None:
            self.__current = None
            return False
        img = gtk.image_new_from_pixbuf(pixbuf)
        img.set_alignment(0.5, 0.5)
        img.show_all()
        self.add(img)
        return True
        
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
        
    def _handle_hide(self, widget):
        self.player.set_state(gst.STATE_NULL)
        
    def _handle_show(self, widget):
        self.player.set_state(gst.STATE_PLAYING)
        
    def preview(self, subject, icon_factory=None):
        if subject.uri == self.player.get_property("uri"):
            return True
        self.player.set_property("uri", subject.uri)
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

    def __init__(self, event):

        gtk.HBox.__init__(self)
        self.set_border_width(2)

        self.btn = gtk.Button()
        self.search_results = []
        self.in_search = False
        self.event = event
        self.subject = event.subjects[0]
        self.time = float(event.timestamp) / 1000
        self.icon = thumbnailer.get_icon(self.subject, 24)
        self.btn.set_relief(gtk.RELIEF_NONE)
        self.btn.set_focus_on_click(False)
        self.__init_widget()
        self.show_all()
        self.markup = None
        #self.set_bookmark_widget()
        self.pin.connect("clicked", lambda x: self.set_bookmarked(False))
        ITEMS.append(self)
        self.pin.hide()
    
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
        img.set_alignment(0.5, 0.5)
        img.set_size_request(24,24)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(""), False, False, 1)
        hbox.pack_start(img, False, False, 0)
        hbox.pack_start(gtk.Label(""), False, False, 3)
        hbox.pack_start(self.label, True, True)
        label = gtk.Label()
        t = datetime.datetime.fromtimestamp(self.time).strftime("%H:%M")
        label.set_markup("<span>%s</span>" % t)
        self.hbox = hbox
        #hbox.pack_end(label, False, False)
        
        img = gtk.image_new_from_file("data/pin.png")
        self.pin = gtk.Button()
        self.pin.add(img)
        self.pin.set_tooltip_text("Remove Pin")
        self.pin.set_focus_on_click(False)
        self.pin.set_relief(gtk.RELIEF_NONE)
        self.pack_end(self.pin, False, False)
        #hbox.pack_end(img, False, False)
        
        self.btn.add(hbox)
        self.pack_start(self.btn)
    
        self.btn.connect("clicked", self.launch)
        self.btn.connect("button_press_event", self._show_item_popup)
        
        def change_style(widget, style):
            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL]
            fcolor = rc_style.fg[gtk.STATE_NORMAL] 
            color.red = (2*color.red + fcolor.red)/3
            color.green = (2*color.green + fcolor.green)/3
            color.blue = (2*color.blue + fcolor.blue)/3
            label.modify_fg(gtk.STATE_NORMAL, color)
            
            if self.in_search:
                color = rc_style.bg[gtk.STATE_SELECTED]
                self.label.modify_text(gtk.STATE_NORMAL, color)
            else:
                color = rc_style.text[gtk.STATE_NORMAL]
                self.label.modify_text(gtk.STATE_NORMAL, color)
            self.highlight()

        self.connect("style-set", change_style)
        #bookmarker.connect("reload", lambda x, y: self.set_bookmark_widget())
        
        self.init_multimedia_tooltip()
        
    def init_multimedia_tooltip(self):        
        """add multimedia tooltip to multimedia files
        multimedia tooltip is shown for all images, all videos and pdfs
        
        TODO: make loading of multimedia thumbs async
        """
        self.__icon_factory = None
        f = gio.File(self.subject.uri)
        try:
            info = f.query_info("standard::icon")
            icon_names = info.get_attribute_object("standard::icon").get_names()
        except (gio.Error, AttributeError):
            # cannot query for icon info, don't know how to handle this item
            return
        is_opendocument = bool(
            filter(lambda name: "application-vnd.oasis.opendocument" in name, icon_names))
        if "video-x-generic" in icon_names or "image-x-generic" in icon_names \
            or "application-pdf" in icon_names or is_opendocument:
            self.set_property("has-tooltip", True)
            self.connect("query-tooltip", self._handle_tooltip)
            if "video-x-generic" in icon_names and gst is not None:
                self.set_tooltip_window(VideoPreviewTooltip)
            else:
                self.set_tooltip_window(StaticPreviewTooltip)
                self.__icon_factory = None
                if is_opendocument:
                    # OMG this is a dirty hack to get the path of the file
                    # python's zipfile modul cannot handle uris it needs
                    # unix paths
                    self.__icon_factory = \
                        lambda uri, icon_size, timestamp: thumbnailer.create_opendocument_thumb(f.get_path(), icon_size, timestamp)
                
        
    def _handle_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        # nothing to do here, we always show the multimedia tooltip
        # if we like video/sound preview later on we can start them here
        tooltip_window = self.get_tooltip_window()
        return tooltip_window.preview(self.subject, icon_factory=self.__icon_factory)
        
    def _show_item_popup(self, widget, ev):
        if ev.button == 3:
            item = self.subject
            if item:
                menu = gtk.Menu()
                menu.attach_to_widget(widget, None)
                self._populate_popup(menu, item)
                menu.popup(None, None, None, ev.button, ev.time)
     
    def _populate_popup(self, menu, item):
        open = gtk.ImageMenuItem (gtk.STOCK_OPEN)
        #open.connect("activate", lambda *discard: self._open_item(item=item))
        open.show()
        menu.append(open)
        bool = bookmarker.is_bookmarked(self.subject.uri)
        if bool:
            bookmark = gtk.MenuItem(("Remove Pin"))
        else:
            bookmark = gtk.MenuItem(("Pin to Today"))
        bookmark.connect("activate", lambda x: self.set_bookmarked(not bool))
        bookmark.show()
        menu.append(bookmark)
                
        #tag = gtk.MenuItem(("Edit tags..."))
        #tag.connect("activate", lambda w: self.tag_item(item))
        #tag.show()
        #menu.append(tag)

    def set_bookmarked(self, bool):
        uri = unicode(self.subject.uri)
        if bool:
            bookmarker.bookmark(uri)
        else:
            bookmarker.unbookmark(uri)
        #self.set_bookmark_widget()

    def launch(self, *discard):
        launcher.launch_uri(self.subject.uri, self.subject.mimetype)

searchbox = SearchBox()
VideoPreviewTooltip = VideoPreviewTooltip()
StaticPreviewTooltip = StaticPreviewTooltip()
