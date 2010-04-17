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
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gtk
import time
import gobject
import gettext
import cairo
import pango
import math
import os
import urllib
from datetime import date

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType, TimeRange

from common import shade_gdk_color, combine_gdk_color, get_gtk_rgba
from widgets import *
from thumb import ThumbBox
from timeline import TimelineView, TimelineHeader
from eventgatherer import get_dayevents, get_file_events

CLIENT = ZeitgeistClient()


class GenericViewWidget(gtk.VBox):
    __gsignals__ = {
        "unfocus-day" : (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
        # Sends a list zeitgeist events
        }

    def __init__(self):
        gtk.VBox.__init__(self)
        self.daylabel = None
        self.connect("style-set", self.change_style)

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

    def click(self, widget, event):
        if event.button in (1, 3):
            self.emit("unfocus-day")

    def change_style(self, widget, style):
        rc_style = self.style
        color = rc_style.bg[gtk.STATE_NORMAL]
        color = shade_gdk_color(color, 102/100.0)
        self.view.modify_bg(gtk.STATE_NORMAL, color)
        self.view.modify_base(gtk.STATE_NORMAL, color)


class ThumbnailDayWidget(GenericViewWidget):

    def __init__(self):
        GenericViewWidget.__init__(self)
        self.monitors = []
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.view = ThumbBox()
        self.scrolledwindow.add_with_viewport(self.view)
        self.scrolledwindow.get_children()[0].set_shadow_type(gtk.SHADOW_NONE)
        self.pack_end(self.scrolledwindow)

    def set_day(self, start, end):

        self.day_start = start
        self.day_end = end
        for widget in self:
            if self.scrolledwindow != widget:
                self.remove(widget)
        self._set_date_strings()
        today = int(time.time() ) - 7*86400
        if self.daylabel:
            #Disconnect here
            pass
        if self.day_start < today:
            self.daylabel = DayLabel(self.date_string, self.week_day_string+", "+ self.year_string)
        else:
            self.daylabel = DayLabel(self.week_day_string, self.date_string+", "+ self.year_string)
        self.daylabel.set_size_request(100, 60)
        self.daylabel.connect("button-press-event", self.click)
        self.daylabel.set_tooltip_text(_("Click to return to multiday view"))
        self.pack_start(self.daylabel, False, False)
        self.show_all()
        self.view.hide_all()
        self.daylabel.show_all()
        self.view.show()

        hour = 60*60
        get_file_events(start*1000, (start + 12*hour -1) * 1000, self.set_morning_events)
        get_file_events((start + 12*hour)*1000, (start + 18*hour - 1)*1000, self.set_afternoon_events)
        get_file_events((start + 18*hour)*1000, end*1000, self.set_evening_events)

    def set_morning_events(self, events):
        if len(events) > 0:
            timestamp = int(events[0].timestamp)
            if self.day_start*1000 <= timestamp and timestamp < (self.day_start + 12*60*60)*1000:
                self.view.set_morning_events(events)
            self.view.views[0].show_all()
            self.view.labels[0].show_all()
        else:
            self.view.set_morning_events(events)
            self.view.views[0].hide_all()
            self.view.labels[0].hide_all()

    def set_afternoon_events(self, events):
        if len(events) > 0:
            timestamp = int(events[0].timestamp)
            if (self.day_start + 12*60*60)*1000 <= timestamp and timestamp < (self.day_start + 18*60*60)*1000:
                self.view.set_afternoon_events(events)
            self.view.views[1].show_all()
            self.view.labels[1].show_all()
        else:
            self.view.set_afternoon_events(events)
            self.view.views[1].hide_all()
            self.view.labels[1].hide_all()

    def set_evening_events(self, events):
        if len(events) > 0:
            timestamp = int(events[0].timestamp)
            if (self.day_start + 18*60*60)*1000 <= timestamp and timestamp < self.day_end*1000:
                self.view.set_evening_events(events)
            self.view.views[2].show_all()
            self.view.labels[2].show_all()
        else:
            self.view.set_evening_events(events)
            self.view.views[2].hide_all()
            self.view.labels[2].hide_all()


class SingleDayWidget(GenericViewWidget):

    def __init__(self):
        GenericViewWidget.__init__(self)
        self.ruler = TimelineHeader()
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.view = TimelineView()
        self.scrolledwindow.add(self.view)
        self.pack_end(self.scrolledwindow)
        self.pack_end(self.ruler, False, False)
        self.view.set_events(gtk.gdk.POINTER_MOTION_MASK | gtk.gdk.POINTER_MOTION_HINT_MASK)

    def set_day(self, start, end):
        self.day_start = start
        self.day_end = end
        for widget in self:
            if widget not in (self.ruler, self.scrolledwindow):
                self.remove(widget)
        self._set_date_strings()
        today = int(time.time() ) - 7*86400
        if self.daylabel:
            #Disconnect here
            pass
        if self.day_start < today:
            self.daylabel = DayLabel(self.date_string, self.week_day_string+", "+ self.year_string)
        else:
            self.daylabel = DayLabel(self.week_day_string, self.date_string+", "+ self.year_string)
        self.daylabel.set_size_request(100, 60)
        self.daylabel.connect("button-press-event", self.click)
        self.daylabel.set_tooltip_text(_("Click to return multiday view"))

        self.pack_start(self.daylabel, False, False)
        get_dayevents(start*1000, end*1000, 1, self.view.set_model_from_list)
        self.show_all()

    def change_style(self, widget, style):
        GenericViewWidget.change_style(self, widget, style)
        rc_style = self.style
        color = rc_style.bg[gtk.STATE_NORMAL]
        color = shade_gdk_color(color, 102/100.0)
        self.ruler.modify_bg(gtk.STATE_NORMAL, color)


class DayWidget(gtk.VBox):

    __gsignals__ = {
        "focus-day" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_INT,))
        }

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
        gobject.timeout_add_seconds(
            86400 - (int(time.time() - time.timezone) % 86400), self._refresh)


        self.show_all()
        self._init_events()

    def refresh(self):
        pass

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
        pinbox.show_all()

    def _init_pinbox(self):
        if self.day_start <= time.time() < self.day_end:
            self.view.pack_start(pinbox, False, False)

    def _init_widgets(self):
        self.vbox = gtk.VBox()
        self.pack_start(self.vbox)

        self.daylabel = None

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
            color = shade_gdk_color(color, 102/100.0)
            evbox2.modify_bg(gtk.STATE_NORMAL, color)

        self.connect("style-set", change_style)

    def _init_date_label(self):
        self._set_date_strings()

        today = int(time.time() ) - 7*86400
        if self.daylabel:
            # Disconnect HERE
            pass
        if self.day_start < today:
            self.daylabel = DayLabel(self.date_string, self.week_day_string+", "+ self.year_string)
        else:
            self.daylabel = DayLabel(self.week_day_string, self.date_string+", "+ self.year_string)
        self.daylabel.connect("button-press-event", self.click)
        self.daylabel.set_tooltip_text(
            _("Left click for a detailed timeline view")
            + u"\n" +
            _("Right click for a thumbnail view"))
        self.daylabel.set_size_request(100, 60)
        evbox = gtk.EventBox()
        evbox.add(self.daylabel)
        evbox.set_size_request(100, 60)
        self.vbox.pack_start(evbox, False, False)
        def cursor_func(x, y):
            if evbox.window:
                evbox.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
        self.connect("motion-notify-event", cursor_func)

        def change_style(widget, style):
            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL]
            evbox.modify_bg(gtk.STATE_NORMAL, color)
            self.daylabel.modify_bg(gtk.STATE_NORMAL, color)

        self.connect("style-set", change_style)
        #self.connect("leave-notify-event", lambda x, y: evbox.window.set_cursor(None))

        self.vbox.reorder_child(self.daylabel, 0)

    def click(self, widget, event):
        if event.button == 1:
            self.emit("focus-day", 1)
        elif event.button == 3:
            self.emit("focus-day", 2)

    def _init_events(self):
        for w in self.view:
            if not w == pinbox:
                self.view.remove(w)
        for period in self._periods:
            part = DayPartWidget(period[0], period[1], period[2])
            self.view.pack_start(part, False, False)


