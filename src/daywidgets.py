# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
# Copyright © 2010 Siegfried Gevatter <siegfried@gevatter.com>
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
    ResultType, TimeRange

from ui_utils import *
from widgets import *

CLIENT = ZeitgeistClient()

class DayWidget(gtk.VBox):

    def __init__(self, start, end):
        super(DayWidget, self).__init__()
        hour = 60*60
        self.day_start = start
        self.day_end = end
        
        self._set_date_strings()
        self._periods = [
            (_("Morning"), start, start + 12*hour - 1),
            (_("Afternoon"), start + 12*hour, start + 18*hour - 1),
            (_("Evening"), start + 18*hour, end),
        ]

        self._init_widgets()
        self._init_pinbox()
        self._init_events()
        gobject.timeout_add_seconds(
            86400 - (int(time.time() - time.timezone) % 86400), self._refresh)

    def _set_date_strings(self):
        self.date_string = date.fromtimestamp(self.day_start).strftime("%d %B")
        self.year_string = date.fromtimestamp(self.day_start).strftime("%Y")
        if time.time() < self.day_end and time.time() > self.day_start:
            self.week_day_string = _("Today")
        elif time.time() - 86400 < self.day_end and time.time() - 86400> self.day_start:
            self.week_day_string = _("Yesterday")
        else:
                self.week_day_string = date.fromtimestamp(self.day_start).strftime("%A")
        self.emit("style-set", None)

    def _refresh(self):
        self._init_date_label()
        self._init_pinbox()

    def _init_pinbox(self):
        if self.day_start <= time.time() < self.day_end:
            self.view.pack_start(pinbox, False, False)

    def _init_widgets(self):
        self.vbox = gtk.VBox()
        evbox = gtk.EventBox()
        evbox.add(self.vbox)

        self.pack_start(evbox)

        self._init_date_label()

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
            
            if color.red * 102/100 > 65535.0:
                color.red = 65535.0
            else:
                color.red = color.red * 102 / 100
                
            if color.green * 102/100 > 65535.0:
                color.green = 65535.0
            else:
                color.green = color.green * 102 / 100
                
            if color.blue * 102/100 > 65535.0:
                color.blue = 65535.0
            else:
                color.blue = color.blue * 102 / 100
                
            evbox2.modify_bg(gtk.STATE_NORMAL, color)

        self.connect("style-set", change_style)

    def _init_date_label(self):
        self._set_date_strings()
        
        today = int(time.time() )- 7*86400
        if self.day_start < today:
            self.daylabel = DayLabel(self.date_string, self.week_day_string+", "+ self.year_string)
        else:
            self.daylabel = DayLabel(self.week_day_string, self.date_string+", "+ self.year_string)
        self.daylabel.set_size_request(100, 60)
        self.vbox.pack_start(self.daylabel, False, False)
        self.vbox.reorder_child(self.daylabel, 0)

    def _init_events(self):
        for w in self.view:
            if not w == pinbox:
                self.view.remove(w)
        for period in self._periods:
            part = DayPartWidget(period[0], period[1], period[2])
            self.view.pack_start(part, False, False)
            part.get_events()

class CategoryBox(gtk.VBox):

    def __init__(self, category, events):
        super(CategoryBox, self).__init__()

        self.view = gtk.VBox(True)
        for event in events:
            item = Item(event)
            self.view.pack_start(item)

        # If this isn't a set of ungrouped events, give it a label
        if category:
            # Place the items into a box and simulate left padding
            self.box = gtk.HBox()
            self.box.pack_start(gtk.Label(" " * 3), False, False)
            self.box.pack_start(self.view)
            self.pack_end(self.box)
            
            # Add the title button
            self.btn = CategoryButton(category, len(events))
            self.btn.connect("toggle", self.on_toggle)
            self.pack_start(self.btn, False, False)
            
            self.show_all()
            self.box.hide_all()
        else:
            self.box = self.view
            self.pack_end(self.box)
            self.show_all()

    def on_toggle(self, view, bool):
        if bool:
            self.box.show_all()
        else:
            self.box.hide_all()

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
        context.set_font_size(20)
        if self.leading:
            fg = self.style.text[gtk.STATE_SELECTED]
            red, green, blue = fg.red/65535.0, fg.green/65535.0, fg.blue/65535.0
            context.set_source_rgba(red, green, blue, 1)
        else:
            fg = self.style.fg[gtk.STATE_NORMAL]
            red, green, blue = fg.red/65535.0, fg.green/65535.0, fg.blue/65535.0
            context.set_source_rgba(red, green, blue, 1)
            
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
            fg = self.style.text[gtk.STATE_SELECTED]
            red, green, blue = fg.red/65535.0, fg.green/65535.0, fg.blue/65535.0
            context.set_source_rgba(red, green, blue, 1)
        else:
            fg = self.style.fg[gtk.STATE_NORMAL]
            bg = self.style.bg[gtk.STATE_NORMAL]
            red, green, blue = (2*bg.red+fg.red)/3/65535.0, (2*bg.green+fg.green)/3/65535.0, (2*bg.blue+fg.blue)/3/65535.0
            context.set_source_rgba(red, green, blue, 1)

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
            bg = self.style.bg[gtk.STATE_NORMAL]
            red = (bg.red * 125 / 100)/65535.0
            green = (bg.green * 125 / 100)/65535.0
            blue = (bg.blue * 125 / 100)/65535.0
        
        # Draw
        x = 0; y = 0
        r = 5
        w, h = event.area.width, event.area.height
        # Temporary color, I will fix this later when I have a chance to sleep. 
        #grad = cairo.LinearGradient(0, 3*event.area.height, 0, 0)
        #grad.add_color_stop_rgb(0,  0, 0, 0)
        #grad.add_color_stop_rgb(1,  red, green, blue)
        
        #if self.leading:
            #context.set_source(grad)
        context.set_source_rgba(red, green, blue, 1)

        context.new_sub_path()
        context.arc(r+x, r+y, r, math.pi, 3 * math.pi /2)
        context.arc(w-r, r+y, r, 3 * math.pi / 2, 0)
        context.close_path()
        context.rectangle(0, r, w, h)
        context.fill_preserve()

