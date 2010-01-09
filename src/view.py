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
from widgets import *
from ui_utils import *
from daywidgets import *
from timelinewidget.calview import cal
from timelinewidget import rdate_z

class ActivityView(gtk.VBox):

    def __init__(self):

        gtk.VBox.__init__(self)

        self.days = {}

        self.dayrange = 3
        cal.scrollcal.set_dayrange(3)
        self.daysbox = None
        self.__first_run = True

        self._set_searchbox()
        self._set_today_timestamp()
        self._set_view_type()
        self._set_timeline()

        settings.connect("change-view", lambda w, x: self.set_view_type(True))
        settings.connect("toggle-grouping", lambda w: self.set_view_type(True))
        self.set_views()

    def _set_searchbox(self):
        pass
    
    def _set_timeline(self):
        
        
        def selection_callback(history, i):
            #print history, i
            if i < len(history):
                selection_date = history[i][0]
                end = selection_date + 86399
                start = selection_date - (self.dayrange -1)*86400
                self.set_dayrange(start, end)
                #if isinstance(selection_date, int): 
                    #selection_date = date.fromtimestamp(selection_date).strftime("%d/%B")
                #print "%d day %s has %s events\n" % (i,selection_date, history[i][1])
        
        def date_changed(*args, **kwargs):
            pass #print "Date Changed" # removed as it slows down the widget by poluting stdout
        
        rdate_z.datelist(90, cal.scrollcal.update_data)
        cal.scrollcal.connect_selection_callback(selection_callback)
        cal.scrollcal.connect("date-set", date_changed)

    def _set_view_type(self, refresh=False):

        for w in self:
            if w == self.searchbox:
                pass
            else:
                self.remove(w)

        if settings.get("view", "Journal") == "Journal":
            self.daysbox = gtk.HBox(True)
        else:
            self.daysbox = gtk.VBox()

        self.pack_start(self.daysbox, True, True, 6)
        if refresh:
            self.set_views()
        self.daysbox.show_all()

    def jump(self, offset):
        self.start = self.start+offset
        if time.time() > self.start:
            diff = self.start - cal.scrollcal.history[0][0]
            cal.scrollcal.set_selection(diff/86400)
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
            dayinfocus = int(time.mktime(time.strptime(time.strftime("%d %B %Y") , "%d %B %Y")))
        self.end = dayinfocus + 86399
        self.start = dayinfocus - (self.dayrange - 1) * 86400
        self.set_views()

    def set_views(self):
        if self.daysbox:
            for w in self.daysbox:
                self.daysbox.remove(w)
            for i in xrange(self.dayrange):
                if not settings.get("view", "Journal") == "Journal":
                    i = (self.dayrange - 1) - i
                ptime =  datetime.datetime.fromtimestamp(self.start + i*86400).strftime("%A, %d %B %Y")
                if not self.days.has_key(ptime):
                    dayview = DayWidget(self.start + i*86400, self.start + i*86400 + 86400)
                    self.days[ptime] = dayview
                self.daysbox.pack_start(self.days[ptime], True, True, 3)
                self.days[ptime].set_date_strings()
