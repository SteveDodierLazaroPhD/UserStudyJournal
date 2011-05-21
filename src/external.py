# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
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

import datetime
import dbus
import os
import gtk
import random
import time

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, TimeRange, ResultType, \
    Interpretation, Manifestation

__all__ = ['CLIENT', 'CLIENT_VERSION', 'TELEPATHY', 'HAMSTER', 'FTS']

# Zeitgeist

try:
    CLIENT = ZeitgeistClient()
except RuntimeError, e:
    print "%s: %s" % (_("ERROR"), _("Unable to connect to Zeitgeist:"))
    print "%s" % e
    CLIENT = CLIENT_VERSION = None
else:
    CLIENT_VERSION = CLIENT.get_version()

STORE = None

try:
    BUS = dbus.SessionBus()
except Exception:
    BUS = None

# Telepathy

TELEPATHY = None

# Hamster

HAMSTER_PATH = "/org/gnome/Hamster"
HAMSTER_URI = "org.gnome.Hamster"

class Hamster(object):
    class HamsterEvent(Event):
        def _HAMSTER_ID_COUNTER():
            i = 1
            while True:
                i -= 1
                yield i
        HAMSTER_ID_COUNTER = _HAMSTER_ID_COUNTER()

        def __init__(self, *args, **kwargs):
            Event.__init__(self, *args, **kwargs)
            self._id = self.HAMSTER_ID_COUNTER.next()

        @property
        def id(self):
            return self._id

    class Fact(object):
        def __init__(self, dictionary):
            self._dictionary = dictionary

        def __getattr__(self, key):
            if self._dictionary.has_key(key):
                return self._dictionary[key]
            return object.__getattribute__(self, key)

        def _make_event(self, tval, interp):
            return Hamster.HamsterEvent.new_for_values(
                interpretation = interp,
                manifestation = Manifestation.USER_ACTIVITY.uri,
                actor = "applications://hamster-standalone.desktop",
                timestamp = tval*1000,
                subject_interpretation = Interpretation.TODO.uri,
                subject_manifestation = Manifestation.SCHEDULED_ACTIVITY.uri,
                subject_text = str(self.name) + ": " + str(self.description),
                subject_uri = ("hamster://%d" % int(self.id)),
            )

        def get_events(self):
            events = []
            events.append(self._make_event(int(self.start_time+time.timezone),
                Interpretation.ACCESS_EVENT.uri))
            if self.end_time:
                events.append(self._make_event(int(self.end_time+time.timezone),
                    Interpretation.LEAVE_EVENT.uri))
            return events

    def __init__(self):
        self.hamster = BUS.get_object(HAMSTER_URI, HAMSTER_PATH)
        self.iface = dbus.Interface(self.hamster, dbus_interface=HAMSTER_URI)

    def get_facts(self, start=1, end=86400, date=None):
        if date:
            start = time.mktime(date.timetuple()) - time.timezone
            end = start+86399
        start -= 86400
        end -= 86400
        return map(self.Fact, self.iface.GetFacts(start, end))

try:
    HAMSTER = Hamster()
except Exception:
    HAMSTER = None

class ZeitgeistFTS(object):
    result_type_relevancy = 100
    def __init__(self):
        self._fts = BUS.get_object('org.gnome.zeitgeist.Engine',
            '/org/gnome/zeitgeist/index/activity')
        self.fts = dbus.Interface(self._fts, 'org.gnome.zeitgeist.Index')

    def search(self, text, templates=None):
        results, count = self.fts.Search(text,  TimeRange.always(),
            templates if templates else [] , 0, 10, self.result_type_relevancy)
        return map(Event, results)

try:
    FTS = ZeitgeistFTS()
except Exception:
    FTS = None
