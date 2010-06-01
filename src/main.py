# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Siegfried Gevatter <siegfried@gevatter.com>
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

import gtk
import gettext
import pango
import gobject
import time
import datetime
import os

from activity_widgets import MultiViewContainer, TimelineViewContainer, ThumbViewContainer, PinnedPane
from supporting_widgets import DayButton, DayLabel, Toolbar, ContextMenu, AboutDialog, HandleBox, SearchBox, InformationContainer, PreferencesDialog
from histogram import HistogramWidget
from store import Store, tdelta, STORE, CLIENT
from config import settings, get_icon_path, get_data_path, PluginManager


AUTOLOAD = True # Should the store request events in the background?


class ViewContainer(gtk.Notebook):
    __gsignals__ = {
        "new-view-added" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,)),
        "view-button-clicked" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,gobject.TYPE_INT)),
    }

    class ViewStruct(object):
        view = None
        button = None

        def __init__(self, view, button):
            self.view = view
            self.button = button

    def __init__(self, store):
        super(ViewContainer, self).__init__()
        self.store = store
        self.set_show_tabs(False)
        self.set_show_border(False)
        self.pages = []
        self.tool_buttons = []
        self.mutliview = MultiViewContainer()
        self.thumbview = ThumbViewContainer()
        self.timelineview = TimelineViewContainer()
        map(self._register_new_view,
            (self.ViewStruct(self.mutliview, Toolbar.get_toolbutton(get_data_path("multiview_icon.png"), _("Switch to MultiView"))),
             self.ViewStruct(self.thumbview, Toolbar.get_toolbutton(get_data_path("thumbview_icon.png"), _("Switch to ThumbView"))),
             self.ViewStruct(self.timelineview, Toolbar.get_toolbutton(get_data_path("timelineview_icon.png"), _("Switch to TimelineView")))
             ))
        self.show_all()
        self.set_current_page(0)
        self.tool_buttons[0].set_sensitive(False)

    def set_day(self, day, page=None):
        if page == None:
            page = self.page
        if page < 3:
            self.pages[page].set_day(day, self.store)

    def _register_new_view(self, viewstruct):
        self.pages.append(viewstruct.view)
        self.tool_buttons.append(viewstruct.button)
        self.append_page(viewstruct.view)
        viewstruct.button.connect("clicked", self.view_button_clicked, len(self.pages)-1)
        viewstruct.view.show_all()
        return self.pages.index(viewstruct.view)

    def register_new_view(self, viewstruct):
        i = self._register_new_view(viewstruct)
        self.emit("new-view-added", viewstruct)
        return i

    @property
    def page(self):
        return self.get_current_page()

    def view_button_clicked(self, button, i):
        self.emit("view-button-clicked", button, i)


class PanedContainer(gtk.HBox):
    def __init__(self):
        super(PanedContainer, self).__init__()
        self.pane1 = pane1 = gtk.HPaned()
        self.pane2 = pane2 = gtk.HPaned()
        pane1.add2(pane2)
        self.boxes = {}
        box1 = self.left_box = gtk.EventBox()
        box2 = self.center_box = gtk.EventBox()
        box3 = self.right_box = gtk.EventBox()
        pane1.pack1(box1, False, False)
        pane2.pack1(box2, False, True)
        pane2.pack2(box3, False, False)
        self.add(pane1)

        self.informationcontainer = InformationContainer()
        ContextMenu.informationwindow = self.informationcontainer
        self.h1 = handle = HandleBox()
        handle.add(self.informationcontainer)
        box3.add(handle)
        self.informationcontainer.connect("hide", self.on_hide)
        self.informationcontainer.connect("show", self.on_show)
        self.informationcontainer.set_size_request(100, 100)
        self.pinbox = PinnedPane()
        self.pinbox.connect("hide", self.on_hide)
        self.pinbox.connect("show", self.on_show)
        self.h2 = handle = HandleBox()
        handle.add(self.pinbox)
        box1.add(handle)

    def on_show(self, w, *args):
        self.pane1.set_position(-1)
        self.pane2.set_position(-1)
        handle = self.h1 if w == self.informationcontainer else self.h2
        handle.show()
        if w == self.informationcontainer:
            self.right_box.show()
        elif w == self.pinbox:
            self.left_box.show()

    def on_hide(self, w, *args):
        self.pane1.set_position(-1)
        self.pane2.set_position(-1)
        handle = self.h1 if w == self.informationcontainer else self.h2
        handle.hide()
        if w == self.informationcontainer:
            self.right_box.hide()
        elif w == self.pinbox:
            self.left_box.hide()


