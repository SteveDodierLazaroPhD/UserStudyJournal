'''
Created on Jan 22, 2010

@author: seif
'''
import time
import gtk
import random
import os
import urllib
from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType, TimeRange

CLIENT = ZeitgeistClient()


'''
def get_dayevents_test(start, end, callback):
    t = int(time.time())/86400
    t = t*86400
    t= t*1000
    
    
    results = []

    e = Event()
    e.timestamp = t
    s = Subject()
    s.uri = "file:///home/lalala"
    e = e.set_subjects([s])
    results.append([e, 5000])
    
    t =  t + (60 * 30 * 1000)
    e = Event()
    e.timestamp = t
    s = Subject()
    s.uri = "file:///home/lalala"
    e = e.set_subjects([s])
    results.append([e, 5000])
    
    t =  t + (60 * 30 * 1000)
    e = Event()
    e.timestamp = t
    print e.timestamp
    s = Subject()
    s.uri = "file:///home/lalala"
    e = e.set_subjects([s])
    results.append([e, 5000])
    
    callback([[results])
'''

def get_dayevents(start, end, callback):
    def event_exists(uri):
        # TODO: Move this into Zeitgeist's datamodel.py
        return not uri.startswith("file://") or os.path.exists(
            urllib.unquote(str(uri[7:])))

    def handle_find_events(events):
        results = {}
        sort_results = {}
        checkpoint = []
        for event in events:
            
            
            
            if event_exists(event.subjects[0].uri):

                if event.interpretation == Interpretation.VISIT_EVENT or \
                            event.interpretation == Interpretation.OPEN_EVENT or \
                            event.interpretation == Interpretation.MODIFY_EVENT:
                    
                    t = event.subjects[0].uri + event.timestamp
                    if not t in checkpoint:
                        checkpoint.append(t)
                        if not results.has_key(event.subjects[0].uri):
                            results[event.subjects[0].uri] = []
                            sort_results[event.subjects[0].uri] = int(event.timestamp)
                        r = [event, 120000]
                        results[event.subjects[0].uri].append(r)
                
                            
        sort_results = [(k, v) for v, k in sort_results.items()]
        sort_results.sort()
        final_results = []
        for v in sort_results:
            final_results.append(results[v[1]])
        callback(final_results)

    timerange = [start, end]
    event = Event()
    CLIENT.find_events_for_templates([event], handle_find_events, timerange, num_events=50000, result_type=1)


