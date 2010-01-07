# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Siegfried Gevatter <siegfried@gevatter.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
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
        self.label = gtk.Label()
        self.label.set_alignment(0.0, 0.5)
        hbox = gtk.HBox()
        
        self.expander = gtk.LinkButton("")
        self.expander.set_label("Show")
        self.expander.set_focus_on_click(False)
        self.expander.set_focus_chain([])
        self.expander.set_relief(gtk.RELIEF_NONE)
            
        self.active = False

        self.pack_start(hbox)
        #self.pack_start(self.img, False, False)
        if category:
            self.label.set_markup("<span>%s</span>" % \
                                  SUPPORTED_SOURCES[category].group_label(count))
        self.label.set_ellipsize(pango.ELLIPSIZE_END)
        
        label = gtk.Label()
        label.set_markup("<span><b>%d</b></span>" % count)
        label.set_alignment(1.0,0.5)
        self.show_all()
        
        hbox.pack_start(label, False, False)
        hbox.pack_start(self.label, True, True, 9)
        hbox.pack_end(self.expander, False, False)


        self.expander.connect("clicked", self.toggle)
        #btn.set_relief(gtk.RELIEF_HALF)
        
        def change_style(widget, style):
            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL] 
            color.red = color.red*2/3
            color.green = color.green*2/3
            color.blue = color.blue*2/3
            label.modify_fg(gtk.STATE_NORMAL, color)
            
        self.connect("style-set", change_style)
        


    def toggle(self, widget):
        self.active = not self.active
        if self.active:
            self.expander.set_label("Hide")
        else:
            self.expander.set_label("Show")
        self.emit("toggle", self.active)

class Item(gtk.Button):

    def __init__(self, event):

        gtk.Button.__init__(self)

        self.event = event
        self.subject = event.subjects[0]
        self.time = float(event.timestamp) / 1000
        self.icon = thumbnailer.get_icon(self.subject, 24)
        self.set_relief(gtk.RELIEF_NONE)
        self.set_focus_on_click(False)
        label = gtk.Label(self.subject.text)
        label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        label.set_alignment(0.0, 0.5)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.image_new_from_pixbuf(self.icon), False, False)
        hbox.pack_start(label, True, True, 9)

        label = gtk.Label()
        t = datetime.datetime.fromtimestamp(self.time).strftime("%H:%M")
        label.set_markup("<span>%s</span>" % t)
        hbox.pack_end(label, False, False)
        self.add(hbox)

        self.connect("clicked", self.launch)
        
        def change_style(widget, style):
            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL] 
            color.red = color.red*2/3
            color.green = color.green*2/3
            color.blue = color.blue*2/3
            label.modify_fg(gtk.STATE_NORMAL, color)
                

        self.connect("style-set", change_style)

    def launch(self, *discard):
        launcher.launch_uri(self.subject.uri, self.subject.mimetype)
