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
    ResultType, TimeRange

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
 
    def search_tracker(self, text):
        # Unmarshal the dbus objects in the response
        return [str(x[0]) for x in
            self.iface.SparqlQuery(QUERY_BY_TEXT % (text))]

    def search_zeitgeist(self, uris, interpretation, search_callback):
        
        def _handle_find_events(events):
            results = []
            for event in events:
                results.append(
                    (int(event.timestamp) / 1000, event.subjects[0].uri))
            search_callback(results)
        
        events = []
        for uri in uris:
            subject = Subject.new_for_values(uri=uri)
            if interpretation:
                subject.interpretation = interpretation
            event = Event.new_for_values(subjects=[subject])
            events.append(event)
        self.zg.find_events_for_templates(events, _handle_find_events,
            TimeRange.until_now(), result_type=ResultType.MostRecentEvents)
    
    def search(self, text, interpretation, search_callback):
        uris = self.search_tracker(text)
        if len(uris) > 0:
            self.search_zeitgeist(uris, interpretation, search_callback)

tracker = TrackerBackend()
