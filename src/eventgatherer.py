# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Seif Lotfy <seif@lotfy.com>
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
from datetime import timedelta, datetime
import gtk
import random
import os
import urllib
from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType, TimeRange

CLIENT = ZeitgeistClient()

event_templates = (
    Event.new_for_values(interpretation=Interpretation.VISIT_EVENT.uri),
    Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri),
    Event.new_for_values(interpretation=Interpretation.CREATE_EVENT.uri),
    Event.new_for_values(interpretation=Interpretation.OPEN_EVENT.uri),
    Event.new_for_values(interpretation=Interpretation.CLOSE_EVENT.uri),
)

EVENTS = {}

def get_dayevents(start, end, callback):

    def event_exists(uri):
        # TODO: Move this into Zeitgeist's datamodel.py
        if uri.startswith("trash://"):
            return False
        return not uri.startswith("file://") or os.path.exists(
            urllib.unquote(str(uri[7:])))

    def handle_find_events(events):
        results = {}
        for event in events:
            uri = event.subjects[0].uri
            if event_exists(uri):
                if not event.subjects[0].uri in results:
                    results[uri] = []
                if not event.interpretation == Interpretation.CLOSE_EVENT.uri:
                    results[uri].append([event, 0])
                else:
                    if not len(results[uri]) == 0:
                        #print "***", results[uri]
                        results[uri][len(results[uri])-1][1] = (int(event.timestamp)) -  int(results[uri][-1][0].timestamp)
                    else:
                        tend = int(event.timestamp)
                        event.timestamp = str(start)
                        results[uri].append([event, tend - start])
        events = list(sorted(results.itervalues(), key=lambda r: \
            r[0][0].timestamp))
        EVENTS[start+end] = events
        callback(events)
    
    if not EVENTS.has_key(start+end):
        CLIENT.find_events_for_templates(event_templates, handle_find_events,
                                         [start, end], num_events=50000,
                                         result_type=ResultType.LeastRecentEvents)
    else:
        callback(EVENTS[start+end]) 

def datelist(n, callback):
    if n == -1:
        n = int(time.time()/86400)
    today = int(time.mktime(time.strptime(time.strftime("%d %B %Y"),
        "%d %B %Y")))
    today = today - n*86400

    x = []

    def _handle_find_events(ids):
        x.append((today+len(x)*86400, len(ids)))
        if len(x) == n+1:
            callback(x)

    def get_ids(start, end):
        CLIENT.find_event_ids_for_templates(event_templates,
            _handle_find_events, [start * 1000, end * 1000],
            num_events=50000, result_type=0)

    for i in xrange(n+1):
        get_ids(today+i*86400, today+i*86400+86399)
