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
import pango
import gobject
import time
import datetime

from widgets import *
from view import ActivityView
from ui_utils import settings

class Portal(gtk.Window):

    def __init__(self):

        gtk.Window.__init__(self)
        self._screen = gtk.gdk.Screen()
        self._requested_size = None

        self.connect("destroy", self.quit)
        self.set_title("Journal")
        self.set_position(gtk.WIN_POS_CENTER)

        self.vbox = gtk.VBox()
        #color = gtk.gdk.rgb_get_colormap().alloc_color('#EEEEEC')
        #self.modify_bg(gtk.STATE_NORMAL, color)
        self.activityview = ActivityView()

        self.backbtn = gtk.Button()
        self.backbtn.add(gtk.Arrow(gtk.ARROW_LEFT, gtk.SHADOW_NONE))
        self.backbtn.set_relief(gtk.RELIEF_NONE)
        self.backbtn.set_focus_on_click(False)
        self.backbtn.set_tooltip_text(_("Go back in time"))
        self.fwdbtn = gtk.Button()
        self.fwdbtn.set_relief(gtk.RELIEF_NONE)
        self.fwdbtn.add(gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_NONE))
        self.fwdbtn.set_focus_on_click(False)
        self.fwdbtn.set_tooltip_text(_("Look into the future"))
        self.backbtn.connect("clicked", lambda w: self.activityview.jump(-86400))
        self.fwdbtn.connect("clicked", lambda w: self.activityview.jump(86400))

        # We configure the view so that the left/right buttons touch the
        # left/right edges in order to utilize Fitts law. This is accomplished
        # by having no padding on the HBox
        self.add(self.vbox)
        hbox = gtk.HBox()
        hbox.pack_start(self.backbtn, False, False)
        hbox.pack_start(self.activityview)
        hbox.pack_start(self.fwdbtn, False, False)
        self.vbox.pack_start(hbox, True, True, 12)

        self.show_all()

        # Do this after showing the window so that in environment with multiple
        # monitors we know which one will show the Journal.
        self._request_size()
        self.set_position(gtk.WIN_POS_CENTER)
        self.connect("configure-event", self._on_size_changed)

    def _request_size(self):
        screen = self._screen.get_monitor_geometry(
            self._screen.get_monitor_at_point(*self.get_position()))

        size = (int(screen[2] * 0.80), int(screen[3] * 0.75))
        if settings["window_size_x"] and settings["window_size_x"] <= screen[2]:
            size[0] = settings['window_size_x']
        size = (int(screen[2] * 0.80), int(screen[3] * 0.75))
        if settings["window_size_y"] and settings["window_size_y"] <= screen[3]:
            size[1] = settings["window_size_y"]

        self.set_geometry_hints(self, min_width=800, min_height=360,
            base_width=size[0], base_height=size[1])
        self._requested_size = size
    
    def _on_size_changed(self, window, event):
        pass #print event.height, event.width, self._requested_size

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
