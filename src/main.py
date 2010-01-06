# -.- coding: utf-8 -.-

# Zeitgeist
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
import pango
import gobject
import time
import datetime
from widgets import *
from view import ActivityView

class Portal(gtk.Window):

    settingswindow = None

    def __init__(self):
        
        gtk.Window.__init__(self)
        
        self.connect("destroy", self.quit)
        self.set_size_request(800, 360)
        self.settingswindow = None
        self.set_title("Journal")
        
        self.vbox = gtk.VBox()
        #color = gtk.gdk.rgb_get_colormap().alloc_color('#EEEEEC')
        #self.modify_bg(gtk.STATE_NORMAL, color)
        self.activityview = ActivityView()
        self._init_toolbar()
        
        # We configure the view so that the left/right buttons touch the
        # left/right edges in order to utilize Fitts law. This is accomplished
        # by having no padding on the HBox
        self.add(self.vbox)
        self.vbox.pack_start(self.toolbar, False, False, 6)
        hbox = gtk.HBox()
        hbox.pack_start(self.backbtn, False, False)        
        hbox.pack_start(self.activityview)
        hbox.pack_start(self.fwdbtn, False, False)
        self.vbox.pack_start(hbox, True, True, 12)
        
        self.show_all()
        self.activityview.optionsbar.hide_all()
        self.toolbar.hide_all()
        self.maximize()

    def destroy_settings(self, w):
        self.settingswindow = None

    def _init_toolbar(self):
        self.toolbar = gtk.HBox()
        
        toolbar = gtk.Toolbar()
        self.toolbar.pack_start(toolbar)
        
        toolbar2 = gtk.Toolbar()
        self.toolbar.pack_end(toolbar2, False, False)
        
        self.backbtn = gtk.Button()
        self.backbtn.add(gtk.Arrow(gtk.ARROW_LEFT, gtk.SHADOW_NONE))
        self.backbtn.set_relief(gtk.RELIEF_NONE)
        self.backbtn.set_focus_on_click(False)
        self.fwdbtn = gtk.Button()
        self.fwdbtn.set_relief(gtk.RELIEF_NONE)
        self.fwdbtn.add(gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_NONE))
        self.fwdbtn.set_focus_on_click(False)
        
        self.todaybtn = gtk.ToolButton("gtk-home")
        self.optbtn = gtk.ToggleToolButton("gtk-preferences")
        
        self.fwdbtn.set_size_request(34,-1)
        self.backbtn.set_size_request(34,-1)
        
        def toggle_optionsbar(widget):
            if not widget.get_active():
                self.optbtn.set_tooltip_text("Show Options")
            else:
                self.optbtn.set_tooltip_text("Hide Options")

        self.todaybtn.connect("clicked", lambda w: self.activityview._set_today_timestamp())
        self.backbtn.connect("clicked", lambda w: self.activityview.jump(-86400))
        self.fwdbtn.connect("clicked", lambda w: self.activityview.jump(86400))
        self.optbtn.connect("toggled", self.activityview.toggle_optionsbar)
        self.optbtn.connect("toggled", toggle_optionsbar)
        
        self.backbtn.set_tooltip_text(_("Go back in time"))
        self.fwdbtn.set_tooltip_text(_("Look into the future"))
        self.todaybtn.set_tooltip_text(_("Recent Events"))
        self.optbtn.set_tooltip_text(_("Show Options"))
        
        self.horviewbtn = gtk.ToggleToolButton()
        self.verviewbtn = gtk.ToggleToolButton()
        
        pixbuf = gtk.gdk.pixbuf_new_from_file_at_size("data/view-calendar-workweek.svg", 24, 24) 
        img = gtk.image_new_from_pixbuf(pixbuf)
        self.horviewbtn.set_icon_widget(img)
        self.horviewbtn.set_active(True)
        
        pixbuf = gtk.gdk.pixbuf_new_from_file_at_size("data/view-calendar-list.svg", 24, 24) 
        img = gtk.image_new_from_pixbuf(pixbuf)
        self.verviewbtn.set_icon_widget(img)
        
        self.horviewbtn.connect("toggled", self.toggle_view)
        self.verviewbtn.connect("toggled", self.toggle_view)
        self.__togglingview = False
        
        toolbar.add(self.todaybtn)
        toolbar.add(gtk.SeparatorToolItem())
        toolbar.add(self.horviewbtn)
        toolbar.add(self.verviewbtn)
        toolbar.add(gtk.SeparatorToolItem())
        toolbar.add(self.optbtn)
        
        hbox = gtk.HBox()
        self.searchbar = SearchEntry()
        hbox.pack_end(self.searchbar)
        toolbar2.add(hbox)
        
        self.show_all()

    def toggle_view(self, widget):
        if not self.__togglingview:
            self.__togglingview = True
            if widget == self.horviewbtn:
                if self.horviewbtn.get_active():
                    self.verviewbtn.set_active(False)
                else:
                    self.horviewbtn.set_active(True)
                if not settings.view == "Journal":
                    settings.set_view("Journal")
            else:
                if self.verviewbtn.get_active():
                    self.horviewbtn.set_active(False)
                else:
                    self.verviewbtn.set_active(True)
                if settings.view == "Journal":
                    settings.set_view("List")
            self.__togglingview = False


    def quit(self, widget):
        gtk.main_quit()

