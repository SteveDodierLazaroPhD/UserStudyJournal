'''
Created on Jan 4, 2010

@author: seif
'''
import gtk
import time, datetime
import gobject
import pango

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation

from ui_utils import *
from widgets import *

try:
    CLIENT = ZeitgeistClient()
except RuntimeError, e:
    print "Unable to connect to Zeitgeist: %s" % e
    CLIENT = None


class DayWidget(gtk.EventBox):
    def __init__(self, start, end):
        gtk.EventBox.__init__(self)
        hour = 60*60
        self.day_start = start
        self.day_end = end
        self.week_day_string = datetime.datetime.fromtimestamp(self.day_start).strftime("%A")
        self.date_string = datetime.datetime.fromtimestamp(self.day_start).strftime("%d %B %Y")
        
        self.morning = {
                        "start": self.day_start,
                        "end": self.day_start + 12*hour -1
                        }
        self.afternoon = {
                          "start": self.day_start + 12*hour,
                          "end": self.day_start + 18*hour-1
                          }
        self.evening = {
                        "start": self.day_start + 18*hour,
                        "end": self.day_end
                        }
        
        self.day_split = {
                          "Morning":  self.morning,
                          "Afternoon": self.afternoon,
                          "Evening": self.evening
                          }
        
        self.day_part_widgets = {
                                      "Morning":  None,
                                      "Afternoon": None,
                                      "Evening": None
                                      }
        
        self.part_order = ["Morning", "Afternoon", "Evening"]
        
        self.__init_widgets()
        self.__init_events()
        
    def __init_widgets(self):
        tm = gtk.IconView()
        tm.show_all()
        style = tm.get_style().copy()
        
        self.vbox = gtk.VBox()
        evbox = gtk.EventBox()
        evbox.add(self.vbox)
        
        style = evbox.get_style().copy()
        evbox.modify_bg(gtk.STATE_NORMAL, style.bg[gtk.STATE_SELECTED])
        
        self.add(evbox)
        
        label = gtk.Label()
        if time.time() < self.day_end and time.time() > self.day_start:
            self.week_day_string = "Today"
        elif time.time() - 86400 < self.day_end and time.time() - 86400> self.day_start:
            self.week_day_string = "Yesterday"
        label.set_markup("<span size='large' color='white'><b>"+self.week_day_string +"</b></span>")
        label.set_alignment(0.5,0.5)
        self.vbox.pack_start(label, False, False)
        label.modify_bg(gtk.STATE_SELECTED, style.bg[gtk.STATE_SELECTED])
        
        label = gtk.Label()
        label.set_markup("<span size='small' color='grey'>"+self.date_string +"</span>")
        label.set_alignment(0.5,0.5)
        self.vbox.pack_start(label, False, False)
        label.modify_bg(gtk.STATE_SELECTED, style.bg[gtk.STATE_SELECTED])

        
        self.view = gtk.VBox()
        scroll = gtk.ScrolledWindow()
        
        evbox = gtk.EventBox()
        evbox.add(self.view)
        
        evbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.add_with_viewport(evbox)
        self.vbox.pack_start(scroll)
        self.show_all()
        
    def __init_events(self):
        for w in self.view:
            self.view.remove(w)
        keys = self.day_split.keys()
        keys.sort()
        for key in self.part_order:
            part = DayPartWidget(key, self.day_split[key]["start"], self.day_split[key]["end"])
            self.view.pack_start(part, False, False)
            part.init_events()

class DayPartWidget(gtk.VBox):
    def __init__(self, part, start, end):
        gtk.VBox.__init__(self)
        self.part = part
        self.start = start
        self.end = end
        self.label = gtk.Label()
        self.label.set_markup("<span color='darkgrey'><b> "+part+"</b></span>")
        self.label.set_alignment(0.01, 0.5)
        self.pack_start(self.label, False, False, 12)
        self.view = gtk.VBox()
        self.pack_start(self.view)
        self.zg = CLIENT
        self.show_all()
        
    def init_events(self):
        event = Event()
        event.set_interpretation(Interpretation.VISIT_EVENT.uri)        
        event2 = Event()
        event2.set_interpretation(Interpretation.MODIFY_EVENT.uri)
        self.zg.find_event_ids_for_templates([event,event2], self._handle_find_events, 
                                             [self.start*1000, self.end*1000], num_events=50000, result_type=3)
        
    def _handle_find_events(self, ids):
        if len(ids) > 0:
            self.zg.get_events(ids, self._handle_get_events)
        else:
            self.hide_all()
    
    def _handle_get_events(self, events):
        
        def exists(uri):
            return not uri.startswith("file://") or os.path.exists(urllib.unquote(str(uri[7:])))
        
        self.categories = {}
        
        for event in events:
            subject = event.subjects[0]
            if exists(subject.uri):
                if not self.categories.has_key(subject.interpretation):
                    self.categories[subject.interpretation] = []
                self.categories[subject.interpretation].append(event)
        keys = self.categories.keys()
        keys.sort()
        
        for key in keys:
            events = self.categories[key]
            box = CategoryBox(key, events)
            self.view.pack_start(box)
        for w in self.view:
            print w

class CategoryBox(gtk.VBox):
    def __init__(self, category, events):
        gtk.VBox.__init__(self)
        self.btn = CategoryButton(category, len(events))
        self.btn.connect("toggle", self.toggle)
        self.pack_start(self.btn, False, False)
        self.view = gtk.VBox(True)
        for event in events:
            item = Item(event)
            self.view.pack_start(item)
        hbox = gtk.HBox()
        self.label = gtk.Label("    ")
        hbox.pack_start(self.label, False, False)
        hbox.pack_start(self.view)
        self.pack_start(hbox)
        self.show_all()
        self.view.hide_all()
        self.label.hide_all()
        
        if len(events) == 1:
            self.view.show_all()
            self.btn.hide_all()
    
    def toggle(self, view, bool):
        if bool:
            self.view.show_all()
            self.label.show_all()
        else:
            self.view.hide_all()
            self.label.hide_all()