class CategoryBox(gtk.HBox):

    def __init__(self, category, events, pinnable = False):
        super(CategoryBox, self).__init__()
        self.view = gtk.VBox(True)
        self.vbox = gtk.VBox()
        for event in events:
            item = Item(event, pinnable)
            hbox = gtk.HBox ()
            #label = gtk.Label("")
            #hbox.pack_start(label, False, False, 7)
            hbox.pack_start(item, True, True, 0)
            self.view.pack_start(hbox, False, False, 0)
            hbox.show()
            #label.show()

        # If this isn't a set of ungrouped events, give it a label
        if category:
            # Place the items into a box and simulate left padding
            self.box = gtk.HBox()
            #label = gtk.Label("")
            self.box.pack_start(self.view)

            hbox = gtk.HBox()
            # Add the title button
            if category in SUPPORTED_SOURCES:
                text = SUPPORTED_SOURCES[category].group_label(len(events))
            else:
                text = "Unknown"

            label = gtk.Label()
            label.set_markup("<span>%s</span>" % text)
            #label.set_ellipsize(pango.ELLIPSIZE_END)

            hbox.pack_start(label, True, True, 0)

            label = gtk.Label()
            label.set_markup("<span>(%d)</span>" % len(events))
            label.set_alignment(1.0,0.5)
            label.set_alignment(1.0,0.5)
            hbox.pack_end(label, False, False, 2)

            hbox.set_border_width(3)

            self.expander = gtk.Expander()
            self.expander.set_label_widget(hbox)

            self.vbox.pack_start(self.expander, False, False)
            self.expander.add(self.box)#

            self.pack_start(self.vbox, True, True, 24)

            self.expander.show_all()
            self.show()
            hbox.show_all()
            label.show_all()
            self.view.show()

        else:
            self.box = self.view
            self.vbox.pack_end(self.box)
            self.box.show()
            self.show()

            self.pack_start(self.vbox, True, True, 16)

        self.show_all()

    def on_toggle(self, view, bool):
        if bool:
            self.box.show()
        else:
            self.box.hide()
        pinbox.show_all()


