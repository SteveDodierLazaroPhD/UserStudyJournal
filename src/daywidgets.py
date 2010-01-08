# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
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
import gettext
import cairo
import pango
import math

from datetime import date

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType

from ui_utils import *
from widgets import *

CLIENT = ZeitgeistClient()

class DayWidget(gtk.VBox):
    # day_start - "time_t"
    # day_end   - "time_t"

    def __init__(self, start, end):
        gtk.VBox.__init__(self)
        hour = 60*60
        self.day_start = start
        self.day_end = end
        
        self.set_date_strings()
        self._periods = [
            (_("Morning"), start, start + 12*hour - 1),
            (_("Afternoon"), start + 12*hour, start + 18*hour - 1),
            (_("Evening"), start + 18*hour, end),
        ]

        self.__init_widgets()
        self.__init_events()

    def set_date_strings(self):
        self.date_string = date.fromtimestamp(self.day_start).strftime("%d %B")
        self.year_string = date.fromtimestamp(self.day_start).strftime("%Y")
        if time.time() < self.day_end and time.time() > self.day_start:
            self.week_day_string = _("Today")
        elif time.time() - 86400 < self.day_end and time.time() - 86400> self.day_start:
            self.week_day_string = _("Yesterday")
        else:
                self.week_day_string = date.fromtimestamp(self.day_start).strftime("%A")
        self.emit("style-set", None)

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
            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL]
            color.red = color.red * 105 / 100
            color.green = color.green * 105 / 100
            color.blue = color.blue * 105 / 100
            evbox2.modify_bg(gtk.STATE_NORMAL, color)

        self.connect("style-set", change_style)

    def __init_date_label(self):

        daylabel = DayLabel(self.week_day_string, self.date_string+", "+ self.year_string)
        #x, y = vbox.get_size_request()
        daylabel.set_size_request(100, 60)
        self.vbox.pack_start(daylabel, False, False)


    def __init_events(self):
        for w in self.view:
            self.view.remove(w)
        for period in self._periods:
            part = DayPartWidget(period[0], period[1], period[2])
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
        self.show()
        if len(ids) > 0:
            self.zg.get_events(ids, self._handle_get_events)
        else:
            self.hide()

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
                if len(events) > 1:
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
        gobject.timeout_add_seconds((int(time.time()) % 86400)+1, self._daily_refresh)
        return False
    
    def day_text(self, context, event):
        context.select_font_face(self.font_name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        
        x, y = event.area.width, event.area.height
        context.set_font_size(20)
        if self.leading:
            context.set_source_rgba(1, 1, 1, 1)
        else:
            context.set_source_rgba(0.2, 0.2, 0.2, 1)
            
        xbearing, ybearing, width, height, xadvance, yadvance = context.text_extents(self.day)
        a = (x-width)/2
        b = y - height - 15
        context.move_to(a, b)
        
        context.show_text(self.day)
        self.date_text(context, event, height)


    def date_text(self, context, event, last_text_height):
        context.select_font_face(self.font_name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

        x, y = event.area.width, event.area.height
        context.set_font_size(12)
        if self.leading:
            context.set_source_rgba(1, 1, 1, 1)
        else:
            context.set_source_rgba(0.7, 0.7, 0.7, 1)

        xbearing, ybearing, width, height, xadvance, yadvance = context.text_extents(self.date)
        a = (x-width)/2
        b = last_text_height + height + 15
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
        r = 5
        w, h = event.area.width, event.area.height
        # Temporary color, I will fix this later when I have a chance to sleep. 
        context.set_source_rgba(red, green, blue, 1)

        context.new_sub_path()
        context.arc(r+x, r+y, r, math.pi, 3 * math.pi /2)
        context.arc(w-r, r+y, r, 3 * math.pi / 2, 0)
        context.close_path()
        context.rectangle(0, r, w, h)
        context.fill_preserve()

    def _daily_refresh(self, *args, **kwargs):
        self.queue_draw()
        gobject.timeout_add_seconds(86400, self._daily_refresh)
        if (time.time() % 86400) < 100: return True
        return False

