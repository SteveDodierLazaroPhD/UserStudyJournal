# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Randal Barlow
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

"""
Takes a two dementional tuple or list and turns it into a graph based on
datastore[n][1]'s size

# datastore = [[raw_date, nitems]]
"""

import cairo
import gobject
import gtk
import math
import time
import datetime

month_dict  = {1:"January", 2:"February", 3:"March", 4:"April",
               5:"May", 6:"June", 7:"July", 8:"August", 9:"September",
               10:"October", 11:"November", 12:"December",
               }

def check_for_new_month(date):
    if datetime.date.fromtimestamp(date).day == 1:
        return True
    return False

def get_gtk_rgba(style, palette, i, shade = 1):
    """Takes a gtk style and returns a RGB tuple

    Arguments:
    - style: a gtk_style object
    - palette: a string representing the palette you want to pull a color from
        Example: "bg", "fg"
    - shade: how much you want to shade the color
    """
    f = lambda num: (num/65535.0) * shade

    color = getattr(style, palette)[i]
    if isinstance(color, gtk.gdk.Color):
        red = f(color.red)
        green = f(color.green)
        blue = f(color.blue)

        return (red if red < 1 else 1,
                green if green < 1 else 1,
                blue if blue < 1 else 1, 1)
    else: raise TypeError("Not a valid gtk.gdk.Color")


