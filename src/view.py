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

import time
import datetime

from widgets import *
from daywidgets import *
from histogramwidget import histogramdata
from config import settings

class ActivityView(gtk.VBox):

    def __init__(self, cal):

        gtk.VBox.__init__(self)

        self.cal = cal

        self.days = {}

        self.daysbox = None
        self.__first_run = True
        self.set_num_days(3)

        self._set_searchbox()
        self._set_today_timestamp()
        self._set_view_type()
        self._set_timeline()

        self.set_views()

    def set_num_days(self, dayrange):
        self.dayrange = dayrange
        self.cal.histogram.set_dayrange(dayrange)
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
        datastore = self.cal.histogram.datastore
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
        def selection_callback(widget, datastore, i):
            if i < len(datastore):
                selection_date = datastore[i][0]
                end = selection_date  + 86399
                start = selection_date - (self.dayrange - 1) * 86400
                self.set_dayrange(start, end)

        histogramdata.datelist(90, self.cal.histogram.set_datastore)
        self.cal.histogram.add_selection_callback(selection_callback)

    def _set_view_type(self, refresh=False):

        for w in self:
            if w != self.searchbox:
                self.remove(w)

        if settings.get("view", "Journal") == "Journal":
            self.daysbox = gtk.HBox(True)
        else:
            self.daysbox = gtk.VBox()

        self.pack_start(self.daysbox, True, True, 0)
        if refresh:
            self.set_views()
        self.daysbox.show_all()

    def jump(self, offset):
        self.start = self.start + offset
        if time.time() > self.start:
            diff = self.start - self.cal.histogram.datastore[0][0]
            self.cal.histogram.set_selected(diff / 86400)
            self.set_dayrange(self.start, self.end+offset)

    def set_dayrange(self, start, end):
        self.start = start
        self.end = end
        self.dayrange = int(int((end - start)) / 86400) + 1
        self.set_views()

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
            for i in xrange(diff):
                self.daysbox.remove(old_days[i])
                old_days[i].unparent()
            i = diff
            for i in xrange(len(new_days)):
                self.daysbox.pack_start(new_days[i], True, True, 3)

        elif diff < 0:
            old_days.reverse()
            for i in xrange(abs(diff)):
                self.daysbox.remove(old_days[i])
                old_days[i].unparent()
            new_days.reverse()
            for i in xrange(len(new_days)):
                self.daysbox.pack_start(new_days[i], True, True, 3)
                self.daysbox.reorder_child(new_days[i], 0)
