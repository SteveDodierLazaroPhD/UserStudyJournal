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
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gtk
import gettext
import pango
import gobject
import time
import datetime
import os

from config import ACCESSIBILITY, settings, get_data_path, get_icon_path
from widgets import *
from view import ActivityView
from histogram import HistogramWidget, JournalHistogram, CairoHistogram
from daywidgets import DayButton


class Portal(gtk.HBox):

    def __init__(self):
        super(Portal, self).__init__()

        self.vbox = gtk.VBox()

        if ACCESSIBILITY:
            self.cal = HistogramWidget(CairoHistogram)
        else:
            self.cal = HistogramWidget(JournalHistogram)
        self.activityview = ActivityView(self.cal)
        if settings["amount_days"]:
            self.activityview.set_num_days(settings["amount_days"])
        settings.connect("amount_days", lambda key, value:
                         self.activityview.set_num_days(value or 3))

        self.backbtn = DayButton(0)
        self.fwdbtn = DayButton(1)
        self.fwdbtn.set_sensitive(False)

        def handle_fwd_leading(widget, i, ii):
            self.throbber.animate_for_seconds(1)
            if i == len(widget.get_datastore()) - widget.selected_range - 1:
                self.fwdbtn.leading = True
            else:
                self.fwdbtn.leading = False
            if ii < len(widget.get_datastore()) - 1:
                self.fwdbtn.set_sensitive(True)
            else:
                self.fwdbtn.set_sensitive(False)
            return True
        self.cal.histogram.connect("selection-set", handle_fwd_leading)

        self.backbtn.connect("clicked", self.moveback)
        self.fwdbtn.connect("clicked", self.moveup)

        self.add(self.vbox)
        self.rbox = gtk.VBox()
        self.rbox.pack_start(self.fwdbtn)

        hbox = gtk.HBox()

        hbox.pack_start(self.backbtn, False, False)
        hbox.pack_start(self.activityview,3)
        hbox.pack_start(self.rbox, False, False)

        self.vbox.pack_start(hbox, True, True, 6)

        self.throbber = AnimatedImage(get_data_path("zlogo/zg%d.png"), 150)
        self.throbber.set_tooltip_text(_("Powered by Zeitgeist"))
        self.throbber.set_alignment(0.9, 0.98)
        aboutbox = gtk.EventBox()
        aboutbox.add(self.throbber)
        aboutbox.connect("button-press-event", self.show_about_window)
        align = gtk.Alignment()
        align.add(self.cal)
        align.set(0, 0, 1, 1)
        align.set_padding(0, 0, 23, 7)
        calhbox = gtk.HBox()
        calhbox.pack_start(align, True, True, 0)
        calhbox.pack_start(aboutbox, False, False)
        self.vbox.pack_end(calhbox, False, False)


        # FIXME: We give focus to the text entry so that it doesn't go to the
        # "go back" button. Ideally it would be on the first event of the
        # current day.

        self.show_all()
        self.activityview.searchbox.hide()
        self.connect("key-press-event", self._global_keypress_handler)
        self.cal.histogram.connect("column_clicked", self.handle_fwd_sensitivity)

    def show_about_window(self, widget, event):
        aboutwindow = AboutDialog()
        aboutwindow.set_transient_for(self)
        aboutwindow.run()
        aboutwindow.destroy()

    def _global_keypress_handler(self, widget, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            if gtk.gdk.keyval_name(event.keyval) == "f":
                self.activityview.searchbox.show()
                self.set_focus(self.activityview.searchbox.search)
                return True
        elif event.keyval == gtk.keysyms.Home:
            i  = len(self.cal.histogram.get_datastore()) - 1
            self.cal.histogram.change_location(i)
            return True
        return False

    def jumpup(self, data=None):
        self.activityview._set_today_timestamp()
        self.fwdbtn.set_sensitive(False)

    def moveup(self, data=None):
        self.activityview.jump(86400)
        dayinfocus = int(time.mktime(time.strptime(time.strftime("%d %B %Y") , "%d %B %Y")))
        if (dayinfocus) < self.activityview.end:
            self.fwdbtn.set_sensitive(False)

    def handle_fwd_sensitivity(self, widget, i):
        datastore = widget.get_datastore()
        if i < len(datastore) - 1:
            self.fwdbtn.set_sensitive(True)
        else:
            self.fwdbtn.set_sensitive(False)

    def moveback(self, data=None):
        self.activityview.jump(-86400)
        self.fwdbtn.set_sensitive(True)


class PortalWindow(gtk.Window):
    def __init__(self):
        """"""
        gtk.Window.__init__(self)
        gtk.Window.__init__(self)
        self._requested_size = None

        self.connect("destroy", self.quit)
        self.set_title(_("Activity Journal"))
        self.set_position(gtk.WIN_POS_CENTER)

        # Detect when we are maximized
        self.connect("window-state-event", self._on_window_state_changed)

        self.set_icon_name("gnome-activity-journal")
        self.set_icon_list(
            *[gtk.gdk.pixbuf_new_from_file(get_icon_path(f)) for f in (
                "hicolor/16x16/apps/gnome-activity-journal.png",
                "hicolor/24x24/apps/gnome-activity-journal.png",
                "hicolor/32x32/apps/gnome-activity-journal.png",
                "hicolor/48x48/apps/gnome-activity-journal.png",
                "hicolor/256x256/apps/gnome-activity-journal.png")])
        self.portal = Portal()
        self.add(self.portal)
        self.set_focus(self.portal.activityview.searchbox.search)
        self.portal.activityview.connect("date-updated", self._title_handler)

        self._request_size()
        self.connect("configure-event", self._on_size_changed)
        start = datetime.date.fromtimestamp(self.portal.activityview.start).strftime("%A")
        self.set_title(_("%s to today") % start + " - " + _("Activity Journal"))
        self.show()

    def _title_handler(self, widget, starti, endi, singleday):
        endday = datetime.date.fromtimestamp(endi)
        startday = datetime.date.fromtimestamp(starti)
        if endday.day == datetime.date.today().day:
            end = _("Today")
            start = startday.strftime("%A")
        elif endday.day == datetime.date.today().day-1:
            end = _("Yesterday")
            start = startday.strftime("%A")
        elif endday.day + 6 > datetime.date.today().day:
            end = endday.strftime("%A")
            start = startday.strftime("%A")
        else:
            start = startday.strftime("%d %B")
            end = endday.strftime("%d %B")
        if singleday:
            self.set_title(end + " - Activity Journal")
        else:
            self.set_title(_("%s to %s") % (start, end) + " - " + _("Activity Journal"))

    def _on_window_state_changed (self, win, event):
        # When maximized we configure the view so that the left/right buttons
        # touch the left/right edges of the screen in order to utilize Fitts law
        if event.new_window_state & gtk.gdk.WINDOW_STATE_MAXIMIZED:
            # FIXME: Keep vertical padding on self.vbox children withou
            #        introducing horizontal padding
            self.set_border_width(0)
            self.vbox.set_border_width(0)
        else:
            self.set_border_width(0)
            self.portal.vbox.set_property("border-width", 0)

    def _request_size(self):
        screen = self.get_screen().get_monitor_geometry(
            self.get_screen().get_monitor_at_point(*self.get_position()))

        min_size = (1024, 600) # minimum netbook size
        size = [
            min(max(int(screen[2] * 0.80), min_size[0]), screen[2]),
            min(max(int(screen[3] * 0.75), min_size[1]), screen[3])
        ]
        if settings["window_width"] and settings["window_width"] <= screen[2]:
            size[0] = settings['window_width']
        if settings["window_height"] and settings["window_height"] <= screen[3]:
            size[1] = settings["window_height"]

        self.set_geometry_hints(min_width=800, min_height=360)
        self.resize(size[0], size[1])
        self._requested_size = size

    def _on_size_changed(self, window, event):
        if (event.width, event.height) not in self._requested_size:
            settings["window_width"] = event.width
            settings["window_height"] = event.height
        if not settings["amount_days"]:
            self.activityview.set_num_days(4 if event.width >= 1300 else 3)

    def quit(self, widget):
        gtk.main_quit()
