# -.- coding: utf-8 -.-
#
# store.py
#
# Copyright © 2010 Randal Barlow
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
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import gobject
import gtk
import sys
import time
import threading
from zeitgeist.client import ZeitgeistClient, ZeitgeistDBusInterface
from zeitgeist.datamodel import Event, ResultType, Interpretation

import content_objects

CLIENT = ZeitgeistClient()
INTERFACE = ZeitgeistDBusInterface()
MAXEVENTS = 999999

#content_object_selector_function = (lambda x: None)
content_object_selector_function = content_objects.choose_content_object

tdelta = lambda x: datetime.timedelta(days=x)


def reduce_dates_by_timedelta(dates, delta):
    new_dates = []
    for date in dates:
        new_dates += [date + delta]
    return new_dates


class DoEmit(object):
    """
    Calls emit_update on the methods class
    """
    def __init__(self, signal):
        self.signal = signal

    def __call__(self, function):
        def wrapper(instance, *args, **kwargs):
            value = function(instance, *args, **kwargs)
            instance.emit(self.signal)
            return value
        return wrapper


class CachedAttribute(object):
    """
    runs the method once, finds the value, and replace the descriptor
    in the instance with the found value
    """
    def __init__(self, method, name=None):
        self.method = method
        self.attr_name = name or method.__name__

    def __get__(self, instance, cls):
        if instance is None:
            return self
        value = self.method(instance)
        setattr(instance, self.attr_name, value)
        return value


class ContentStruct(object):
    id = 0
    event = None

    @CachedAttribute
    def content_object(self):
        return content_object_selector_function(self.event)

    @CachedAttribute
    def event(self):
        events = INTERFACE.GetEvents([self.id])
        if events:
            return Event(events[0])

    def __init__(self, id, event=None, content_object=None, build=False):
        self.id = id
        if event:
            self.event = event
        if content_object:
            self.content_object = content_object
        if build:
            CLIENT.get_events([self.id], self.set_event)

    def set_event(self, value):
        if isinstance(value, tuple) or isinstance(value, list) and len(value):
            self.event = value[0]
        elif isinstance(value, Event):
            self.event = value
        else:
            self.event = ContentStruct.event
        gtk.gdk.threads_enter()
        content_object_selector_function(self.event)
        gtk.gdk.threads_leave()

    def do_build(self):
        CLIENT.get_events([self.id], self.set_event)


class Day(gobject.GObject):
    __gsignals__ = {
        "update" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
    }


    date = None
    start = 0
    end = 86400

    @property
    def time_range(self):
        return [self.start*1000, self.end*1000]

    @property
    def items(self):
        return self._items.values()

    @CachedAttribute
    def templates(self):
        return [Event.new_for_values()]

    def __init__(self, date):
        super(Day, self).__init__()
        self.date = date
        self._items = {}#id:ContentItem
        self.start = int(time.mktime(date.timetuple()))
        self.end = self.start+86399
        CLIENT.find_event_ids_for_templates(self.templates, self.set_ids, self.time_range, num_events=MAXEVENTS)
        CLIENT.install_monitor(self.time_range, self.templates, self.insert_events, self.remove_ids)

    def has_id(self, id_):
        return self._items.has_key(id_)

    def __getitem__(self, id_):
        return self._items[id_]

    def __len__(self):
        return len(self._items)

    @DoEmit("update")
    def set_ids(self, event_ids):
        for id_ in event_ids:
            self._items[id_] = ContentStruct(id_)

    @DoEmit("update")
    def remove_ids(self, time_range, ids):
        for id_ in ids:
            try:
                del self._items[id_]
            except KeyError:
                pass

    @DoEmit("update")
    def insert_events(self, time_range, events):
        for event in events:
            self._items[event.id] = ContentStruct(event.id, event)

    def next(self, store):
        date = self.date + datetime.timedelta(days=1)
        return store[date]

    def previous(self, store):
        date = self.date + datetime.timedelta(days=-1)
        return store[date]

    def filter(self, event_template=None, result_type=None):
        items = self.filter_event_template(event_template)
        items = self.filter_result_type(items, result_type)
        return items

    def filter_event_template(self, event_template):
        items = []
        if isinstance(event_template, Event):
            for obj in self._items.values():
                if obj.event.matches_template(event_template):
                    items.append(obj)
        elif event_template:
            for template in event_template:
                items += self.filter(template)
            items = list(set(items))
        return items

    def filter_result_type(self, items, result_type):
        if items and result_type is ResultType.MostRecentSubjects:
            item_dict = {}
            for item in items:
                subject_uri = item.event.subjects[0].uri
                item_dict[subject_uri] = item
            items = item_dict.values()
        return items

    def get_time_map(self):
        start = self.start
        results = {}
        for item in self.items:
            uri = item.event.subjects[0].uri
            if not uri in results:
                results[uri] = []
            if not item.event.interpretation == Interpretation.CLOSE_EVENT.uri:
                results[uri].append([item, 0])
            else:
                if not len(results[uri]) == 0:
                    #print "***", results[uri]
                    results[uri][len(results[uri])-1][1] = (int(item.event.timestamp)) -  int(results[uri][-1][0].event.timestamp)
                else:
                    tend = int(item.event.timestamp)
                    item.event.timestamp = str(start)
                    results[uri].append([item, tend - start])
        results = list(sorted(results.itervalues(), key=lambda r: \
                             r[0][0].event.timestamp))
        return results


class Store(gobject.GObject):
    __gsignals__ = {
        "update" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
    }

    @property
    def today(self):
        return self[datetime.date.today()]

    @property
    def days(self):
        dates = self.dates
        return [self._days[date] for date in dates]

    @property
    def dates(self):
        dates = self._days.keys()
        dates.sort()
        return dates

    def __init__(self):
        super(Store, self).__init__()
        self._days = {}
        self._day_connections = {}
        today = datetime.date.today()
        t = time.mktime(today.timetuple())
        for i in range(1,30*10):
            date = datetime.date.fromtimestamp(t)
            day = Day(date)
            self.add_day(date, day)
            t -= 86400

    @DoEmit("update")
    def add_day(self, key, day):
        self._days[key] = day
        self._day_connections[key] = day.connect("update", lambda *args: self.emit("update"))

    def __getitem__(self, key):
        if isinstance(key, datetime.date):
            # Return day from date
            try:
                return self._days[key]
            except KeyError:
                day = Day(key)
                self.add_day(key, day)
                return day
        elif isinstance(key, int):
            # Return event id
            for date, obj in self._days.iteritems():
                if obj.has_id(id):
                    return obj[id]
        raise KeyError("%s Not found" % key)

    def __len__(self):
        i = 0
        for item in self._days.itervalues():
            i+=len(item)
        return i

    def build_all(self, threaded=False):
        def _build():
            for day in self.days:
                for item in day.items:
                    item.do_build()
        if threaded:
            thread = threading.Thread(target=_build)
            thread.start()
        else: return _build


gobject.type_register(Day)
gobject.type_register(Store)

