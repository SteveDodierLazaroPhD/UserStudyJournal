'''
Created on Nov 28, 2009

@author: seif
'''

import gtk
import gettext
import datetime
import gobject
import pango
from ui_utils import *
#from teamgeist import TeamgeistInterface

class ToggleButton(gtk.ToggleButton):
    def __init__(self, category):
        gtk.ToggleButton.__init__(self)
        self.category = category
        self.text = SUPPORTED_SOURCES[category].name
        img = gtk.image_new_from_pixbuf(get_category_icon(SUPPORTED_SOURCES[category].icon, 16))
        self.set_image(img)
        self.set_relief(gtk.RELIEF_NONE)
        self.set_focus_on_click(False)
        self.connect("toggled", lambda w: settings.toggle_compression(self.category, self.get_active()))
        
class Tab(gtk.HBox):
    def __init__(self, text):
        gtk.HBox.__init__(self)
        self.label = gtk.Label(text)
        self.pack_start(self.label)

        self.closebtn= gtk.Button()
        self.closebtn.set_focus_on_click(False)
        self.closebtn.set_relief(gtk.RELIEF_NONE)
        img = gtk.image_new_from_stock("gtk-close", 4)
        self.closebtn.add(img)
        self.pack_end(self.closebtn)
        
        self.show_all()

class SearchEntry(gtk.Entry):

    __gsignals__ = {
        "clear" : (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   ()),
        "search" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_STRING,))
    }

    default_text = _("Search...")

    # The font style of the text in the entry.
    font_style = None

    # TODO: What is this?
    search_timeout = 0

    def __init__(self, accel_group = None):
        gtk.Entry.__init__(self)

        self.set_width_chars(30)
        self.set_text(self.default_text)

        self.connect("changed", lambda w: self._queue_search())
        self.connect("focus-in-event", self._entry_focus_in)
        self.connect("focus-out-event", self._entry_focus_out)
        self.connect("icon-press", self._icon_press)

        self.set_property("primary-icon-name", gtk.STOCK_FIND)
        self.set_property("secondary-icon-name", gtk.STOCK_CLEAR)

        self.font_style = self.get_style().font_desc
        self.font_style.set_style(pango.STYLE_ITALIC)
        self.modify_font(self.font_style)

        self.show_all()

    def _icon_press(self, widget, pos, event):
        # Note: GTK_ENTRY_ICON_SECONDARY does not seem to be bound in PyGTK.
        if int(pos) == 1 and not self.get_text() == self.default_text:
            self._entry_clear_no_change_handler()

    def _entry_focus_in(self, widget, x):
        if self.get_text() == self.default_text:
            self.set_text("")
            self.font_style.set_style(pango.STYLE_NORMAL)
            self.modify_font(self.font_style)

    def _entry_focus_out(self, widget, x):
        if self.get_text() == "":
            self.set_text(self.default_text)
            self.font_style.set_style(pango.STYLE_ITALIC)
            self.modify_font(self.font_style)

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
        #self.img = gtk.image_new_from_pixbuf(icon_factory.load_icon(SUPPORTED_SOURCES[category].icon, 24))
        self.label = gtk.Label(SUPPORTED_SOURCES[category].group_label(count))
        self.label.set_alignment(0.0, 0.5)
        #print SUPPORTED_SOURCES[category].name
        self.btn = gtk.Button()
        self.btn.set_relief(gtk.RELIEF_NONE)
        self.btn.set_size_request(32,32)
        self.img = gtk.Label()
        self.img.set_markup("<span><b>+</b></span>")
        self.btn.add(self.img)
        self.btn.set_focus_on_click(False)
        self.active = False
        
        self.pack_start(self.btn, False, False)
        #self.pack_start(self.img, False, False)
        self.pack_start(self.label)
        
        label = gtk.Label()
        label.set_markup("<span color='darkgrey'>"+"("+str(count)+")"+"</span>")
        label.set_alignment(1.0,0.5)
        self.pack_end(label, False, False, 3)
        self.show_all()
        
        self.btn.connect("clicked", self.toggle)
    
    def toggle(self, widget):
        self.active = not self.active
        if self.active:
            self.img.set_markup("<span><b>-</b></span>")
        else:
            self.img.set_markup("<span><b>+</b></span>")
        self.emit("toggle", self.active)
        
class Item(gtk.Button):
    def __init__(self, event):
        gtk.Button.__init__(self)
        self.event = event
        self.subject = event.subjects[0]
        self.time = float(event.timestamp)/1000
        self.icon = thumbnailer.get_icon(self.subject, 24)
        self.set_relief(gtk.RELIEF_NONE)
        self.set_focus_on_click(False)
        img = gtk.image_new_from_pixbuf(self.icon)
        label = gtk.Label(" "+self.subject.text)
        label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        label.set_alignment(0.0, 0.5)
        
        hbox = gtk.HBox()
        hbox.pack_start(img, False, False)
        hbox.pack_start(label)
        hbox.pack_start(img)
        self.add(hbox)