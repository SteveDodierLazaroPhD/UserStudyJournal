# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
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
import dbus
import gobject
import gtk
import sys
import time
import threading
from zeitgeist.client import ZeitgeistClient, ZeitgeistDBusInterface
from zeitgeist.datamodel import Event, ResultType, Interpretation

import content_objects
import external

CLIENT = ZeitgeistClient()
INTERFACE = ZeitgeistDBusInterface()
MAXEVENTS = 999999


tdelta = lambda x: datetime.timedelta(days=x)


def get_related_events_for_uri(uri, callback):
    """
    :param uri: A uri for which to request related uris using zetigeist
    :param callback: this callback is called once the events are retrieved for
    the uris. It is called with a list of events.
    """
    def _event_request_handler(ids):
        events = []
        for id_ in ids:
            events.append(STORE.get_event_from_id(id_))
        callback(events)

    def _event_id_request_handler(uris):
        templates = []
        if len(uris) > 0:
            for i, uri in enumerate(uris):
                templates += [
                        Event.new_for_values(interpretation=Interpretation.VISIT_EVENT.uri, subject_uri=uri),
                        Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri, subject_uri=uri),
                        Event.new_for_values(interpretation=Interpretation.CREATE_EVENT.uri, subject_uri=uri),
                        Event.new_for_values(interpretation=Interpretation.OPEN_EVENT.uri, subject_uri=uri)
                    ]
            CLIENT.find_event_ids_for_templates(templates, _event_request_handler,
                                             [0, time.time()*1000], num_events=50000,
                                             result_type=ResultType.MostRecentSubjects)

    end = time.time() * 1000
    start = end - (86400*30*1000)
    CLIENT.find_related_uris_for_uris([uri], _event_id_request_handler)


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

    _content_object_built = False
    @CachedAttribute
    def content_object(self):
        self._content_object_built = True
        return content_objects.ContentObject.new_from_event(self.event)

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
        if isinstance(value, dbus.Array) or isinstance(value, list) or isinstance(value, tuple) and len(value):
            self.event = value[0]
        elif isinstance(value, Event):
            self.event = value
        else:
            self.event = ContentStruct.event
        self.build_struct()

    def build_struct(self):
        gtk.gdk.threads_enter()
        self._content_object_built = True
        self.content_object = content_objects.ContentObject.new_from_event(self.event)
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
        if external.HAMSTER:
            facts = external.HAMSTER.get_facts(self.start, self.end)
            for fact in facts:
                self.insert_events(None, fact.get_events())

    def has_id(self, id_):
        """
        Returns True if the this object contains an event with the given id
        """
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

    @DoEmit("update")
    def insert_event(self, event, overwrite=False):
        """
        Insert an event into the day object

        Emits a 'update' signal
        """
        return self._insert_event(event, overwrite)

    def _insert_event(self, event, overwrite=False):
        """
        Insert an event into the day object without emitting a 'update' signal
        """
        if not overwrite and self.has_id(event.id):
            self._items[event.id].event = event
            return False
        self._items[event.id] = ContentStruct(event.id, event)
        if overwrite:
            self._items[event.id]._content_object_built = True
            self._items[event.id].content_object = content_objects.ContentObject.new_from_event(event)
        return True

    def next(self, store=None):
        """
        Return the next day in the given store
        """
        if not store:
            store = STORE # Singleton
        date = self.date + datetime.timedelta(days=1)
        return store[date]

    def previous(self, store=None):
        """
        Return the previous day in the given store
        """
        if not store:
            store = STORE # Singleton
        date = self.date + datetime.timedelta(days=-1)
        return store[date]

    def filter(self, event_template=None, result_type=None):
        if event_template:
            items = self.filter_event_template(event_template)
            items = self.filter_result_type(items, result_type)
        elif result_type:
            items = self.filter_result_type(self._items.values(), result_type)
        else:
            items = self._items.values()
        items.sort(key=lambda obj: int(obj.event.timestamp))
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

    def do_build(self):
        CLIENT.get_events(self._items.keys(), self.__set_events_by_id)

    def __set_events_by_id(self, events):
        for event in events:
            self._items[event.id].event = event
            self._items[event.id].build_struct()


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
        self.run_build_thread = False
        self._days = {}
        self._day_connections = {}
        today = datetime.date.today()
        t = time.mktime(today.timetuple())
        for i in range(1,30*10):
            date = datetime.date.fromtimestamp(t)
            day = Day(date)
            self.add_day(date, day)
            t -= 86400

        content_objects.AbstractContentObject.connect_to_manager("add", self.add_content_object_with_new_type)
        content_objects.AbstractContentObject.connect_to_manager("remove", self.remove_content_objects_with_type)

    def add_content_object_with_new_type(self, obj):
        print "OK"
        for day in self.days:
            for instance in day.items:
                if instance._content_object_built:
                    cls = content_objects.ContentObject.find_best_type_from_event(instance.event)
                    if not isinstance(instance.content_object, cls) and instance.content_object:
                        print "replacing %s with %s" % (str(type(instance.content_object)), cls)
                        del instance.content_object
                        instance.content_object = cls.create(instance.event)
            day.emit("update")

    def remove_content_objects_with_type(self, obj):
        for day in self.days:
            for instance in day.items:
                if instance._content_object_built:
                    if isinstance(instance.content_object, obj):
                        instance.content_object = content_objects.ContentObject.new_from_event(instance.event)
            day.emit("update")

    @DoEmit("update")
    def add_day(self, key, day):
        self._days[key] = day
        self._day_connections[key] = day.connect("update", lambda *args: self.emit("update"))

    def get_event_from_id(self, id_):
        struct = ContentStruct(id_)
        date = datetime.date.fromtimestamp(int(struct.event.timestamp)/1000)
        if date in self.dates:
            nstruct = self[date][id_]
            nstruct.event = struct.event
            del struct
            return nstruct
        else:
            day = Day(date)
            self.add_day(date, day)
            day._items[id_] = struct
            return struct

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

    def request_last_n_days_events(self, n=90, func=None):
        """
        Find the events for 'n' days and packs them into the store

        Optionally calls func upon completion
        """
        event_templates = (
            Event.new_for_values(interpretation=Interpretation.VISIT_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.CREATE_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.OPEN_EVENT.uri),
        )
        def callback(events):
            def _thread_fn(events):
                map(self.add_event, events)
                if func:
                    func()
                return False
            thread = threading.Thread(target=_thread_fn, args=(events,))
            thread.start()

        end = time.time() - 3*86400
        start = end - n*86400
        if n >= 60:
            inc = (end - start)/(n/30)
            for i in range(n/30):
                a = end - (inc*(i+1)) + 1
                b = end - (inc*(i))
                CLIENT.find_events_for_templates(
                    event_templates, callback, [a*1000, b*1000], num_events=50000)
        else:
            CLIENT.find_events_for_templates(
                event_templates, callback, [start*1000, end*1000], num_events=50000)
        return False

    def add_event(self, event, overwrite=True, idle=True):

        date = datetime.date.fromtimestamp(int(event.timestamp)/1000)
        day = self[date]
        if idle:
            def _idle_add(event, overwrite):
                # Use _insert_event to avoid update signals
                day._insert_event(event, overwrite)
                return False
            gobject.idle_add(_idle_add, event, overwrite)
        else:
            day.insert_event(event, overwrite)



gobject.type_register(Day)
gobject.type_register(Store)

# Init
STORE = Store()
external.STORE = STORE