class DayLabel(gtk.DrawingArea):

    _events = (
        gtk.gdk.ENTER_NOTIFY_MASK | gtk.gdk.LEAVE_NOTIFY_MASK |
        gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON_MOTION_MASK |
        gtk.gdk.POINTER_MOTION_HINT_MASK | gtk.gdk.BUTTON_RELEASE_MASK |
        gtk.gdk.BUTTON_PRESS_MASK
    )

    def __init__(self, day, date):
        if day == _("Today"):
            self.leading = True
        else:
            self.leading = False
        super(DayLabel, self).__init__()
        self.date = date
        self.day = day
        self.set_events(self._events)
        self.connect("expose_event", self.expose)
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)

    def _on_enter(self, widget, event):
        widget.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))

    def _on_leave(self, widget, event):
        widget.window.set_cursor(None)

    def expose(self, widget, event):
        context = widget.window.cairo_create()
        self.context = context

        bg = self.style.bg[0]
        red, green, blue = bg.red/65535.0, bg.green/65535.0, bg.blue/65535.0
        self.font_name = self.style.font_desc.get_family()

        widget.style.set_background(widget.window, gtk.STATE_NORMAL)

        # set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()
        self.draw(widget, event, context)
        self.day_text(widget, event, context)
        return False

    def day_text(self, widget, event, context):
        actual_y = self.get_size_request()[1]
        if actual_y > event.area.height:
            y = actual_y
        else:
            y = event.area.height
        x = event.area.width
        gc = self.style.fg_gc[gtk.STATE_SELECTED if self.leading else gtk.STATE_NORMAL]
        layout = widget.create_pango_layout(self.day)
        layout.set_font_description(pango.FontDescription(self.font_name + " Bold 15"))
        w, h = layout.get_pixel_size()
        widget.window.draw_layout(gc, (x-w)/2, (y)/2 - h + 5, layout)
        self.date_text(widget, event, context, (y)/2 + 5)

    def date_text(self, widget, event, context, lastfontheight):
        gc = self.style.fg_gc[gtk.STATE_SELECTED if self.leading else gtk.STATE_INSENSITIVE]
        layout = widget.create_pango_layout(self.date)
        layout.set_font_description(pango.FontDescription(self.font_name + " 10"))
        w, h = layout.get_pixel_size()
        widget.window.draw_layout(gc, (event.area.width-w)/2, lastfontheight, layout)

    def draw(self, widget, event, context):
        if self.leading:
            bg = self.style.bg[gtk.STATE_SELECTED]
            red, green, blue = bg.red/65535.0, bg.green/65535.0, bg.blue/65535.0
        else:
            bg = self.style.bg[gtk.STATE_NORMAL]
            red = (bg.red * 125 / 100)/65535.0
            green = (bg.green * 125 / 100)/65535.0
            blue = (bg.blue * 125 / 100)/65535.0
        x = 0; y = 0
        r = 5
        w, h = event.area.width, event.area.height
        context.set_source_rgba(red, green, blue, 1)
        context.new_sub_path()
        context.arc(r+x, r+y, r, math.pi, 3 * math.pi /2)
        context.arc(w-r, r+y, r, 3 * math.pi / 2, 0)
        context.close_path()
        context.rectangle(0, r, w, h)
        context.fill_preserve()


