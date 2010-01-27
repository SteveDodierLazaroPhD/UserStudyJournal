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


def get_dayevents(start, end, callback):
    def event_exists(uri):
        # TODO: Move this into Zeitgeist's datamodel.py
        return not uri.startswith("file://") or os.path.exists(
            urllib.unquote(str(uri[7:])))

    def handle_find_events(events):
        results = {}
        sort_results = {}
        for event in events:
            if event_exists(event.subjects[0].uri):
               
                if event.interpretation == Interpretation.VISIT_EVENT or \
                            event.interpretation == Interpretation.OPEN_EVENT:
                   
                    if not results.has_key(event.subjects[0].uri):
                        results[event.subjects[0].uri] = []
                        sort_results[event.subjects[0].uri] = int(event.timestamp)
                    r = [event, 1000]
                    results[event.subjects[0].uri].append(r)
                else:
                    if results.has_key(event.subjects[0].uri):
                        item = results[event.subjects[0].uri][len(results[event.subjects[0].uri])-1] 
                        if int(event.timestamp) > int(item[0].timestamp):
                            item[1] = int(event.timestamp) - int(item[0].timestamp)
                            results[event.subjects[0].uri][len(results[event.subjects[0].uri])-1] = item
                            
        sort_results = [(k, v) for v, k in sort_results.items()]
        sort_results.sort()
        final_results = []
        for v in sort_results:
            final_results.append(results[v[1]])
        
        callback(final_results)
    
    timerange = [start, end]
    event = Event()
    #event.interpretation = Interpretation.VISIT_EVENT
    CLIENT.find_events_for_templates([event], handle_find_events, timerange, num_events=50000, result_type=1)


