# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Randal Barlow
# Copyright © 2010 Markus Korn
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
import datetime
import calendar


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

        return (min(red, 1), min(green, 1), min(blue, 1), 1)
    else: raise TypeError("Not a valid gtk.gdk.Color")


class CairoHistogram(gtk.DrawingArea):
    """
    A histogram which is represented by a list of dimensions and dates
    """
    padding = 2
    ypad = 0
    wcolumn = 9
    xincrement = wcolumn + padding
    max_width = xincrement
    column_radius = 0.1
    font_size = 10
    
    datastore = None
    selected_range = 0
    highlighted = []
    __calbacks = None
    
    bg_color = (1, 1, 1, 1)
    column_color_normal =  (1, 1, 1, 1)
    column_color_selected = (1, 1, 1, 1)
    column_color_alternative = (1, 1, 1, 1)
    font_color = (0, 0, 0, 0)
    stroke_color = (1, 1, 1, 0)

    __gsignals__ = {
        # the index of the first selected item in the datastore.
        "selection-set": (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,(gobject.TYPE_INT,)),
        "data-updated":  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,())
        }

    def __init__(self, datastore = None, selected_range = 0):
        """

        Arguments:
        - datastore: The.CairoHistograms two dimensional list of dates and nitems
        - selected_range: the number of days displayed at once
        """
        super(CairoHistogram, self).__init__()
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self._expose_handler_id = self.connect("expose_event", self.expose)
        self.connect("button-press-event", self.clicked)
        self.font_name = self.style.font_desc.get_family()
        self.set_data(datastore if datastore else [], draw = False)
        self.selected_range = selected_range
        self.connect("style-set", self.change_style)
        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.query_tooltip)
        self._saved_tooltip_location = None
        
    def reconnect_expose(self, *args):
        """ disconnects the current expose_event handler and connects to
        a new one with given arguments
        """
        self.disconnect(self._expose_handler_id)
        self._expose_handler_id = self.connect("expose_event", self.expose, *args)
        
    def query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        location = self.get_data_index_from_cartesian(x, y)
        if location != self._saved_tooltip_location:
            # don't show the previous tooltip if we moved to another
            # location
            self._saved_tooltip_location = location
            return False
        try:
            timestamp, count = self.datastore[location]
        except IndexError:
            # there is no bar for at this location
            # don't show a tooltip
            return False
        date = datetime.date.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        tooltip.set_text("%s (%i)" %(date, count))
        return True
    
    def change_style(self, widget, *args, **kwargs):
        self.bg_color = get_gtk_rgba(self.style, "text", 1)
        self.column_color_normal =  get_gtk_rgba(self.style, "text", 4, 1.17)
        self.column_color_selected = get_gtk_rgba(self.style, "bg", 3)
        self.column_color_selected_alternative = (0, 0.8, 0.2, 1)
        self.column_color_alternative = (1, 0.54, 0.07, 1)
        fg = self.style.fg[gtk.STATE_NORMAL]
        bg = self.style.bg[gtk.STATE_NORMAL]
        self.font_color = get_gtk_rgba(self.style, "text", 4)
        self.stroke_color = (0.2,0.2,0.2,0.7)

    def set_selected_range(self, selected_range):
        """
        Set the number of days to be colored as selected
        """
        self.selected_range = selected_range

    set_dayrange = set_selected_range # Legacy compatibility

    def set_data(self, datastore = None, draw = True):
        """
        Sets the objects datastore attribute or calls update() on the current datastore object
        then queues a draw
        """
        if datastore != None and isinstance(datastore, list):
            self.datastore = datastore
            self.largest = 1
            for date, nitems in self.datastore:
                if nitems > self.largest: self.largest = nitems
            self.max_width = self.xincrement + (self.xincrement *len(datastore))
        elif datastore != None and not isinstance(datastore, list):
            raise TypeError("Datastore is not a list")
        if draw:
            self.queue_draw()
        self.emit("data-updated")

    def get_data(self):
        return self.datastore
    
    def expose(self, widget, event, selected = None, highlighted = None):
        # Default hilight to the last items
        if selected == None:
            selected = range(len(self.datastore))[-self.selected_range:]
        elif isinstance(selected, int):
            selected = range(selected, selected + self.selected_range)
        elif isinstance(selected, list) and len(selected) == 0:
            selected = [-1] # Disable color
        
        context = widget.window.cairo_create()
        # Set the source to the background color
        
        context.set_source_rgba(*self.bg_color)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        # set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()
        x = self.xincrement
        y = event.area.height

        months_positions = []
        i = 0
        for date, nitems in self.datastore:
            if check_for_new_month(date):
                months_positions += [(date, x)]
            if len(self.highlighted) > 0 and i >= self.highlighted[0] and i <= self.highlighted[-1] and i in self.highlighted: 
                color = self.column_color_selected_alternative if i in selected else self.column_color_alternative
            elif i >= selected[0] and i <= selected[-1] and i in selected:
                color = self.column_color_selected
            else:
                color = self.column_color_normal
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

        y = maxheight - height
        # Draw
        context.set_source_rgba(*color)
        context.move_to(x + self.column_radius, y)
        context.new_sub_path()
        if nitems > 4:
            context.arc(self.column_radius + x, self.column_radius + y, self.column_radius, math.pi, 3 * math.pi /2)
            context.arc(x + self.wcolumn - self.column_radius, self.column_radius + y, self.column_radius, 3 * math.pi / 2, 0)
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
        context.set_source_rgba(*self.stroke_color)
        
        context.set_line_width(1)
        context.move_to(x+1, 0)
        context.line_to(x+1, height)
        context.stroke()

        context.set_source_rgba(*self.font_color)
        
        context.select_font_face(self.font_name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(self.font_size)

        date = datetime.date.fromtimestamp(date)
        month = calendar.month_name[date.month]

        date = "%s %d" % (month, date.year)
        xbearing, ybearing, width, oheight, xadvance, yadvance = context.text_extents(date)
        context.move_to(x + 8, oheight+2)
        context.show_text(date)

    def set_selection(self, i):
        self.reconnect_expose(i)
        self.queue_draw()
        if isinstance(i, int):
            self.emit("selection-set", max(i, 0))
        elif isinstance(i, list) and len(i) > 0:
            self.emit("selection-set", max(i[0], 0))

    def set_highlighted(self, highlighted):
        if isinstance(highlighted, list):
            self.highlighted = highlighted
        else: raise TypeError("highlighted is not a list")
        self.reconnect_expose()
        self.queue_draw()

    def clear_highlighted(self):
        self.highlighted = []
        self.reconnect_expose()
        self.queue_draw()
       
    def add_selection_callback(self, callback):
        """
        add a callback for clicked to call when a item is clicked. 
        clicked passes this widget, a datastore list, and i to the function
        """
        if callable(callback):
            if not self.__calbacks:
                self.__calbacks = [callback]
            elif isinstance(self.__calbacks, list):
                self.__calbacks.append(callback)
        else:
            raise TypeError("Callback is not a function")

    def get_data_index_from_cartesian(self, x, y):
        return int((x - self.xincrement) / self.xincrement)

    def clicked(self, widget, event, *args, **kwargs):
        """Handles click events

        By wrapping this and using the returned location you can do nifty stuff
        with the datastore object

        Calls a calback set by connect_selection_callback
        """
        location = self.get_data_index_from_cartesian(event.x, event.y)
        self.reconnect_expose(max(location - self.selected_range + 1, 0))
        self.queue_draw()
        self.emit("selection-set", max(location - self.selected_range + 1, 0))
        if isinstance(self.__calbacks, list):
            for callback in self.__calbacks:
                if callable(callback):
                    callback(self, self.datastore, location)


class JournalHistogram(CairoHistogram):
    """
    A subclass of CairoHistogram with theming to fit into Journal
    """
    column_radius = 1.3
    font_size = 12
    ypad = 25
    def change_style(self, widget, *args, **kwargs):
        self.bg_color = get_gtk_rgba(self.style, "bg", 0, 1.02)
        self.column_color_normal =  get_gtk_rgba(self.style, "text", 1)
        self.column_color_selected = get_gtk_rgba(self.style, "bg", 3)
        self.column_color_selected_alternative = get_gtk_rgba(self.style, "bg", 3, 0.7)
        self.column_color_alternative = get_gtk_rgba(self.style, "text", 2)
        fg = self.style.fg[gtk.STATE_NORMAL]
        bg = self.style.bg[gtk.STATE_NORMAL]
        self.font_color = ((2*bg.red+fg.red)/3/65535.0, (2*bg.green+fg.green)/3/65535.0, (2*bg.blue+fg.blue)/3/65535.0, 1)

    def draw_month(self, context, x, height, date):
        """
        Draws a line signifying the start of a month
        """
        fg = self.style.fg[gtk.STATE_NORMAL]
        bg = self.style.bg[gtk.STATE_NORMAL]
        context.set_source_rgba(*self.font_color)
        
        context.set_line_width(2)
        context.move_to(x+1, height - self.ypad)
        context.line_to(x+1, height - self.ypad/3)

        context.stroke()
        context.select_font_face(self.font_name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(self.font_size)

        date = datetime.date.fromtimestamp(date)
        month = calendar.month_name[date.month]

        date = "%s %d" % (month, date.year)
        xbearing, ybearing, width, oheight, xadvance, yadvance = context.text_extents(date)
        context.move_to(x + 8, height - self.ypad/3)
        context.show_text(date)


class HistogramWidget(gtk.HBox):
    """
    A container for a CairoHistogram
    """
    def __init__(self):
        super(gtk.HBox, self).__init__()
        viewport = gtk.Viewport()
        #viewport.set_shadow_type(gtk.SHADOW_IN)
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.set_size_request(600,70)
        #self.histogram = CairoHistogram()
        self.histogram = JournalHistogram()

        # viewport work
        viewport.add(self.histogram)
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
                   self.histogram, -3*self.histogram.xincrement)
        b2.connect("clicked", self.scroll_viewport, viewport,
                   self.histogram, 3*self.histogram.xincrement)
        self.histogram.connect("data-updated", self.scroll_to_end)
        self.pack_start(b1, False, False)
        self.pack_start(align, True, True, 3)
        self.pack_end(b2, False, False)
        # Prepare the adjustment
        self.adjustment = viewport.get_hadjustment()
        self.adjustment.set_value(1) # Needs to be set twice to work
        self.adjustment.set_value(self.histogram.max_width - self.adjustment.page_size)

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
        self.adjustment.set_value(1)
        self.adjustment.set_value(self.histogram.max_width - self.adjustment.page_size)


cal = HistogramWidget()

