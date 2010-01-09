# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Siegfried Gevatter <siegfried@gevatter.com>
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
from ui_utils import *
#from teamgeist import TeamgeistInterface

class SearchBox(gtk.HBox):
    def __init__(self):
        gtk.HBox.__init__(self)
        self.search = SearchEntry()
        self.pack_start(self.search)
        self.set_border_width(3)
        
        self.category = {}
        
        for source in SUPPORTED_SOURCES.keys():
            s = SUPPORTED_SOURCES[source]._desc_pl
            self.category[s] = source
            
        self._init_combobox()
        self.show_all()
        
    def _init_combobox(self):
        self.combobox = gtk.combo_box_new_text()
        self.pack_end(self.combobox, False, False, 3)
        self.combobox.append_text("All Activities")
        self.combobox.set_active(0)
        for cat in self.category.keys():
            self.combobox.append_text(cat)
        

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
        #self.connect("icon-press", self._icon_press)

        #self.set_property("primary-icon-name", gtk.STOCK_FIND)
        #self.set_property("secondary-icon-name", gtk.STOCK_CLEAR)
        #self.set_has_frame(False)

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

        self.btn = gtk.Button()
        self.btn.set_relief(gtk.RELIEF_NONE)
        self.btn.set_size_request(32,32)
        self.btn.set_focus_on_click(False)
        self.btn.add(hbox)

        self.img = gtk.Label()
        self.img.set_markup("<span size='small'><b>+</b></span>")
        self.img.set_alignment(0.5, 0.5)
        btn = gtk.Button()
        btn.add(self.img)
        #btn.set_sensitive(False)
        btn.set_size_request(21,21)
        
        hbox.pack_start(btn, False, False)
        self.active = False

        self.pack_start(self.btn)
        #self.pack_start(self.img, False, False)
        if category:
            self.label.set_markup("<span>%s</span>" % \
                                  SUPPORTED_SOURCES[category].group_label(count))
        self.label.set_ellipsize(pango.ELLIPSIZE_END)
        hbox.pack_start(self.label, True, True, 9)

        label = gtk.Label()
        label.set_markup("<span>(%d)</span>" % count)
        label.set_alignment(1.0,0.5)
        hbox.pack_end(label, False, False)
        self.show_all()

        self.btn.connect("clicked", self.toggle)
        btn.set_relief(gtk.RELIEF_HALF)
        
        def change_style(widget, style):
            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL]
            
            if color.red * 125/100 > 65535.0:
            	color.red = 65535.0
            else:
                color.red = color.red * 125 / 100
            	
            if color.green * 125/100 > 65535.0:
            	color.green = 65535.0
            else:
            	color.green = color.green * 125 / 100
            	
            if color.blue * 125/100 > 65535.0:
            	color.blue = 65535.0
            else:
                color.blue = color.blue * 125 / 100
                
            btn.modify_bg(gtk.STATE_NORMAL, color)
            
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
            self.img.set_markup("<span size='small'><b>-</b></span>")
        else:
            self.img.set_markup("<span size='small'><b>+</b></span>")
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
        self.connect("button_press_event", self._show_item_popup)
        
        def change_style(widget, style):
            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL]
            fcolor = rc_style.fg[gtk.STATE_NORMAL] 
            color.red = (2*color.red + fcolor.red)/3
            color.green = (2*color.green + fcolor.green)/3
            color.blue = (2*color.blue + fcolor.blue)/3
            label.modify_fg(gtk.STATE_NORMAL, color)

        self.connect("style-set", change_style)
        
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
        #if item["bookmark"]:
            #bookmark = gtk.MenuItem(("Unbookmark"))
        #else:
            #bookmark = gtk.MenuItem(("Bookmark"))
        #bookmark.connect("activate", lambda w: self.toggle_bookmark(item=item))
        #bookmark.show()
        #menu.append(bookmark)
                
        #tag = gtk.MenuItem(("Edit tags..."))
        #tag.connect("activate", lambda w: self.tag_item(item))
        #tag.show()
        #menu.append(tag)

    def launch(self, *discard):
        launcher.launch_uri(self.subject.uri, self.subject.mimetype)
