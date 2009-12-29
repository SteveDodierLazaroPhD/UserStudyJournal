'''
Created on Nov 28, 2009

@author: seif
'''
import gtk
import pango
import gobject
import time
import datetime
from contextview import WindowView
from widgets import *
from ui_utils import *
from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation

try:
    CLIENT = ZeitgeistClient()
except RuntimeError, e:
    print "Unable to connect to Zeitgeist, won't send events. Reason: '%s'" %e
    CLIENT = None

CATEGORY_FILTER= {}
for k in SUPPORTED_SOURCES.keys():
            CATEGORY_FILTER[k] = True


class Portal(gtk.Window):
    '''
    classdocs
    '''

    def __init__(self, model):
        '''
        Constructor
        '''
        gtk.Window.__init__(self)
        self.connect("destroy", self.quit)
        self.set_size_request(800, 360)
        self.model = model
        self.settingswindow = None
        
        self.vbox = gtk.VBox()
        self.add(self.vbox)
        
        self.__init_widgets()
        self.__init_toolbar()
        
        #self.vbox.pack_start(self.menu, False, False)
        self.vbox.pack_start(self.toolbar, False, False)
        self.vbox.pack_start(self.notebook, True, True)
        self.vbox.pack_start(self.statusbar, False, False)
        
        self.show_all()
        self.notebook.activityview.optionsbar.hide_all()
        
    
    def destroy_settings(self, w):
        self.settingswindow = None
        
    def __init_widgets(self):
        self.notebook = Notebook()
        self.statusbar = gtk.Statusbar()
        
    def __init_toolbar(self):
        self.toolbar = gtk.HBox()
        
        toolbar = gtk.Toolbar()
        self.toolbar.pack_start(toolbar)
        
        toolbar2 = gtk.Toolbar()
        self.toolbar.pack_end(toolbar2, False, False)
        
        self.backbtn = gtk.ToolButton("gtk-go-back")
        self.todaybtn = gtk.ToolButton("gtk-home")
        self.fwdbtn = gtk.ToolButton("gtk-go-forward")
        self.optbtn = gtk.ToolItem()
        btn = gtk.ToggleButton()
        btn.set_relief(gtk.RELIEF_NONE)
        btn.add(gtk.Label("Options"))
        self.optbtn.add(btn)
        self.prefbtn = gtk.ToolButton("gtk-preferences")
        #self.propbtn = gtk.ToolButton("gtk-properties")
        
        self.todaybtn.connect("clicked", lambda w: self.notebook.activityview._set_today_timestamp())
        self.backbtn.connect("clicked", lambda w: self.notebook.activityview.jump(-86400))
        self.fwdbtn.connect("clicked", lambda w: self.notebook.activityview.jump(86400))
        self.prefbtn.connect("clicked", self.toggle_preferences)
        btn.connect("toggled", self.notebook.activityview.toggle_optionsbar)
        
        toolbar.add(self.backbtn)
        toolbar.add(self.todaybtn)
        toolbar.add(self.fwdbtn)
        toolbar.add(gtk.SeparatorToolItem())
        toolbar.add(self.optbtn)
        
        hbox = gtk.HBox()
        hbox.pack_start(self.prefbtn)
        self.searchbar = SearchEntry()
        hbox.pack_end(self.searchbar)
        toolbar2.add(hbox)
        
        self.show_all()

    def toggle_preferences(self, w):
        if not self.settingswindow:
            self.settingswindow = SettingsWindow()
        self.settingswindow.show_all()

    def quit(self, widget):
        gtk.main_quit()

class Notebook(gtk.Notebook):
    
    def __init__(self):
        gtk.Notebook.__init__(self)
        self.set_show_tabs(False)
        self._set_own_timeline()
        
    def _set_own_timeline(self):
        self.activityview = ActivityView()
        tab = Tab("Personal Timeline")
        self.append_page(self.activityview, tab)
        tab.closebtn.set_sensitive(False)

