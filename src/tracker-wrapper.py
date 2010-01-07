# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
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

import dbus
import os
import gtk
import time

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType

TRACKER = 'org.freedesktop.Tracker1'
TRACKER_OBJ = '/org/freedesktop/Tracker1/Resources'
TRACKER_IFACE = 'org.freedesktop.Tracker1.Resources'
QUERY_BY_TEXT = """
    SELECT ?u WHERE {
        ?u a nie:InformationElement ;
        fts:match "%s*" .
    } """

try:
    CLIENT = ZeitgeistClient()
except RuntimeError, e:
    print "Unable to connect to Zeitgeist: %s" % e
    CLIENT = None

class TrackerBackend:

    def __init__(self):
        bus = dbus.SessionBus ()
        self.tracker = bus.get_object(TRACKER, TRACKER_OBJ)
        self.iface = dbus.Interface(self.tracker, TRACKER_IFACE)
        self.zg = CLIENT

    def search(self, text):
        # Unmarshal the dbus objects in the response
        return map(lambda x: str(e[0]),
            self.iface.SparqlQuery(QUERY_BY_TEXT % text))

    def search_zeitgeist(self, uris):
        events = []
        for uri in uris:
            subject = Subject.new_for_values(uri=uri)
            event = Event.new_for_values(subjects=[subject])
            events.append(event)
        self.zg.find_event_ids_for_templates(events, self._handle_find_events,
            TimeRange.until_now(), num_events=50000,
            result_type=ResultType.MostPopularSubjects)

    def _handle_find_events(self, ids):
        self.zg.get_events(ids, self._handle_get_events)

    def _handle_get_events(self, events):
        for event in events:
            print event.timestamp, event.subjects[0].uri

"""
Example usage:

    tracker = TrackerBackend()
    uris = tracker.search("adam")
    tracker.search_zeitgeist(uris)
"""
