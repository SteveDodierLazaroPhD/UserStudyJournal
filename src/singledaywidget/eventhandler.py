'''
Created on Jan 22, 2010

@author: seif
'''
import time
import gtk
import random

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType, TimeRange

CLIENT = ZeitgeistClient()


def get_dayevents(start, end, callback):
    def handle_find_events(events):
        results = []
        for event in events:
            #results.append([event, random.randint(720000, 14200000), None])#random.randint(0, 72000000)])
            results.append([event, random.randint(0, 14200000), None])#random.randint(0, 72000000)])

        callback(results)
    timerange = [start, end]
    event = Event()
    event.interpretation = Interpretation.VISIT_EVENT
    CLIENT.find_events_for_templates([event], handle_find_events, timerange, num_events=50000, result_type=1)


