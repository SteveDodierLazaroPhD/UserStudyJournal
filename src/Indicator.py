# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Stefano Candori <stefano.candori@gmail.com>
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

import gtk
import os 

from config import get_icon_path, settings

HAS_INDICATOR = True
try:
    import appindicator
except ImportError:
    HAS_INDICATOR = False
else:
    class Indicator(appindicator.Indicator):
        """
        A widget that implements the appindicator for ubuntu
        """
        def __init__(self, main_window):
            path = get_icon_path("hicolor/scalable/apps/gnome-activity-journal.svg")
            name = "Gnome Activity Journal"
            appindicator.Indicator.__init__(self, name, path, \
                appindicator.CATEGORY_APPLICATION_STATUS)

            self.main_window = main_window
            menu = Menu(self.main_window)
            self.set_menu(menu)

        def set_visible(self, bool):
            if not bool: self.set_status(appindicator.STATUS_PASSIVE)
            else: self.set_status(appindicator.STATUS_ACTIVE)

class TrayIcon(gtk.StatusIcon):
    """
    A widget that implements the tray icon
    """
    def __init__(self, main_window):

        gtk.StatusIcon.__init__(self)
        self.main_window = main_window
        path = get_icon_path("hicolor/scalable/apps/gnome-activity-journal.svg")
        self.set_from_file(path)
        self.set_tooltip("Gnome Activity Journal")
        self.connect('activate', self._on_activate)
        self.connect('popup-menu', self._on_popup)

        self.menu = Menu(self.main_window)

    def _on_activate(self, trayicon):
        if(self.main_window.get_property("visible")):
            self.main_window.hide()
        else:
            self.main_window.show()

    def _on_popup(self, trayicon, button, activate_time):
        position = None
        if os.name == 'posix':
            position = gtk.status_icon_position_menu
        self.menu.popup(None, None, position, button, activate_time, trayicon)

class Menu(gtk.Menu):
    """
    a widget that represents the menu displayed on the trayicon on the
    main window
    """

    def __init__(self, main_window):
        
        gtk.Menu.__init__(self)
        self.main_window = main_window
        self.hide_show_mainwindow = gtk.MenuItem(_('Hide/Show GAJ'))
        self.hide_show_mainwindow.connect('activate', self._on_activate)
        self.quit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        self.quit.connect('activate',
            lambda *args: self.main_window.quit_and_save())

        self.append(self.hide_show_mainwindow)
        self.append(gtk.SeparatorMenuItem())
        self.append(self.quit)

        self.show_all()

    def _on_activate(self, tray):
        if(self.main_window != None):
            if(self.main_window.get_property("visible")):
                self.main_window.hide()
            else:
                self.main_window.show()

class TrayIconManager():

    def __init__(self, main_window):
        self.tray = None
        self.main_window = main_window
        if settings.get("tray_icon", False):
            self._create_tray_icon(self.main_window)

        settings.connect("tray_icon", self._on_tray_conf_changed)

    def _create_tray_icon(self, main_window):
        if HAS_INDICATOR: self.tray = Indicator(main_window)
        else: self.tray = TrayIcon(main_window)  
       
        self.tray.set_visible(True)

    def _on_tray_conf_changed(self, *args):
        if not settings.get("tray_icon", False):
            self.tray.set_visible(False)
        else:
            if not self.tray:
                self._create_tray_icon(self.main_window)
            else:
                self.tray.set_visible(True)

