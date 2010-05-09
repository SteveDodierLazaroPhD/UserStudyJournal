# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
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

import dbus
import os
import gtk
import random
import time
from content_objects import ContentObject
from store import STORE

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType, TimeRange

try:
    CLIENT = ZeitgeistClient()
except RuntimeError, e:
    print "Unable to connect to Zeitgeist: %s" % e
    CLIENT = None


TRACKER_NAME = 'org.freedesktop.Tracker1'
TRACKER_OBJ = '/org/freedesktop/Tracker1/Resources'
TRACKER_IFACE = 'org.freedesktop.Tracker1.Resources'

class StandardQueries:
    QUERY_BY_TEXT = """
        SELECT ?u WHERE {
        ?u a nie:InformationElement ;
            fts:match "%s*" .
        } """ # % text

    GET_TAGS_FOR_FILE = """
        SELECT ?tags ?labels
        WHERE {
          ?f nie:isStoredAs ?as ;
             nao:hasTag ?tags .
          ?as nie:url '%s' .
          ?tags a nao:Tag ;
             nao:prefLabel ?labels .
        } ORDER BY ASC(?labels)""" # % some URI

    ADD_EXISTING_TAG = """
        INSERT {
          ?unknown nao:hasTag ?id
        } WHERE {
          ?unknown nie:isStoredAs ?as .
          ?as nie:url '%s' .
          ?id nao:prefLabel '%s'
        }""" # % (uri, label)

    GET_FILES_WITH_TAGS = """
    """

    GET_TAGS_WITH_LABEL = """
        SELECT ?tag
        WHERE {
          ?tag a nao:Tag .
          ?tag nao:prefLabel '%s' .
        }
    """ #% label

    ADD_NEW_TAG_TO_FILE = """
        INSERT {
          _:tag a nao:Tag ;
                nao:prefLabel '%s' .
          ?unknown nao:hasTag _:tag
        } WHERE {
          ?unknown nie:isStoredAs ?as .
          ?as nie:url '%s'
        }
    """ # % (label, uri)


class TrackerBackend:

    def __init__(self):
        bus = dbus.SessionBus ()
        self.tracker = bus.get_object(TRACKER_NAME, TRACKER_OBJ)
        self.iface = dbus.Interface(self.tracker, TRACKER_IFACE)
        self.zg = CLIENT

    def add_tag_to_uri(self, label, uri):
        result = list(self.iface.SparqlQuery(StandardQueries.GET_TAGS_WITH_LABEL % label))
        if result:
            self.iface.SparqlUpdate(StandardQueries.ADD_EXISTING_TAG % (uri, label))
        else:
            self.iface.SparqlUpdate(StandardQueries.ADD_NEW_TAG_TO_FILE % (label, uri))

    def get_tags_for_uri(self, uri):
        tags = [x for x in
            self.iface.SparqlQuery(StandardQueries.GET_TAGS_FOR_FILE % (uri))]
        tag_names = [x[1] for x in tags]
        return tag_names

    def get_tag_dict_for_uri(self, uri):
        tag_dict = {}
        try:
            tags = [x for x in
                self.iface.SparqlQuery(StandardQueries.GET_TAGS_FOR_FILE % (uri))]
            for tag in tags:
                name = str(tag[1])
                urn = tag[0]
                tag_dict[name] = random.randint(1, 100)
            return tag_dict
        except dbus.exceptions.DBusException as e:
            print "TAG SEARCH FAILURE", e
            return tag_dict

    def search_tracker(self, text):
        # Unmarshal the dbus objects in the response
        return [str(x[0]) for x in
            self.iface.SparqlQuery(StandardQueries.QUERY_BY_TEXT % text)]

    def search_zeitgeist(self, uris, interpretation, search_callback, use_objs=True):

        def _handle_find_events(events):
            if not use_objs:
                search_callback(events)
            else:
                map(STORE.add_event, events)
                objs = map(lambda e:STORE[e.id], events)
                search_callback(objs)
        events = []
        for uri in uris:
            subject = Subject.new_for_values(uri=uri)
            if interpretation:
                subject.interpretation = interpretation
            event = Event.new_for_values(subjects=[subject])
            events.append(event)
        self.zg.find_events_for_templates(events, _handle_find_events,
            TimeRange.until_now(), num_events=50000, result_type=0)

    def search(self, text, interpretation, search_callback):
        uris = list(set(self.search_tracker(text)))
        #if len(uris) > 200:
        if len(uris) > 0:
            self.search_zeitgeist(uris, interpretation, search_callback)


TRACKER = TrackerBackend()
