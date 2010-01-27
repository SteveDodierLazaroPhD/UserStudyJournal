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
        for event in events:
            if event_exists(event.subjects[0].uri):
                if not results.has_key(event.subjects[0].uri):
                    results[event.subjects[0].uri] = []
                if event.interpretation == Interpretation.VISIT_EVENT or \
                            event.interpretation == Interpretation.OPEN_EVENT:
                    r = [event, 1000]
                    results[event.subjects[0].uri].append(r)
                else:
                    try:
                        item = results[event.subjects[0].uri][len(results[event.subjects[0].uri])-1] 
                        if int(event.timestamp) > int(item[0].timestamp):
                            item[1] = int(event.timestamp) - int(item[0].timestamp)
                            results[event.subjects[0].uri][len(results[event.subjects[0].uri])-1] = item
                    except Exception, ex:
                        print ex
                #results.append([event, random.randint(720000, 14200000), None])#random.randint(0, 72000000)])
                #results.append([event, random.randint(0, 14200000), None])#random.randint(0, 72000000)])
        
        for r in results.values():
            for event in r:
                print event[0].subjects[0].uri, event[1]


        callback(results)
    timerange = [start, end]
    event = Event()
    #event.interpretation = Interpretation.VISIT_EVENT
    CLIENT.find_events_for_templates([event], handle_find_events, timerange, num_events=50000, result_type=1)


