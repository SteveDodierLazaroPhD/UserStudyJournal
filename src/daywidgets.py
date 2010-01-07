# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gtk
import time, datetime
import gobject
import cairo
import pango
import math

from datetime import date

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType

from ui_utils import *
from widgets import *

try:
    CLIENT = ZeitgeistClient()
except RuntimeError, e:
    print "Unable to connect to Zeitgeist: %s" % e
    CLIENT = None


class DayWidget(gtk.VBox):
    # day_start - "time_t"
    # day_end   - "time_t"

    def __init__(self, start, end):
        gtk.VBox.__init__(self)
        hour = 60*60
        self.day_start = start
        self.day_end = end
        self.date_string = date.fromtimestamp(self.day_start).strftime("%d %B")
        self.year_string = date.fromtimestamp(self.day_start).strftime("%Y")
        if time.time() < self.day_end and time.time() > self.day_start:
            self.week_day_string = "Today"
        elif time.time() - 86400 < self.day_end and time.time() - 86400> self.day_start:
            self.week_day_string = "Yesterday"
        else:
                self.week_day_string = date.fromtimestamp(self.day_start).strftime("%A")

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


        self.vbox = gtk.VBox()
        evbox = gtk.EventBox()
        evbox.add(self.vbox)

        self.pack_start(evbox)

        self.__init_date_label()

        #label.modify_bg(gtk.STATE_SELECTED, style.bg[gtk.STATE_SELECTED])

        self.view = gtk.VBox()
        scroll = gtk.ScrolledWindow()
        scroll.set_shadow_type(gtk.SHADOW_NONE)

        evbox2 = gtk.EventBox()
        evbox2.add(self.view)
        self.view.set_border_width(6)

        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.add_with_viewport(evbox2)
        for w in scroll.get_children():
            w.set_shadow_type(gtk.SHADOW_NONE)
        self.vbox.pack_start(scroll)
        self.show_all()

        def change_style(widget, style):
            print "*************"
            rc_style = self.style
            if self.week_day_string == "Today":
                color = rc_style.bg[gtk.STATE_SELECTED]
                evbox.modify_bg(gtk.STATE_NORMAL, color)
            else:
                color = rc_style.base[gtk.STATE_NORMAL]
                evbox.modify_bg(gtk.STATE_NORMAL,  color)

            color = rc_style.base[gtk.STATE_NORMAL]
            color.red = color.red * 95 / 100
            color.green = color.green * 95 / 100
            color.blue = color.blue * 95 / 100
            evbox2.modify_bg(gtk.STATE_NORMAL, color)

        self.connect("style-set", change_style)

    def __init_date_label(self):

        vbox = gtk.VBox(False, 3)
        vbox = gtk.VBox(False, 3)
        daylabel = DayLabel(self.week_day_string, self.date_string)
        x, y = vbox.get_size_request()
        daylabel.set_size_request(100, 60)


        today = time.time()

        vbox.pack_start(daylabel,False,False)

        self.vbox.pack_start(vbox, False, False)


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
        self.label.set_markup("<span>%s</span>" % part)
        self.label.set_alignment(0.01, 0.5)
        self.pack_start(self.label, False, False, 6)
        self.view = gtk.VBox()
        self.pack_start(self.view)
        self.zg = CLIENT
        self.show_all()
        
        event = Event()
        event.set_interpretation(Interpretation.VISIT_EVENT.uri)
        event2 = Event()
        event2.set_interpretation(Interpretation.MODIFY_EVENT.uri)
        
        self.event_templates = [] #[event, event2]
        
        def change_style(widget, style):
            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL] 
            color.red = color.red*2/3
            color.green = color.green*2/3
            color.blue = color.blue*2/3
            #label1.modify_text(gtk.STATE_NORMAL, color)
            self.label.modify_fg(gtk.STATE_NORMAL, color)
                

        self.connect("style-set", change_style)
        
        self.zg.install_monitor([self.start*1000, self.end*1000], self.event_templates,
            self.notify_insert_handler, self.notify_delete_handler)
        
    def notify_insert_handler(self, time_range, events):
            self.init_events()
        
    def notify_delete_handler(self, time_range, event_ids):
            self.init_events()            
        
    def init_events(self):
        self.zg.find_event_ids_for_templates(self.event_templates,
            self._handle_find_events, [self.start * 1000, self.end * 1000],
            num_events=50000, result_type=ResultType.MostRecentSubjects)

    def _handle_find_events(self, ids):
        self.show_all()
        if len(ids) > 0:
            self.zg.get_events(ids, self._handle_get_events)
        else:
            self.hide_all()

    def _handle_get_events(self, events):
        real_count = 0

        def exists(uri):
            return not uri.startswith("file://") or \
                os.path.exists(urllib.unquote(str(uri[7:])))

        self.categories = {}

        for widget in self.view:
            self.view.remove(widget)

        for event in events:
            subject = event.subjects[0]
            if exists(subject.uri):
                real_count += 1
                if not self.categories.has_key(subject.interpretation):
                    self.categories[subject.interpretation] = []
                self.categories[subject.interpretation].append(event)
        if real_count == 0:
            self.hide_all()
        else:
            keys = self.categories.keys()
            keys.sort()

            temp_keys = []
            for key in keys:
                events = self.categories[key]
                events.reverse()
                if len(events) > 3:
                    box = CategoryBox(key, events)
                    self.view.pack_start(box)
                else:
                    temp_keys.append(key)
            
            temp_events = []
            
            for key in temp_keys:
                events = self.categories[key]
                temp_events += events
            
            def comp(x, y):
                return cmp(int(x.timestamp), int(y.timestamp))
            
            temp_events.sort(comp)
            box = CategoryBox(None, temp_events)
            self.view.pack_start(box)

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

        if not category:
            self.view.show_all()
            self.btn.hide_all()

    def toggle(self, view, bool):
        if bool:
            self.view.show_all()
            self.label.show_all()
        else:
            self.view.hide_all()
            self.label.hide_all()