class EventGroup(gtk.VBox):

    def __init__(self, title):
        super(EventGroup, self).__init__()
        
        # Create the title label
        self.label = gtk.Label(title)
        self.label.set_alignment(0.03, 0.5)
        self.pack_start(self.label, False, False, 6)
        
        # Create the main container
        self.view = gtk.VBox()
        self.pack_start(self.view)

        # Connect to relevant signals
        self.connect("style-set", self.on_style_change)
        
        # Populate the widget with content
        self.get_events()

    def on_style_change(self, widget, style):
        """ Update used colors according to the system theme. """
        color = self.style.bg[gtk.STATE_NORMAL]
        fcolor = self.style.fg[gtk.STATE_NORMAL] 
        color.red = (2 * color.red + fcolor.red) / 3
        color.green = (2 * color.green + fcolor.green) / 3
        color.blue = (2 * color.blue + fcolor.blue) / 3
        self.label.modify_fg(gtk.STATE_NORMAL, color)

    @staticmethod
    def event_exists(uri):
        # TODO: Move this into Zeitgeist's datamodel.py
        return not uri.startswith("file://") or os.path.exists(
            urllib.unquote(str(uri[7:])))

    def set_events(self, events):
        for widget in self.view:
            self.view.remove(widget)

        categories = {}
        for event in events:
            subject = event.subjects[0]
            if self.event_exists(subject.uri):
                if not categories.has_key(subject.interpretation):
                    categories[subject.interpretation] = []
                categories[subject.interpretation].append(event)

        if not categories:
            self.hide_all()
        else:
            ungrouped_events = []
            for key in sorted(categories.iterkeys()):
                events = categories[key]
                if len(events) > 3:
                    box = CategoryBox(key, list(reversed(events)))
                    self.view.pack_start(box)
                else:
                    ungrouped_events += events

            ungrouped_events.sort(key=lambda x: x.timestamp)
            box = CategoryBox(None, ungrouped_events)
            self.view.pack_start(box)
            self.view.show()

    def get_events(self):
        if self.event_templates is not None:
            CLIENT.find_events_for_templates(self.event_templates,
                self.set_events, self.event_timerange, num_events=50000,
                result_type=ResultType.MostRecentSubjects)

class DayPartWidget(EventGroup):

    def __init__(self, title, start, end):
        # Setup event criteria for querying
        self.event_timerange = [start * 1000, end * 1000]
        self.event_templates = (
            Event.new_for_values(interpretation=Interpretation.VISIT_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri)
        )
        
        # Initialize the widget
        super(DayPartWidget, self).__init__(title)
        
        # FIXME: Move this into EventGroup
        CLIENT.install_monitor(self.event_timerange, self.event_templates,
            self.notify_insert_handler, self.notify_delete_handler)
        self.show_all()

    def notify_insert_handler(self, time_range, events):
        # FIXME: Don't regenerate everything, we already get the
        # information we need
        self.get_events()

    def notify_delete_handler(self, time_range, event_ids):
        # FIXME: Same as above
        self.get_events()

class PinBox(EventGroup):

    def __init__(self):
        # Setup event criteria for querying
        self.event_timerange = TimeRange.until_now()

        # Initialize the widget
        super(PinBox, self).__init__("Pinned")

        # Connect to relevant signals
        bookmarker.connect("reload", lambda widget, uris: self.get_events())

    @property
    def event_templates(self):
        if not bookmarker.bookmarks:
            # Abort, or we will query with no templates and get lots of
            # irrelevant events.
            return None
        
        templates = []
        for bookmark in bookmarker.bookmarks:
            templates.append(Event.new_for_values(
                subjects=[Subject.new_for_values(uri=bookmark)]))
        return templates

pinbox = PinBox()