class DayButton(gtk.DrawingArea):
    leading = False
    pressed = False
    sensitive = True
    hover = False
    header_size = 60
    bg_color = (0, 0, 0, 0)
    header_color = (1, 1, 1, 1)
    leading_header_color = (1, 1, 1, 1)
    internal_color = (0, 1, 0, 1)
    arrow_color = (1,1,1,1)
    arrow_color_selected = (1, 1, 1, 1)

    __gsignals__ = {
        "clicked":  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,()),
        }
    _events = (
        gtk.gdk.ENTER_NOTIFY_MASK | gtk.gdk.LEAVE_NOTIFY_MASK |
        gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.BUTTON_PRESS_MASK |
        gtk.gdk.MOTION_NOTIFY |   gtk.gdk.POINTER_MOTION_MASK
    )
    def __init__(self, side = 0, leading = False):
        super(DayButton, self).__init__()
        self.set_events(self._events)
        self.set_flags(gtk.CAN_FOCUS)
        self.leading = leading
        self.side = side
        self.connect("button_press_event", self.on_press)
        self.connect("button_release_event", self.clicked_sender)
        self.connect("key_press_event", self.keyboard_clicked_sender)
        self.connect("motion_notify_event", self.on_hover)
        self.connect("leave_notify_event", self._enter_leave_notify, False)
        self.connect("expose_event", self.expose)
        self.connect("style-set", self.change_style)
        self.set_size_request(20, -1)

    def set_sensitive(self, case):
        self.sensitive = case
        self.queue_draw()

    def _enter_leave_notify(self, widget, event, bol):
        self.hover = bol
        self.queue_draw()

    def on_hover(self, widget, event):
        if event.y > self.header_size:
            if not self.hover:
                self.hover = True
                self.queue_draw()
        else:
            if self.hover:
                self.hover = False
                self.queue_draw()
        return False

    def on_press(self, widget, event):
        if event.y > self.header_size:
            self.pressed = True
            self.queue_draw()

    def keyboard_clicked_sender(self, widget, event):
        if event.keyval in (gtk.keysyms.Return, gtk.keysyms.space):
            if self.sensitive:
                self.emit("clicked")
            self.pressed = False
            self.queue_draw()
            return True
        return False

    def clicked_sender(self, widget, event):
        if event.y > self.header_size:
            if self.sensitive:
                self.emit("clicked")
        self.pressed = False
        self.queue_draw()
        return True

    def change_style(self, *args, **kwargs):
        self.bg_color = get_gtk_rgba(self.style, "bg", 0)
        self.header_color = get_gtk_rgba(self.style, "bg", 0, 1.25)
        self.leading_header_color = get_gtk_rgba(self.style, "bg", 3)
        self.internal_color = get_gtk_rgba(self.style, "bg", 0, 1.02)
        self.arrow_color = get_gtk_rgba(self.style, "text", 0, 0.6)
        self.arrow_color_selected = get_gtk_rgba(self.style, "bg", 3)
        self.arrow_color_insensitive = get_gtk_rgba(self.style, "text", 4)

    def expose(self, widget, event):
        context = widget.window.cairo_create()

        context.set_source_rgba(*self.bg_color)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()

        x = 0; y = 0
        r = 5
        w, h = event.area.width, event.area.height
        size = 20
        if self.sensitive:
            context.set_source_rgba(*(self.leading_header_color if self.leading else self.header_color))
            context.new_sub_path()
            context.move_to(x+r,y)
            context.line_to(x+w-r,y)
            context.curve_to(x+w,y,x+w,y,x+w,y+r)
            context.line_to(x+w,y+h-r)
            context.curve_to(x+w,y+h,x+w,y+h,x+w-r,y+h)
            context.line_to(x+r,y+h)
            context.curve_to(x,y+h,x,y+h,x,y+h-r)
            context.line_to(x,y+r)
            context.curve_to(x,y,x,y,x+r,y)
            context.set_source_rgba(*(self.leading_header_color if self.leading else self.header_color))
            context.close_path()
            context.rectangle(0, r, w,  self.header_size)
            context.fill()
            context.set_source_rgba(*self.internal_color)
            context.rectangle(0, self.header_size, w,  h)
            context.fill()
            if self.hover:
                widget.style.paint_box(widget.window, gtk.STATE_PRELIGHT, gtk.SHADOW_OUT,
                                         event.area, widget, "button",
                                         event.area.x, self.header_size,
                                         w, h-self.header_size)
        size = 10
        if not self.sensitive:
            state = gtk.STATE_INSENSITIVE
        elif self.is_focus() or self.pressed:
            widget.style.paint_focus(widget.window, gtk.STATE_ACTIVE, event.area,
                                     widget, None, event.area.x, self.header_size,
                                     w, h-self.header_size)
            state = gtk.STATE_SELECTED
        else:
            state = gtk.STATE_NORMAL
        arrow = gtk.ARROW_RIGHT if self.side else gtk.ARROW_LEFT
        self.style.paint_arrow(widget.window, state, gtk.SHADOW_NONE, None,
                               self, "arrow", arrow, True,
                               w/2-size/2, h/2 + size/2, size, size)


