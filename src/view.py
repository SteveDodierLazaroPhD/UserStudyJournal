'''
Created on Jan 4, 2010

@author: seif
'''

import gtk
import time
from widgets import *
from ui_utils import *
from daywidgets import *
CATEGORY_FILTER= {}
for k in SUPPORTED_SOURCES.keys():
            CATEGORY_FILTER[k] = True

class ActivityView(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self)
        
        self.days = {}
        self.sorting = "Recency"
        
        self.range = 3
        self.daysbox = None
        
        self._set_today_timestamp()
        self.__init_optionsbar()
        self.set_view_type()
        
        settings.connect("change-view", lambda w, x: self.set_view_type(True))
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
        
        self.pack_start(self.daysbox)
        if refresh:
            self.set_views()
        self.daysbox.show_all()

    def __init_optionsbar(self):
        self.optionsbar = gtk.HBox()
        self.pack_end(self.optionsbar,False, False)
        self.optionsbar.pack_start(gtk.Label("Group:"),False, False, 3)
        for k in SUPPORTED_SOURCES.keys():
            btn = ToggleButton(k)
            self.optionsbar.pack_start(btn, False, False)
            #btn.connect_after("toggled", self.set_filter)

        self.timecheckbox = gtk.CheckButton("Show Time")
        self.timecheckbox.set_active(settings.show_timestamps)
        self.timecheckbox.connect("toggled", lambda w: settings.toggle_time(self.timecheckbox.get_active()))
        self.timecheckbox.set_focus_on_click(False)
        self.optionsbar.pack_end(self.timecheckbox, False, False, 3)
        
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
        self.end =  dayinfocus + 86399 
        self.start =  dayinfocus - (self.range-1)*86400
        self.set_views()
      
    def set_views(self):
        #for day in self.days:
           # self.days[day].clear()
        #self.days.clear()
        if self.daysbox:
            for w in self.daysbox:
                self.daysbox.remove(w)
            for i in xrange(self.range):
                if not settings.view == "Journal":
                    i = (self.range-1) - i
                ptime =  datetime.datetime.fromtimestamp(self.start + i*86400).strftime("%A, %d %B %Y")
                if not self.days.has_key(ptime):
                    print ptime
                    dayview = DayWidget(self.start + i*86400, self.start + i*86400 + 86400)
                    self.days[ptime] = dayview
                self.daysbox.pack_start(self.days[ptime], True, True, 3)
                #self.days[ptime].init_events()
                