class CairoCalendar(gtk.DrawingArea):
    """
    A calendar which is represented by a list of dimensions and dates
    """
    padding = 2
    ypad = 25
    wcolumn = 9
    xincrement = wcolumn + padding
    max_width = xincrement
    datastore = None
    __gsignals__ = {
        "selection-set": (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,()),
        "data-updated":  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,())
        }

    def __init__(self, datastore, selected_range=0):
        """

        Arguments:
        - datastore: The.CairoCalendars two dimensional list of dates and nitems
        - selected_range: the number of days displayed at once
        """
        super(CairoCalendar, self).__init__()
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.connect("expose_event", self.expose)
        self.connect("button-press-event", self.clicked)
        self.font_name = self.style.font_desc.get_family()
        self.update_data(datastore, draw = False)
        self.selected_range = selected_range

    def set_selected_range(self, selected_range):
        """
        Set the number of days to be colored as selected
        """
        self.selected_range = selected_range

    set_dayrange = set_selected_range # Legacy compatibility

    def update_data(self, datastore = None, draw = True):
        """
        Sets the objects datastore attribute or calls update() on the current datastore object
        then queues a draw
        """
        if datastore:
            self.datastore = datastore
            self.largest = 1
            for date, nitems in self.datastore:
                if nitems > self.largest: self.largest = nitems
            self.max_width = self.xincrement + (self.xincrement *len(datastore))
        else:
            self.datastore.update()
        if draw:
            self.queue_draw()
        self.emit("data-updated")

    def expose(self, widget, event, selected = None, alternative_highlight = False):
        # Default hilight to the last items
        if selected == None:
            selected = range(len(self.datastore))[-self.selected_range:]
        elif isinstance(selected, int):
            selected = range(selected, selected + self.selected_range)
        elif isinstance(selected, list) and len(selected) == 0:
            selected = [-1] # Disable color
        
        context = widget.window.cairo_create()
        # Set the source to the background color
        color = get_gtk_rgba(self.style, "bg", 0, 1.02)
        context.set_source_rgba(*color)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        # set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()
        x = self.xincrement
        y = event.area.height

        normalcolor =  get_gtk_rgba(self.style, "text", 1)
        selectedcolor = get_gtk_rgba(self.style, "bg", 3)
        pinnedcolor = get_gtk_rgba(self.style, "text", 2)

        months_positions = []

        i = 0
        for date, nitems in self.datastore:
            if check_for_new_month(date):
                months_positions += [(date, x)]
            if i >= selected[0] and i <= selected[-1] and i in selected:
                if alternative_highlight:
                    color = pinnedcolor
                else:
                    color = selectedcolor
            else:
                color = normalcolor
            self.draw_column(context, x, event.area.height, nitems, color)
            x += self.xincrement
            i += 1


        # Draw over the selected items
        if x > event.area.width: # Check for resize
            self.set_size_request(x+self.xincrement, event.area.height)
        for date, line in months_positions:
            self.draw_month(context, line - self.padding, event.area.height, date)
        self.max_width = x # remove me
        
    def draw_column(self, context, x, maxheight, nitems, color):
        """
        Draws a columns at x with height based on nitems, and maxheight

        Arguments:
        - context: The drawingarea's cairo context from the expose event
        - x: The current position in the image
        - maxheight: The event areas height
        - nitems: The number of items in the column to be drawn
        - color: A RGBA tuple
            Example: (0.3, 0.4, 0.8, 1)
        """
        if nitems < 2:
            nitems = 2
        maxheight = maxheight - self.ypad
        height = int(((float(nitems)/self.largest)*(maxheight-2))) - 6

        if height < 2:
            height = 2

        radius = 1.3
        y = maxheight - height
        # Draw
        context.set_source_rgba(*color)
        context.move_to(x + radius, y)
        context.new_sub_path()
        if nitems > 4:
            context.arc(radius + x, radius + y, radius, math.pi, 3 * math.pi /2)
            context.arc(x + self.wcolumn - radius, radius + y, radius, 3 * math.pi / 2, 0)
            context.rectangle(x, y, self.wcolumn, height)
        else:
            context.rectangle(x, y, self.wcolumn, height)
        context.close_path()
        context.fill()


    def draw_month(self, context, x, height, date):
        """
        Draws a line signifying the start of a month
        """
        fg = self.style.fg[gtk.STATE_NORMAL]
        bg = self.style.bg[gtk.STATE_NORMAL]
        red, green, blue = (2*bg.red+fg.red)/3/65535.0, (2*bg.green+fg.green)/3/65535.0, (2*bg.blue+fg.blue)/3/65535.0
        context.set_source_rgba(red, green, blue, 1)
        
        context.set_line_width(2)
        context.move_to(x+1, height - self.ypad)
        context.line_to(x+1, height - self.ypad/3)

        context.stroke()
        context.select_font_face(self.font_name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(12)

        date = datetime.date.fromtimestamp(date)
        month  = month_dict[date.month]

        date = "%s %d" % (month, date.year)
        xbearing, ybearing, width, oheight, xadvance, yadvance = context.text_extents(date)
        context.move_to(x + 8, height - self.ypad/3)
        context.show_text(date)

    def set_selection(self, i, alternative_highlight = False):
        self.connect("expose_event", self.expose, i, alternative_highlight)
        self.queue_draw()
        self.emit("selection-set")

    def selection_callback(self, datastore, i):
        """
        A demo callback, either rewrite this or use connect_selection_callback
        """
        print "day %s has %s events\n" % (datastore[i][0], datastore[i][1])

    def connect_selection_callback(self, callback):
        """
        Connect a callback for clicked to call. clicked passes this widget,
        a datastore list, and i to the function
        """
        if callable(callback):
            self.selection_callback = callback
        else:
            raise TypeError("Callback is not a function")

    def clicked(self, widget, event, *args, **kwargs):
        """Handles click events

        By wrapping this and using the returned location you can do nifty stuff
        with the datastore object

        Calls a calback set by connect_selection_callback
        """
        location = int((event.x - self.xincrement) / self.xincrement)
        self.connect("expose_event", self.expose, max(min(location - 2,
            len(self.datastore) - self.selected_range), 0))
        self.queue_draw()
        self.emit("selection-set")
        if callable(self.selection_callback):
            self.selection_callback(self.datastore, location)


class ImmediateCalendar(gtk.DrawingArea):
    padding = 2
    ypad = 25
    wcolumn = 9
    xincrement = wcolumn + padding
    max_width = xincrement

    def __init__(self, datastore):
        super(ImmediateCalendar, self).__init__()
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.connect("expose_event", self.expose)
        self.connect("button-press-event", self.clicked)
        self.font_name = self.style.font_desc.get_family()
        gobject.signal_new("iselection-set",ImmediateCalendar,
                           gobject.SIGNAL_RUN_LAST,
                           gobject.TYPE_NONE,())
        gobject.signal_new("idata-updated",ImmediateCalendar,
                           gobject.SIGNAL_RUN_LAST,
                           gobject.TYPE_NONE,())
        self.update_data(datastore, draw = False)
        
    def update_data(self, datastore = None, draw = True):
        """
        Sets the objects datastore attribute or calls update() on the current datastore object
        then queues a draw
        """
        if datastore:
            self.datastore = datastore
            self.largest = 1
            for date, nitems in self.datastore:
                if nitems > self.largest: self.largest = nitems
            self.max_width = self.xincrement + (self.xincrement *len(datastore))
        else:
            self.datastore.update()
        if draw:
            self.queue_draw()
        self.emit("data-updated")

    def expose(self, widget, event, selected = False):
        # Default hilight to the last items
        context = widget.window.cairo_create()
        # Set the source to the background color
        color = get_gtk_rgba(self.style, "bg", 0, 1.02)
        context.set_source_rgba(*color)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        # set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()
        
        x = self.xincrement
        y = event.area.height
        if selected == True:
            color = get_gtk_rgba(self.style, "bg", 3)
        else:
            color =  get_gtk_rgba(self.style, "text", 1)

        for date, nitems in self.datastore:
            self.draw_column(context, x, event.area.height, nitems, color)
            x += self.xincrement
        
        # widget size
        if x > event.area.width: # Check for resize
            self.set_size_request(x+self.xincrement, event.area.height)
        self.max_width = x # remove me

    def draw_column(self, context, x, maxheight, nitems, color):
        """
        Draws a columns at x with height based on nitems, and maxheight

        Arguments:
        - context: The drawingarea's cairo context from the expose event
        - x: The current position in the image
        - maxheight: The event areas height
        - nitems: The number of items in the column to be drawn
        - color: A RGBA tuple
            Example: (0.3, 0.4, 0.8, 1)
        """
        if nitems < 2:
            nitems = 2
        maxheight = maxheight - self.ypad
        height = int(((float(nitems)/self.largest)*(maxheight-2))) - 6

        if height < 2:
            height = 2

        radius = 1.3
        y = maxheight - height
        # Draw
        context.set_source_rgba(*color)
        context.move_to(x + radius, y)
        context.new_sub_path()
        if nitems > 4:
            context.arc(radius + x, radius + y, radius, math.pi, 3 * math.pi /2)
            context.arc(x + self.wcolumn - radius, radius + y, radius, 3 * math.pi / 2, 0)
            context.rectangle(x, y, self.wcolumn, height)
        else:
            context.rectangle(x, y, self.wcolumn, height)
        context.close_path()
        context.fill()

    def selection_callback(self, datastore, i):
        """
        A demo callback, either rewrite this or use connect_selection_callback
        """
        print "day %s has %s events\n" % (datastore[i][0], datastore[i][1])

    def connect_selection_callback(self, callback):
        """
        Connect a callback for clicked to call. clicked passes this widget,
        a datastore list, and i to the function
        """
        if callable(callback):
            self.selection_callback = callback
        else:
            raise TypeError("Callback is not a function")

    def clicked(self, widget, event, *args, **kwargs):
        """Handles click events

        By wrapping this and using the returned location you can do nifty stuff
        with the datastore object

        Calls a calback set by connect_selection_callback
        """
        self.connect("expose_event", self.expose, True)
        self.queue_draw()
        self.emit("selection-set")
        if callable(self.selection_callback):
            self.selection_callback(self.datastore, 0)

class CalendarWidget(gtk.HBox):
    """
    A container for a CairoCalendar
    """
    def __init__(self):
        super(gtk.HBox, self).__init__()
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.set_size_request(600,70)
        self.calendar = CairoCalendar([[0, 0]])
        #mini cal setup
        #self.immediatecalendar = ImmediateCalendar([[0,0]])
        #self.immediatecalendar.set_size_request(70,70)

        # viewport work
        viewport.add(self.calendar)
        # Aligning work
        align = gtk.Alignment(0,0,1,1)
        align.set_padding(0, 0, 0, 0)
        align.add(viewport)
        # Back button
        b1 = gtk.Button()
        b1.add(gtk.Arrow(gtk.ARROW_LEFT, gtk.SHADOW_NONE))
        b1.set_relief(gtk.RELIEF_NONE)
        b1.set_focus_on_click(False)
        # Forward button
        b2 = gtk.Button()
        b2.add(gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_NONE))
        b2.set_relief(gtk.RELIEF_NONE)
        b2.set_focus_on_click(False)

        b1.connect("clicked", self.scroll_viewport, viewport,
                   self.calendar, -3*self.calendar.xincrement)
        b2.connect("clicked", self.scroll_viewport, viewport,
                   self.calendar, 3*self.calendar.xincrement)
        self.calendar.connect("data-updated", self.scroll_to_end)

        self.pack_start(b1, False, False)
        self.pack_start(align, True, True, 3)
        #self.pack_start(self.immediatecalendar, False, False)
        self.pack_end(b2, False, False)
        # Prepare the adjustment
        self.adjustment = viewport.get_hadjustment()
        #self.adjustment.set_upper(self.calendar.max_width)
        self.adjustment.set_value(1) # Needs to be set twice to work
        self.adjustment.set_value(self.calendar.max_width - self.adjustment.page_size)

    def scroll_viewport(self, widget, viewport, scroll_cal, value, *args, **kwargs):
        """Broken for now
        """
        adjustment = viewport.get_hadjustment()
        page_size = adjustment.get_page_size()
        if value < 1:
            newadjval = 0 if value > adjustment.value else (adjustment.value + value)
        elif adjustment.value + page_size > scroll_cal.max_width - value:
            newadjval = scroll_cal.max_width - page_size
        else:
            newadjval = adjustment.value + value
        adjustment.set_value(newadjval)

    def scroll_to_end(self, *args, **kwargs):
        #self.adjustment.set_upper(self.calendar.max_width)
        self.adjustment.set_value(1)
        self.adjustment.set_value(self.calendar.max_width - self.adjustment.page_size)

cal = CalendarWidget()