class EventGroup(gtk.VBox):

    def __init__(self, title):
        super(EventGroup, self).__init__()

        # Create the title label
        self.label = gtk.Label(title)
        self.label.set_alignment(0.03, 0.5)
        self.pack_start(self.label, False, False, 6)
        self.events = []
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
        color = combine_gdk_color(color, fcolor)
        self.label.modify_fg(gtk.STATE_NORMAL, color)

    @staticmethod
    def event_exists(uri):
        # TODO: Move this into Zeitgeist's datamodel.py
        return not uri.startswith("file://") or os.path.exists(
            urllib.unquote(str(uri[7:])))

    def set_events(self, events):
        self.events = []
        for widget in self.view:
            self.view.remove(widget)

        if self == pinbox:
            box = CategoryBox(None, events, True)
            self.view.pack_start(box)
        else:
            categories = {}
            for event in events:
                subject = event.subjects[0]
                if self.event_exists(subject.uri):
                    if not categories.has_key(subject.interpretation):
                        categories[subject.interpretation] = []
                    categories[subject.interpretation].append(event)
                    self.events.append(event)

            if not categories:
                self.hide_all()
            else:
                # Make the group title, etc. visible
                self.show_all()

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

                # Make the group's contents visible
                self.view.show()
                pinbox.show_all()

        if len(self.events) == 0:
            self.hide()
        else:
            self.show()

    def get_events(self, *discard):
        if self.event_templates and len(self.event_templates) > 0:
            CLIENT.find_events_for_templates(self.event_templates,
                self.set_events, self.event_timerange, num_events=50000,
                result_type=ResultType.MostRecentSubjects)
        else:
            self.view.hide()


class DayPartWidget(EventGroup):

    def __init__(self, title, start, end):
        # Setup event criteria for querying
        self.event_timerange = [start * 1000, end * 1000]
        self.event_templates = (
            Event.new_for_values(interpretation=Interpretation.VISIT_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.CREATE_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.OPEN_EVENT.uri),
        )

        # Initialize the widget
        super(DayPartWidget, self).__init__(title)

        # FIXME: Move this into EventGroup
        CLIENT.install_monitor(self.event_timerange, self.event_templates,
            self.notify_insert_handler, self.notify_delete_handler)

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
        super(PinBox, self).__init__(_("Pinned items"))

        # Connect to relevant signals
        bookmarker.connect("reload", self.get_events)

    @property
    def event_templates(self):
        if not bookmarker.bookmarks:
            # Abort, or we will query with no templates and get lots of
            # irrelevant events.
            return None

        templates = []
        for bookmark in bookmarker.bookmarks:
            templates.append(Event.new_for_values(subject_uri=bookmark))
        return templates

    def set_events(self, *args, **kwargs):
        super(PinBox, self).set_events(*args, **kwargs)
        # Make the pin icons visible
        self.view.show_all()
        self.show_all()

pinbox = PinBox()
