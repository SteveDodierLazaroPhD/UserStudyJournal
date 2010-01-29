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
import time, datetime
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

from widgets import *
import logwidget
from eventgatherer import get_dayevents

CLIENT = ZeitgeistClient()

class SingleDayWidget(gtk.VBox):

    __gsignals__ = {
        "unfocus-day" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    ())
        }

    def __init__(self):
        gtk.VBox.__init__(self)
        self.daylabel = None
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.view = logwidget.DetailedView()
        self.view.connect("area-clicked", self.area_clicked)
        self.view.connect("private-area-clicked", self.private_area_clicked)
        self.scrolledwindow.add_with_viewport(self.view)
        self.scrolledwindow.get_children()[0].set_shadow_type(gtk.SHADOW_NONE)
        self.pack_end(self.scrolledwindow)
        self.f_color = self.style.text[4]

        def change_style(widget, style):
            self.f_color = widget.style.text[4]
            self.f_color.red = max(self.f_color.red * 60/100, 0)
            self.f_color.green = max(self.f_color.green * 60/100, 0)
            self.f_color.blue = max(self.f_color.blue * 60/100, 0)
            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL]
            color.red = min(color.red * 102/100, 65535.0)
            color.green = min(color.green * 102/100, 65535.0)
            color.blue = min(color.blue * 102/100, 65535.0)
            self.view.modify_bg(gtk.STATE_NORMAL, color)

        self.connect("style-set", change_style)

        def text_handler(obj):
            """
            A text handler that returns the text to be drawn by the
            draw_text_box

            Arguments:
            - obj: A event object
            """
            text = obj.subjects[0].text
            interpretation = obj.subjects[0].interpretation
            t1 = (logwidget.FILETYPESNAMES[interpretation] if
                  interpretation in logwidget.FILETYPESNAMES.keys() else "Unknown")
            t1 = "<b>" + t1 + "</b>"
            t2 = "<span color='%s'>%s</span> " % (self.f_color, text)
            return str(t1) + "\n" + str(t2) + ""
        self.view.set_text_handler(text_handler)

        def query_tooltip(widget, x, y, keyboard_mode, tooltip):
            """
            Uses _currently_active_obj to check the tooltip
            _currently_active_obj is a zeitgeist event
            """
            if widget._currently_active_obj:
                tooltip_window = widget.get_tooltip_window()
                gio_file = GioFile.create(widget._currently_active_obj.subjects[0].uri)
                return tooltip_window.preview(gio_file)
            return False
        self.view.set_tooltip_window(StaticPreviewTooltip)
        self.view.connect("query-tooltip", query_tooltip)

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
        evbox = gtk.EventBox()
        evbox.add(self.daylabel)
        self.pack_start(evbox, False, False)
        get_dayevents(start*1000, end*1000, self.view.set_datastore)
        self.show_all()


        #self.connect("motion-notify-event", lambda x, y: evbox.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2)))
        #self.connect("leave-notify-event", lambda x, y: evbox.window.set_cursor(None))
        try:
            evbox.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
        except:
            pass

    def click(self, widget, event):
        if event.button == 1:
            self.emit("unfocus-day")

    def area_clicked(self, widget, zevent):
        """
        A sample event for clicks
        """
        gio_file = GioFile.create(zevent.subjects[0].uri)
        if gio_file: gio_file.launch()

    def private_area_clicked(self, widget, obj):
        widget.queue_draw()


class DayWidget(gtk.VBox):

    __gsignals__ = {
        "focus-day" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    ())
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
        for w in self.view:
            w.on_style_change(None, None)

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

        today = int(time.time() ) - 7*86400
        if self.daylabel:
            # Disconnect HERE
            pass
        if self.day_start < today:
            self.daylabel = DayLabel(self.date_string, self.week_day_string+", "+ self.year_string)
        else:
            self.daylabel = DayLabel(self.week_day_string, self.date_string+", "+ self.year_string)
        self.daylabel.connect("button-press-event", self.click)

        self.daylabel.set_size_request(100, 60)
        evbox = gtk.EventBox()
        evbox.add(self.daylabel)
        evbox.set_size_request(100, 60)
        self.vbox.pack_start(evbox, False, False)
        try:
            self.connect("motion-notify-event", lambda x, y: evbox.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2)))
        except:
            pass

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
            self.emit("focus-day")

    def _init_events(self):
        for w in self.view:
            if not w == pinbox:
                self.view.remove(w)
        for period in self._periods:
            part = DayPartWidget(period[0], period[1], period[2])
            self.view.pack_start(part, False, False)