class ActivityView(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self)
        
        self.ready = False
        self.days = {}
        self.sorting = "Type"
        
        self.zg = CLIENT
        self.__init_optionsbar()
        self.set_view_type()
    
        self.range = 3
        self._set_today_timestamp()
        
        self.ready = True
        
        settings.connect("change-view", lambda w, x: self.set_view_type(True))
        settings.connect("toggle-time", lambda w, x: self.set_view_type(True))
        settings.connect("toggle-grouping", lambda w: self.set_view_type(True))
        self.set_views()
        
    def set_view_type(self, refresh=False):
        
        for w in self:
            if not w == self.optionsbar:
                self.remove(w)
        
        if settings.view == "Journal":
            self.daysbox = gtk.HBox(True)
        else:
            self.daysbox = gtk.VBox()
        
        self.scroll = gtk.ScrolledWindow()
        self.scroll.add_with_viewport(self.daysbox)
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.pack_start(self.scroll, True, True, 3)
        if refresh:
            self.set_views()
        self.scroll.show_all()

    def __init_optionsbar(self):
        self.optionsbar = gtk.HBox()
        self.pack_start(self.optionsbar,False, False)
        self.optionsbar.pack_start(gtk.Label("Group:"),False, False, 3)
        for k in SUPPORTED_SOURCES.keys():
            btn = ToggleButton(k)
            self.optionsbar.pack_start(btn, False, False)
            #btn.connect_after("toggled", self.set_filter)
            
        self.combobox = gtk.combo_box_new_text()
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Sort by:"), False, False)
        hbox.pack_start(self.combobox, True, False, 3)
        self.optionsbar.pack_end(hbox, False, False)
        self.optionsbar.set_border_width(3)
        
        self.combobox.append_text("Type")
        self.combobox.append_text("Populartiy")
        self.combobox.append_text("Recency")
        
        def change_sorting(widget):
            self.sorting = widget.get_active_text()
            self.set_views()            
        self.combobox.connect("changed", change_sorting)
        self.combobox.set_active(0)
        
    def toggle_optionsbar(self, widget):
        if widget.get_active():
            self.optionsbar.show_all()
        else:
            self.optionsbar.hide_all()
    
    def jump(self, offset):
        self.set_range(self.start+offset, self.end+offset)
        
    def set_range(self, start, end):
        self.start = start
        self.end = end
        self.range = int(int((end - start))/86400) + 1
        self.set_views()
    
    def _set_today_timestamp(self, dayinfocus=None):    
        '''
        Return the range of seconds between the min_timestamp and max_timestamp        
        '''
        # For the local timezone
        if not dayinfocus:
            dayinfocus = int(time.mktime(time.strptime(time.strftime("%d %B %Y") , "%d %B %Y")))
            pt = datetime.datetime.fromtimestamp(dayinfocus).strftime("%A, %d %B %Y    %H:%M:%S")
        self.end =  dayinfocus + 86399 
        self.start =  dayinfocus - (self.range-1)*86400
        self.set_views()
      
    def set_views(self):
        self.days.clear()
        if self.ready:
            print "SETTING VIEWS", self.sorting
            for w in self.daysbox:
                self.daysbox.remove(w)
            for i in xrange(self.range):
                if not settings.view == "Journal":
                    i = (self.range-1) - i
                ptime =  datetime.datetime.fromtimestamp(self.start + i*86400).strftime("%A, %d %B %Y")
                if not self.days.has_key(ptime):
                    dayview = DayView(ptime, self.start + i*86400, sorting=self.sorting)
                    self.days[ptime] = dayview
                    self.daysbox.pack_start(self.days[ptime])
                self.days[ptime].show_all()
                self.days[ptime].init_events(self.sorting)

class DayView(gtk.VBox):
        
    def __init__(self, ptime, timestamp, sorting = "Type"):
        gtk.VBox.__init__(self)
        self.time = ptime
        self.zg = CLIENT
        self.start = timestamp
        self.end = timestamp + 86400
        self.sorting = sorting
        print "************", self.sorting
        self.label = gtk.Label(self.time)
        if ptime == datetime.datetime.fromtimestamp(time.time()).strftime("%A, %d %B %Y"):
            self.label.set_markup("<span><b>"+self.time+"</b></span>")
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)
        scroll.add_with_viewport(self.label)
        self.pack_start(scroll, False, False)
        scroll = gtk.ScrolledWindow()
        if settings.view == "Journal":
            scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        else:
            scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_NEVER)

        self.view = DayListView()
        scroll.add_with_viewport(self.view)
        self.pack_start(scroll)
        
        
    def init_events(self, sorting):
        self.sorting = sorting
        event = Event()
        event.set_interpretation(Interpretation.VISIT_EVENT.uri)        
        event2 = Event()
        event2.set_interpretation(Interpretation.MODIFY_EVENT.uri)
        if self.sorting == "Recency":
            self.zg.find_event_ids_for_templates([event,event2], self._handle_find_events, [self.start*1000, self.end*1000], num_events=50000, result_type=2)
        else:
            self.zg.find_event_ids_for_templates([event,event2], self._handle_find_events, [self.start*1000, self.end*1000], num_events=50000, result_type=4)

    def _handle_find_events(self, ids):
        self.zg.get_events(ids, self._handle_get_events)
    
    def _handle_get_events(self, events):
        self.events = events
        self.view.set_filters(CATEGORY_FILTER)
        self.insert_events(events)
        self.view.show_all()
        
    def insert_events(self, x):
                
        def exists(uri):
            return not uri.startswith("file://") or os.path.exists(urllib.unquote(str(uri[7:])))
        
        event_dict = {}
        self.view.clear()
        subjects = {}
        
        cat, x = self.extract_categories(x)
        
        for c in cat.keys():
            self.view.append_category(c, cat[c])
            
        
        if not self.sorting == "Type":
            for event in x:
                subject = event.subjects[0]
                if exists(subject.uri):
                    icon =  thumbnailer.get_icon(subject, 32)
                    self.view.append_object(icon, subject.text, event)

        else:
            for event in x:
                subject = event.subjects[0] 
                if exists(subject.uri):
                    if not event_dict.has_key(subject.interpretation):
                        event_dict[subject.interpretation] = {}
                    if not event_dict[subject.interpretation].has_key(subject.uri):
                        event_dict[subject.interpretation][subject.uri] = {"count":0, "events":[]}
                    event_dict[subject.interpretation][subject.uri]["count"]+=1
                    event_dict[subject.interpretation][subject.uri]["events"].append(event)
            events = event_dict.keys()
            if events: events.sort()
            for k in events:
                for subject in event_dict[k]:
                    if not subject in subjects.keys():
                        subjects[subject] = event_dict[k][subject]["events"][0].subjects[0]
                        event = event_dict[k][subject]["events"][0]
                        subject = event_dict[k][subject]["events"][0].subjects[0]
                        icon =  thumbnailer.get_icon(subject, 32)
                        self.view.append_object(icon, subject.text, event)

                        
    def extract_categories(self, events):
        categories={}
        temp_events = []
        for event in events:
            cat = event.subjects[0].interpretation 
            if settings.compress_categories[cat]:
                if not categories.has_key(event.subjects[0].interpretation):
                    categories[cat] = []
                categories[cat].append(event)
            else:
                temp_events.append(event)
        return categories, temp_events