import dbus
import os
import gtk
import time 

TRACKER = 'org.freedesktop.Tracker1'
TRACKER_OBJ = '/org/freedesktop/Tracker1/Resources'
TRACKER_IFACE = 'org.freedesktop.Tracker1.Resources'
QUERY_BY_TEXT = """
SELECT ?u WHERE {
 ?u a nie:InformationElement ;
    fts:match "%s*" .
}
"""

t = None

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation

try:
    CLIENT = ZeitgeistClient()
except RuntimeError, e:
    print "Unable to connect to Zeitgeist: %s" % e
    CLIENT = None

class TrackerBackend:

    def __init__ (self):
        bus = dbus.SessionBus ()
        self.tracker = bus.get_object (TRACKER, TRACKER_OBJ)
        self.iface = dbus.Interface (self.tracker, TRACKER_IFACE)
        self.zg = CLIENT

    def search (self, text):
        """
        Remember to unmarshal the dbus objects in the response
        """
        uris = [str (e[0]) for e in self.iface.SparqlQuery (QUERY_BY_TEXT % (text)) ]
        return uris

    def search_zeitgeist(self, uris):
        events = []
        for uri in uris:
            subject = Subject()
            subject.set_uri(uri)
            print uri
            event = Event()
            event.set_subjects([subject])
            events.append(event)
        self.zg.find_event_ids_for_templates(events, self._handle_find_events, [0, time.time()*1000], num_events=50000, result_type=4)

        
    def _handle_find_events(self, ids):
        self.zg.get_events(ids, self._handle_get_events)
    
    def _handle_get_events(self, events):
        print "-----------------"
        for event in events:
            print event.timestamp, event.subjects[0].uri
            
if __name__ == "__main__" :
    tracker = TrackerBackend()
    t = time.time()
    print "Tracker search: \n ----------------"
    uris = tracker.search ("adam")
    tracker.search_zeitgeist(uris) 
    gtk.main()