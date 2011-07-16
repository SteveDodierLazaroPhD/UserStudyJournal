# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Stefano Candori <stefano.candori@gmail.com>
# Copyright © 2011 Collabora Ltd.
#             By Siegfried-Angel Gevatter Pujals <siegfried@gevatter.com>
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
from blacklist import BLACKLIST
from common import ignore_exceptions

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
            name = _("Activity Journal")
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
        path = get_icon_path("hicolor/scalable/apps/gnome-activity-journal-paused.svg")
        self.set_from_file(path)
        self.set_tooltip(_("Activity Journal"))
        self.connect('activate', self._on_activate)
        self.connect('popup-menu', self._on_popup)

        self.menu = Menu(self.main_window, self)

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

    def set_icon(self, paused):
        if paused:
            name = "hicolor/scalable/apps/gnome-activity-journal-paused.svg"
        else:
            name = "hicolor/scalable/apps/gnome-activity-journal.svg"
        self.set_from_file(get_icon_path(name))

class Menu(gtk.Menu):
    """
    a widget that represents the menu displayed on the trayicon on the
    main window
    """

    def __init__(self, main_window, parent=None):
        
        gtk.Menu.__init__(self)
        self.main_window = main_window
        self._parent = parent
        self.hide_show_mainwindow = gtk.MenuItem(_('Hide/Show GAJ'))
        self.hide_show_mainwindow.connect('activate', self._on_activate)
        self.incognito_enable = gtk.MenuItem(_('Start incognito mode (pause event logging)'))
        self.incognito_enable.connect('activate', self._toggle_incognito)
        self.incognito_disable = gtk.MenuItem(_('Resume event logging (exit incognito)'))
        self.incognito_disable.connect('activate', self._toggle_incognito)
        self.quit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        self.quit.connect('activate',
            lambda *args: self.main_window.quit_and_save())

        self.append(self.hide_show_mainwindow)
        self.append(self.incognito_enable)
        self.append(self.incognito_disable)
        self.append(gtk.SeparatorMenuItem())
        self.append(self.quit)

        self.show_all()
        
        BLACKLIST.set_incognito_toggle_callback(self._update_incognito)
        if self._update_incognito() is None:
            self.incognito_enable.hide()
            self.incognito_disable.hide()

    def _on_activate(self, tray):
        if(self.main_window != None):
            if(self.main_window.get_property("visible")):
                self.main_window.hide()
            else:
                self.main_window.show()

    @ignore_exceptions()
    def _update_incognito(self):
        enabled = BLACKLIST.get_incognito()
        if enabled:
            self.incognito_enable.hide()
            self.incognito_disable.show()
        else:
            self.incognito_enable.show()
            self.incognito_disable.hide()
        if self._parent is not None:
            self._parent.set_icon(paused=enabled)
        return enabled
    
    @ignore_exceptions()
    def _toggle_incognito(self, *discard):
        BLACKLIST.toggle_incognito()

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