class CategoryBox(gtk.VBox):

    def __init__(self, category, events):
        super(CategoryBox, self).__init__()

        self.view = gtk.VBox(True)
        for event in events:
            item = Item(event)
            hbox = gtk.HBox ()
            label = gtk.Label("")
            hbox.pack_start(label, False, False, 7)
            hbox.pack_start(item, True, True, 0)
            self.view.pack_start(hbox, False, False, 0)
            hbox.show()
            label.show()

        # If this isn't a set of ungrouped events, give it a label
        if category:
            # Place the items into a box and simulate left padding
            self.box = gtk.HBox()
            label = gtk.Label("")
            self.box.pack_start(label, False, False, 7)
            self.box.pack_start(self.view)
            self.pack_end(self.box)

            # Add the title button
            self.btn = CategoryButton(category, len(events))
            self.btn.connect("toggle", self.on_toggle)
            hbox = gtk.HBox ()
            lbl = gtk.Label("")
            hbox.pack_start(lbl, False, False, 8)
            hbox.pack_start(self.btn, True, True, 0)
            self.pack_start(hbox, False, False)

            self.show()
            hbox.show_all()
            label.show_all()
            self.btn.show()
            self.view.show()

        else:
            self.box = self.view
            self.pack_end(self.box)
            self.box.show()
            self.show()


    def on_toggle(self, view, bool):
        if bool:
            self.box.show()
        else:
            self.box.hide()
        pinbox.show_all()

class DayLabel(gtk.DrawingArea):

    __events__ = (gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON_MOTION_MASK |
                  gtk.gdk.POINTER_MOTION_HINT_MASK | gtk.gdk.BUTTON_RELEASE_MASK |
                  gtk.gdk.BUTTON_PRESS_MASK)

    def __init__(self, day, date):
        if day == _("Today"):
            self.leading = True
        else:
            self.leading = False
        super(DayLabel, self).__init__()
        self.date = date
        self.day = day
        self.set_events(self.__events__)
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
        gc = self.style.text_gc[gtk.STATE_SELECTED if self.leading else gtk.STATE_INSENSITIVE]
        layout = widget.create_pango_layout(self.date)
        layout.set_font_description(pango.FontDescription(self.font_name + " 10"))
        w, h = layout.get_pixel_size()
        widget.window.draw_layout(gc, (event.area.width-w)/2, lastfontheight, layout)

    def draw(self, widget, event, context):
        if self.leading:
            bg = self.style.bg[3]
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
    def __init__(self, side = 0, leading = False):
        super(DayButton, self).__init__()
        self.set_events(gtk.gdk.ENTER_NOTIFY_MASK | gtk.gdk.LEAVE_NOTIFY_MASK | gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK |
                        gtk.gdk.BUTTON_PRESS_MASK)
        self.set_flags(gtk.CAN_FOCUS)
        self.leading = leading
        self.side = side
        self.connect("button_press_event", self.on_press)
        self.connect("button_release_event", self.clicked_sender)
        self.connect("key_press_event", self.keyboard_clicked_sender)
        self.connect("enter_notify_event", self.on_hover, True)
        self.connect("leave_notify_event", self.on_hover, False)
        self.connect("expose_event", self.expose)
        self.connect("style-set", self.change_style)
        self.set_size_request(20, -1)

    def set_sensitive(self, case):
        self.sensitive = case
        self.queue_draw()

    def on_hover(self, widget, event, switch):
        self.hover = switch
        self.queue_draw()

    def on_press(self, widget, event):
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
        self.bg_color = logwidget.get_gtk_rgba(self.style, "bg", 0)
        self.header_color = logwidget.get_gtk_rgba(self.style, "bg", 0, 1.25)
        self.leading_header_color = logwidget.get_gtk_rgba(self.style, "bg", 3)
        self.internal_color = logwidget.get_gtk_rgba(self.style, "bg", 0, 1.02)
        self.arrow_color = logwidget.get_gtk_rgba(self.style, "text", 0, 0.6)
        self.arrow_color_selected = logwidget.get_gtk_rgba(self.style, "bg", 3)
        self.arrow_color_insensitive = logwidget.get_gtk_rgba(self.style, "text", 4)

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
        self.events = []
        for widget in self.view:
            self.view.remove(widget)

        if self == pinbox:
            box = CategoryBox(None, events)
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
                pass
            else:
                # Make the group title, etc. visible
                self.show()

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
        try:
            pinbox.show_all()
        except:
            pass

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
        self.show_all()

class DayPartWidget(EventGroup):

    def __init__(self, title, start, end):
        # Setup event criteria for querying
        self.event_timerange = [start * 1000, end * 1000]
        self.event_templates = (
            Event.new_for_values(interpretation=Interpretation.VISIT_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.CREATE_EVENT.uri),
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
