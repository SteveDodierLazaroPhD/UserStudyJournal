#!/usr/bin/env python
#coding:utf-8
# Author:
# Purpose: 

iszeitgeist = True

from datetime import timedelta, datetime
import time
from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType

CLIENT = ZeitgeistClient()

def datelist(n, callback):
    today = int(time.time())/86400
    today = today*86400 - n*86400
    
    x = []
    
    def _handle_find_events(ids):
        if len(ids) > 100:
            count = 101
        else:
            count = len(ids)
        x.append((today+len(x)*86400, count))
        if len(x) == n+1:
            callback(x)
    
    def get_ids(start, end):
        event = Event()
        event.set_interpretation(Interpretation.VISIT_EVENT.uri)
        event2 = Event()
        event2.set_interpretation(Interpretation.MODIFY_EVENT.uri)
        
        event_templates = [event, event2]
        CLIENT.find_event_ids_for_templates(event_templates,
            _handle_find_events, [start * 1000, end * 1000],
            num_events=50000, result_type=0)
    
    for i in xrange(n+1):
       get_ids(today+i*86400, today+i*86400+86399)
