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

SUBJECT_VIEW = "File View"
EVENT_VIEW = "Activity View"
VIEW_TYPE = SUBJECT_VIEW


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
        
        self.vbox = gtk.VBox()
        self.add(self.vbox)
        
        self.__init_widgets()
        self.__init_toolbar()
        self.__init_menubar()
        
        self.vbox.pack_start(self.menu, False, False)
        self.vbox.pack_start(self.toolbar, False, False)
        self.vbox.pack_start(self.notebook, True, True)
        self.vbox.pack_start(self.statusbar, False, False)
        
        self.show_all()
        self.notebook.activityview.optionsbar.hide_all()
        
    def __init_menubar(self):
        viewmenu = gtk.Menu()
        
        filem = gtk.MenuItem("File")
        filem.set_submenu(viewmenu)
        self.menu.append(filem)
        self.menu.show_all()
        
    def __init_widgets(self):
        self.menu = gtk.MenuBar()
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
        self.prefbtn = gtk.ToggleToolButton("gtk-preferences")
        
        self.todaybtn.connect("clicked", lambda w: self.notebook.activityview._set_today_timestamp())
        self.backbtn.connect("clicked", lambda w: self.notebook.activityview.jump(-86400))
        self.fwdbtn.connect("clicked", lambda w: self.notebook.activityview.jump(86400))
        self.prefbtn.connect("toggled", self.notebook.activityview.toggle_optionsbar)
        
        toolbar.add(self.backbtn)
        toolbar.add(self.todaybtn)
        toolbar.add(self.fwdbtn)
        toolbar.add(gtk.SeparatorToolItem())
        toolbar.add(self.prefbtn)
        
        #self.combobox = gtk.combo_box_new_text()
        #self.combobox.append_text(SUBJECT_VIEW)
        #self.combobox.append_text(EVENT_VIEW)
        #self.combobox.set_active(0)
        
        #hbox = gtk.VBox()
        #hbox.pack_start(self.combobox, True, False)
        
        #toolbar2.add(hbox)
        
        self.searchbar = SearchEntry()
        toolbar2.add(self.searchbar)
        
        self.show_all()

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
        self.zg = CLIENT
        self.daysbox = gtk.HBox(True)
        scroll = gtk.ScrolledWindow()
        scroll.add_with_viewport(self.daysbox)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.__init_optionsbar()
        
        self.category_filter = {}
        for k in SUPPORTED_SOURCES.keys():
            self.category_filter[k] = True
        
        self.pack_start(scroll)
        self.days = {}
        
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        #self.pack_end(scroll, True, True)
        scroll.set_border_width(1)
        
        self.range = 3
        self._set_today_timestamp()
        self.set_view()
        
    def __init_optionsbar(self):
        self.optionsbar = gtk.HBox()
        self.pack_start(self.optionsbar,False, False)
        self.optionsbar.pack_start(gtk.Label("Show:"),False, False, 3)
        for k in SUPPORTED_SOURCES.keys():
            img = gtk.image_new_from_pixbuf(get_category_icon(SUPPORTED_SOURCES[k]["icon"]))
            btn = FilterButton(img, k)
            self.optionsbar.pack_start(btn, False, False)
            btn.connect_after("clicked", self.set_filter)
    
    def set_filter(self, widget):
        self.category_filter[widget.category] = widget.active
        print widget.category, widget.active
        for daybox in self.days.values():
            daybox.view.set_filters(self.category_filter)
    
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
        print self.range
        self.set_view()
    
    def _set_today_timestamp(self, dayinfocus=None):    
        '''
        Return the range of seconds between the min_timestamp and max_timestamp        
        '''
        # For the local timezone
        if not dayinfocus:
            dayinfocus = int(time.mktime(time.strptime(time.strftime("%d %B %Y") , "%d %B %Y")))
            pt = datetime.datetime.fromtimestamp(dayinfocus).strftime("%A, %d %B %Y    %H:%M:%S")
            print self.range, dayinfocus, "--------------> "+ pt
        self.end =  dayinfocus + 86399 
        self.start =  dayinfocus - (self.range-1)*86400
        self.set_view()
      
            
        
    def set_view(self):
        event = Event()
        event.set_interpretation(Interpretation.VISIT_EVENT.uri)        
        event2 = Event()
        event2.set_interpretation(Interpretation.MODIFY_EVENT.uri)
        self.zg.find_event_ids_for_templates([event,event2], self._handle_find_events, [self.start*1000, self.end*1000], num_events=50000, result_type=0)
            
    def _handle_find_events(self, ids):
        self.zg.get_events(ids, self._handle_get_events)
    
    def _handle_get_events(self, events):
        for w in self.daysbox:
            self.daysbox.remove(w)

        event_dict = {}

        for i in xrange(self.range):
            ptime =  datetime.datetime.fromtimestamp(self.start + i*86400).strftime("%A, %d %B %Y")
            if not self.days.has_key(ptime):
                dayview = DayView(ptime)
                self.days[ptime] = dayview
                event_dict[ptime] = []
                print ptime
            self.daysbox.pack_start(self.days[ptime])
        
        
        for event in events:
            t = datetime.datetime.fromtimestamp(float(event.timestamp)/1000).strftime("%A, %d %B %Y")
            if not event_dict.has_key(t):
                event_dict[t] = []
            event_dict[t].append(event)
            
        for k in event_dict.keys():
            dayview = self.days[k]
            dayview.view.set_filters(self.category_filter)
            dayview.insert_events(event_dict[k])
            dayview.show_all()


class DayView(gtk.VBox):
        
    def __init__(self, ptime):
        gtk.VBox.__init__(self)
        self.time = ptime
        self.label = gtk.Label(self.time)
        if ptime == datetime.datetime.fromtimestamp(time.time()).strftime("%A, %d %B %Y"):
            self.label.set_markup("<span><b>"+self.time+"</b></span>")
        self.pack_start(self.label, False, False)
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.pack_start(scroll)
        self.view = DayListView()
        scroll.add_with_viewport(self.view)
        
    def insert_events(self, x):
                
        def exists(uri):
            return not uri.startswith("file://") or os.path.exists(urllib.unquote(str(uri[7:])))
        
        event_dict = {}
        self.view.clear()
        subjects = []
        
        if VIEW_TYPE== SUBJECT_VIEW:
            for event in x:
                subject = event.subjects[0]
                
                if not event_dict.has_key(subject.interpretation):
                    event_dict[subject.interpretation] = {}
                if not event_dict[subject.interpretation].has_key(subject.uri):
                    event_dict[subject.interpretation][subject.uri] = {"count":0, "events":[]}
                event_dict[subject.interpretation][subject.uri]["count"]+=1
                event_dict[subject.interpretation][subject.uri]["events"].append(event)
            for k in event_dict.keys():
                '''
                icon = get_category_icon(SUPPORTED_SOURCES[k]["icon"])
                text = str(len(event_dict[k]))+" "+SUPPORTED_SOURCES[k]["desc"]
                self.view.append_object(icon, text, event_dict[k])
                '''
                for subject in event_dict[k]:
                    if not subject in subjects:
                        if exists(subject):
                            subjects.append(subject)
                            subject = event_dict[k][subject]["events"][0].subjects[0]
                            icon =  thumbnailer.get_icon(subject, 32)
                            self.view.append_object(icon, subject.text, subject)