class PortalWindow(gtk.Window):

    def __init__(self):
        super(PortalWindow, self).__init__()
        self.__initialized = False
        self._requested_size = None
        # Important
        self._request_size()
        self.store = STORE
        self.day_iter = self.store.today
        self.view = ViewContainer(self.store)
        self.toolbar = Toolbar()
        map(self.toolbar.add_new_view_button, self.view.tool_buttons[::-1])
        self.view.connect("new-view-added", lambda w, v: self.toolbar.add_new_view_button(v.button, len(self.view.tool_buttons)))
        self.panedcontainer = PanedContainer()
        self.preferences_dialog = PreferencesDialog()
        self.histogram = HistogramWidget()
        self.histogram.set_store(self.store)
        self.histogram.set_dates([self.day_iter.date])
        self.backward_button = DayButton(0)
        self.forward_button = DayButton(1, sensitive=False)
        self.searchbox = SearchBox
        # Widget placement
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        histogramhbox = gtk.HBox()
        hbox.pack_start(self.backward_button, False, False)
        hbox.pack_start(self.view, True, True, 6)
        hbox.pack_end(self.forward_button, False, False)
        hbox.set_border_width(4)
        vbox.pack_start(self.toolbar, False, False)
        self.panedcontainer.center_box.add(hbox)
        vbox.pack_start(self.panedcontainer, True, True, 2)
        histogramhbox.pack_end(self.histogram, True, True, 30)
        vbox.pack_end(histogramhbox, False, False)
        self.add(vbox)
        self.show_all()
        self.panedcontainer.informationcontainer.hide()
        self.panedcontainer.pinbox.hide()
        # Settings
        self.view.set_day(self.store.today)
        # Connections
        self.connect("destroy", self.quit)
        self.connect("delete-event", self.on_delete)
        self.backward_button.connect("clicked", self.previous)
        self.forward_button.connect("clicked", self.next)
        self.histogram.connect("date-changed", lambda w, date: self.set_date(date))
        self.view.connect("view-button-clicked", self.on_view_button_click)
        self.toolbar.throbber.connect("clicked", self.show_about_window)
        self.toolbar.goto_today_button.connect("clicked", lambda w: self.set_date(datetime.date.today()))
        self.toolbar.pin_button.connect("clicked", lambda w: self.panedcontainer.pinbox.show_all())
        self.store.connect("update", self.histogram.histogram.set_store)
        self.searchbox.connect("search", self._on_search)
        self.searchbox.connect("clear", self._on_search_clear)
        self.set_title_from_date(self.day_iter.date)
        def setup(*args):
            self.histogram.set_dates(self.active_dates)
            self.histogram.scroll_to_end()
            if AUTOLOAD:
                self.store.request_last_n_days_events(90)
            return False
        gobject.timeout_add_seconds(1, setup)
        self.histogram.scroll_to_end()
        # hide unused widgets
        self.searchbox.hide()
        # Window configuration
        self.set_icon_name("gnome-activity-journal")
        self.set_icon_list(
            *[gtk.gdk.pixbuf_new_from_file(get_icon_path(f)) for f in (
                "hicolor/16x16/apps/gnome-activity-journal.png",
                "hicolor/24x24/apps/gnome-activity-journal.png",
                "hicolor/32x32/apps/gnome-activity-journal.png",
                "hicolor/48x48/apps/gnome-activity-journal.png",
                "hicolor/256x256/apps/gnome-activity-journal.png")])
        gobject.idle_add(self.load_plugins)

    def load_plugins(self):
        self.plug_manager = PluginManager(CLIENT, STORE, self)
        self.preferences_dialog.notebook.show_all()
        self.toolbar.preference_button.connect("clicked", lambda *args: self.preferences_dialog.show())
        self.preferences_dialog.plug_tree.set_items(self.plug_manager)

        return False

    def set_visibility(self, val):
        if val: self.show()
        else: self.hide()

    def toggle_visibility(self):
        if self.get_property("visible"):
            self.hide()
            return False
        self.show()
        return True

    @property
    def active_dates(self):
        date = self.day_iter.date
        if self.view.page != 0: return [date]
        dates = []
        for i in range(self.view.mutliview.num_pages):
            dates.append(date + tdelta(-i))
        dates.sort()
        return dates

    def set_day(self, day):
        self.toolbar.do_throb()
        self.day_iter = day
        self.handle_button_sensitivity(day.date)
        self.view.set_day(day)
        self.histogram.set_dates(self.active_dates)
        # Set title
        self.set_title_from_date(day.date)

    def set_date(self, date):
        self.set_day(self.store[date])

    def next(self, *args):
        day = self.day_iter.next(self.store)
        self.set_day(day)

    def previous(self, *args):
        day = self.day_iter.previous(self.store)
        self.set_day(day)

    def handle_button_sensitivity(self, date):
        today = datetime.date.today()
        if date == today:
            return self.forward_button.set_sensitive(False)
        elif date == today + tdelta(-1):
            self.forward_button.set_leading(True)
        else:
            self.forward_button.set_leading(False)
        self.forward_button.set_sensitive(True)

    def on_view_button_click(self, w, button, i):
        print "Yay"
        for button in self.view.tool_buttons:
            button.set_sensitive(True)
        self.view.tool_buttons[i].set_sensitive(False)
        self.view.set_current_page(i)
        self.view.set_day(self.day_iter, page=i)
        self.histogram.set_dates(self.active_dates)
        self.set_title_from_date(self.day_iter.date)

    def show_about_window(self, *args):
        aboutwindow = AboutDialog()
        aboutwindow.set_transient_for(self)
        aboutwindow.run()
        aboutwindow.destroy()

    def _on_search(self, box, results):
        dates = []
        for obj in results:
            dates.append(datetime.date.fromtimestamp(int(obj.event.timestamp)/1000.0))
        self.histogram.histogram.set_highlighted(dates)

    def _on_search_clear(self, *args):
        self.histogram.histogram.clear_highlighted()

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

    def set_title_from_date(self, date):
        pages = self.view.mutliview.num_pages
        if self.view.page == 0:
            start_date = date + tdelta(-pages+1)
        else:
            start_date = date
        if date == datetime.date.today():
            end = _("Today")
            start = start_date.strftime("%A")
        elif date == datetime.date.today() + tdelta(-1):
            end = _("Yesterday")
            start = start_date.strftime("%A")
        elif date + tdelta(6) > datetime.date.today():
            end = date.strftime("%A")
            start = start_date.strftime("%A")
        else:
            start = start_date.strftime("%d %B")
            end = date.strftime("%d %B")
        if self.view.page != 0:
            self.set_title(end + " - Activity Journal")
        else:
            self.set_title(_("%s to %s") % (start, end) + " - " + _("Activity Journal"))

    def on_delete(self, w, event):
        x, y = self.get_size()
        settings["window_width"] = x
        settings["window_height"] = y

    def quit(self, *args):
        gtk.main_quit()