class DayLabel(gtk.DrawingArea):

    def __init__(self, day, date):
        if day == "Today":
            self.leading = True
        else:
            self.leading = False
        super(DayLabel, self).__init__()
        self.date = date
        self.day = day
        self.connect("expose_event", self.expose)
    
    def expose(self, widget, event):
        context = widget.window.cairo_create()
        self.context = context

        bg = self.style.bg[0]
        red, green, blue = bg.red/65535.0, bg.green/65535.0, bg.blue/65535.0
        self.font_name = self.style.font_desc.get_family()
        
        context.set_source_rgba(red, green, blue, 1)

        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        # set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()
        self.draw(context, event)
        self.day_text(context, event)
        return False
    
    def day_text(self, context, event):
        context.select_font_face(self.font_name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        
        x, y = event.area.width, event.area.height
        context.set_font_size(24)
        if self.leading:
            context.set_source_rgba(1, 1, 1, 1)
        else:
            context.set_source_rgba(0.2, 0.2, 0.2, 1)
            
        xbearing, ybearing, width, height, xadvance, yadvance = context.text_extents(self.day)
        a = (x-width)/2
        b = y-height-5
        context.move_to(a, b)
        
        context.show_text(self.day)
        self.date_text(context, event, height)


    def date_text(self, context, event, last_text_height):
        context.select_font_face(self.font_name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

        x, y = event.area.width, event.area.height
        context.set_font_size(14)
        if self.leading:
            context.set_source_rgba(1, 1, 1, 1)
        else:
            context.set_source_rgba(0.7, 0.7, 0.7, 1)

        xbearing, ybearing, width, height, xadvance, yadvance = context.text_extents(self.date)
        a = (x-width)/2
        b = last_text_height + height + 10
        context.move_to(a, b)
        
        context.show_text(self.date)
    
    def draw(self, context, event):
        if self.leading:
            bg = self.style.bg[3]
            red, green, blue = bg.red/65535.0, bg.green/65535.0, bg.blue/65535.0
        else:
            red, green, blue = 1, 1, 1
        
        # Draw
        x = 0; y = 0
        r = 8
        w, h = event.area.width, event.area.height
        # Temporary color, I will fix this later when I have a chance to sleep. 
        context.set_source_rgba(red, green, blue, 1)

        context.new_sub_path()
        context.arc(r+x, r+y, r, math.pi, 3 * math.pi /2)
        context.arc(w-r, r+y, r, 3 * math.pi / 2, 0)
        context.close_path()
        context.rectangle(0, r, w, h)
        context.fill_preserve()
