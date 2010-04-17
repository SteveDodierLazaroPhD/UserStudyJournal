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

import time
import datetime
import gc

from widgets import *
from daywidgets import *
from eventgatherer import datelist
from config import settings


def get_seconds_remaining_in_day():
    return 86400 - ((time.time()-time.timezone-time.daylight*(60*60)) % 86400) + 4


class ActivityView(gtk.VBox):
    __gsignals__ = {
        # Sent when date is updated. Sends a start time in seconds, end time in seconds
        # and a bool that si true if we are in single day view
        "date-updated" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                          (gobject.TYPE_INT, gobject.TYPE_INT, gobject.TYPE_BOOLEAN)),
        }
    def __init__(self, cal):

        gtk.VBox.__init__(self)

        self.cal = cal

        self.days = {}

        self.daysbox = None
        self.daybox = None
        self.__first_run = True
        self.set_num_days(3)

        self._set_searchbox()
        self._set_today_timestamp()
        self._set_view_type()
        self._set_timeline()

        def new_day_updater():
            self.set_views()
            seconds = get_seconds_remaining_in_day()
            gobject.timeout_add_seconds(seconds, new_day_updater)
            return False
        new_day_updater()

    def set_num_days(self, dayrange):
        self.dayrange = dayrange
        self.cal.histogram.set_selected_range(dayrange)
        self.set_views()

    def _set_searchbox(self):
        self.searchbox = searchbox
        self.pack_start(self.searchbox, False, False)
        self.searchbox.connect("search", self._handle_search_results)
        self.searchbox.connect("clear", self._clear_search_results)

    def _clear_search_results(self, widget):
        self.cal.histogram.clear_highlighted()
        for item in ITEMS:
            item.highlight()

    def _handle_search_results(self, widget, results):
        datastore = self.cal.histogram.get_datastore()
        keys = []
        t = time.time()
        offset =time.mktime(time.gmtime(t)) - time.mktime(time.localtime(t))

        for r in results:
            timestamp = int(time.mktime(time.localtime(r[0]))) / 86400
            keys.append(offset + timestamp*86400)

        dates = []
        for i, (date, nitems) in enumerate(datastore):
            if int(date) in keys:
                dates.append(i)
        self.cal.histogram.set_highlighted(dates)
        for item in ITEMS:
            item.highlight()

    def _set_timeline(self):
        def selection_callback(widget, i):
            datastore = widget.get_datastore()
            if i < len(datastore):
                selection_date = datastore[i][0]
                end = selection_date  + 86399
                start = selection_date - (self.dayrange - 1) * 86400
                self.set_dayrange(start, end)
        datelist(90, self.cal.histogram.set_datastore)
        self.cal.histogram.connect("column_clicked", selection_callback)

    def _set_view_type(self, refresh=False):

        for w in self:
            if w != self.searchbox:
                self.remove(w)
        self.daysbox = gtk.HBox(True)
        self.daybox = SingleDayWidget()
        self.thumbbox = ThumbnailDayWidget()
        hbox  = gtk.HBox()
        hbox.pack_start(self.daybox, True, True, 3)
        hbox2  = gtk.HBox()
        hbox2.pack_start(self.thumbbox, True, True, 3)
        self.daybox.connect("unfocus-day", self._zoom_out_day)
        self.thumbbox.connect("unfocus-day", self._zoom_out_day)

        self.notebook = gtk.Notebook()
        self.notebook.set_show_tabs(False)
        self.notebook.set_show_border(False)

        self.notebook.append_page(self.daysbox, gtk.Label("Group View"))
        self.notebook.append_page(hbox, gtk.Label("Day View"))
        self.notebook.append_page(hbox2, gtk.Label("Thumbnail View"))

        self.pack_start(self.notebook, True, True, 0)
        if refresh:
            self.set_views()
        self.daysbox.show_all()

        def change_style(widget, style):
            rc_style = self.style
            #color = rc_style.bg[gtk.STATE_NORMAL]
            self.notebook.set_style(rc_style)

        self.notebook.connect("style-set", change_style)

    def jump(self, offset):
        self.start = self.start + offset

        if time.time() > self.start:
            model = self.cal.histogram.get_datastore()
            if len(model) < 1:
                return
            diff = self.start - model[0][0]
            self.cal.histogram.set_selected(diff / 86400)
            self.set_dayrange(self.start, self.end+offset)

    def set_dayrange(self, start, end):
        self.start = start
        self.end = end
        notebook_page = self.notebook.get_current_page()
        self.dayrange = int(int((end - start)) / 86400) + 1
        self.set_views()
        widget = self.daysbox.get_children()[self.dayrange -1]
        if notebook_page == 1:
            self.daybox.set_day(widget.day_start, widget.day_end)
        elif notebook_page == 2:
            self.thumbbox.set_day(widget.day_start, widget.day_end)
        if notebook_page in (1, 2):
            val = True
        else: val = False
        self.emit("date-updated", start, end, val)

    def _set_today_timestamp(self, dayinfocus=None):
        """
        Return the dayrange of seconds between the min_timestamp and max_timestamp
        """
        # For the local timezone
        if not dayinfocus:
            dayinfocus = int(time.mktime(time.strptime(
                time.strftime("%d %B %Y") , "%d %B %Y")))
        self.end = dayinfocus + 86399
        self.start = dayinfocus - (self.dayrange - 1) * 86400
        self.set_views()

    def _zoom_out_day(self, widget):
        offset = self._prezoom_position*86400
        #_t = (86400 - (time.time() % 86400)) + time.time() + time.timezone
        #while offset + self.end > _t - 2:
        #    offset -=86400
        self.jump(offset)
        self.notebook.set_current_page(0)
        self.cal.histogram.set_single_day(False)
        self.emit("date-updated", self.start, self.end, False)

    def _zoom_in_day(self, widget, page):
        i = self.dayrange - 1
        for w in self.daysbox:
            if w == widget: break
            i -= 1
        self._prezoom_position = i
        self.notebook.set_current_page(page)
        self.jump(i*-86400)
        self.cal.histogram.set_single_day(True)
        if page == 1:
            self.daybox.set_day(widget.day_start, widget.day_end)
        elif page == 2:
            self.thumbbox.set_day(widget.day_start, widget.day_end)


    def set_views(self):
        if not self.daysbox:
            return # nothing to do - TODO: should this be allowed to happen?

        new_days = []

        for i in xrange(self.dayrange):
            if not settings.get("view", "Journal") == "Journal":
                i = (self.dayrange - 1) - i
            ptime =  datetime.datetime.fromtimestamp(
                self.start + i*86400).strftime("%A, %d %B %Y")
            if not self.days.has_key(ptime):
                dayview = DayWidget(self.start + i*86400,
                    self.start + i*86400 + 86400)
                dayview.connect("focus-day", self._zoom_in_day)
                self.days[ptime] = dayview
            new_days.append(self.days[ptime])

        widgets = self.daysbox.get_children()

        diff = 0
        if len(widgets) > 0:
            first_day = widgets[0]
            diff = (new_days[0].day_start - first_day.day_start) / 86400

        old_days = self.daysbox.get_children()

        if abs(diff) >= self.dayrange or diff == 0:
            for w in self.daysbox:
                self.daysbox.remove(w)
            for day in new_days:
                self.daysbox.pack_start(day, True, True, 3)
                day.refresh()

        elif diff > 0:
            for i in xrange(len(new_days)):
                self.daysbox.pack_start(new_days[i], True, True, 3)
                new_days[i].refresh()

            for i in xrange(diff):
                self.daysbox.remove(old_days[i])
                old_days[i].unparent()

        elif diff < 0:
            old_days.reverse()
            new_days.reverse()
            for i in xrange(len(new_days)):
                self.daysbox.pack_start(new_days[i], True, True, 3)
                self.daysbox.reorder_child(new_days[i], 0)
                new_days[i].refresh()

            # SCROLL HERE to new_days[i]

            for i in xrange(abs(diff)):
                self.daysbox.remove(old_days[i])
                old_days[i].unparent()

        pinbox.get_events()
        for day in self.daysbox:
            day._init_pinbox()

        del new_days, old_days, diff
        gc.collect()
