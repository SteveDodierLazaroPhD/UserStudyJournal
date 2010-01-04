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
        tm = gtk.Menu()
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
        self.view = DayListView()
        for event in events:
            icon = thumbnailer.get_icon(event.subjects[0], 24)
            text = event.subjects[0].text
            self.view.append_object(icon, text, event)
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

class DayListView(gtk.TreeView):
    def __init__(self):
        gtk.TreeView.__init__(self)
        self.store = gtk.ListStore(
                                gtk.gdk.Pixbuf,
                                str,    #TIME
                                gobject.TYPE_PYOBJECT,
                                str
                                )

        self.filters = {}
        # Icon
        icon_cell = gtk.CellRendererPixbuf()
        icon_cell.set_property("yalign", 0.5)
        icon_cell.set_property("xalign", 1.0)
        icon_column = gtk.TreeViewColumn("Icon", icon_cell, pixbuf=0)

        text_cell = gtk.CellRendererText()
        text_cell.set_property("ellipsize", pango.ELLIPSIZE_END)
        text_column = gtk.TreeViewColumn("Activity", text_cell, markup=1)
        text_column.set_expand(True)
        
        time_cell = gtk.CellRendererText()
        self.time_column = gtk.TreeViewColumn("Activity", time_cell, markup=3)
        
        self.append_column(icon_column)
        self.append_column(text_column)
        self.append_column(self.time_column)
            
        
        def _deselect_all(view, event):
            selection = self.get_selection()
            selection.unselect_all()
        
        self.connect("focus-out-event", _deselect_all)
        
        self.set_headers_visible(False)
        
        self.set_model(self.store)
        
        self.connect("button-press-event", self._handle_click)
        self.connect("row-activated", self._handle_open)
        
    def _handle_open(self, view=None, path=None, column=None, item=None):
        if not item:
            item = view.get_model()[path][2].subjects[0]
        if item.mimetype == "x-tomboy/note":
            uri_to_open = "note://tomboy/%s" % os.path.splitext(os.path.split(item.uri)[1])[0]
        else:
            uri_to_open = item.uri
        if uri_to_open:
            launcher.launch_uri(uri_to_open, item.mimetype)
        
    def _handle_click(self, view, ev):
        if ev.button == 3:
            (path,col,x,y) = view.get_path_at_pos(int(ev.x),int(ev.y))
            iter = self.filterstore.get_iter(path)
            item = self.filterstore.get_value(iter, 2).subjects[0]
            if item:
                menu = gtk.Menu()
                menu.attach_to_widget(view, None)
                self._populate_popup(menu, item)
                menu.popup(None, None, None, ev.button, ev.time)

    def _populate_popup(self, menu, item):
        open = gtk.ImageMenuItem(gtk.STOCK_OPEN)
        open.connect("activate", lambda *discard: self._handle_open(item=item))
        menu.append(open)
        most = gtk.MenuItem(_("Related files..."))
        menu.append(most)
        prop = gtk.MenuItem(_("Properties..."))
        menu.append(prop)
        menu.show_all()

    
    def set_filters(self, filters):
        self.filters = filters
        for path in self.store:
            event =  path[2]
            path[3] = self.filters[event.subjects[0].interpretation]

    def clear(self):
        self.store.clear()
    
    def append_object(self, icon, text, event):
        #print text
        #text = "<span><b>"+text+"</b></span>"
        bool = True
        timestamp = datetime.datetime.fromtimestamp(int(event.timestamp)/1000).strftime("%H:%M")
        timestamp = "<span color='darkgrey'>"+timestamp+"</span>"
        self.store.append([
                        icon,
                        text,
                        event,
                        timestamp
                        ])