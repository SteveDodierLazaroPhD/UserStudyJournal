# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
# Copyright © 2010 Markus Korn
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

"""
Takes a two dementional list of ints and turns it into a graph based on
the first value a int date, and the second value the number of items on that date
where items are
datastore = []
datastore.append(time, nitems)
CairoHistogram.set_datastore(datastore)
"""
import datetime
import cairo
import calendar
import gettext
import gobject
import gtk
from math import pi as PI
import pango
from common import *


def get_gc_from_colormap(widget, shade):
    """
    Gets a gtk.gdk.GC and modifies the color by shade
    """
    gc = widget.style.text_gc[gtk.STATE_INSENSITIVE]
    if gc:
        color = widget.style.text[4]
        color = shade_gdk_color(color, shade)
        gc.set_rgb_fg_color(color)
    return gc


class CairoHistogram(gtk.DrawingArea):
    """
    A histogram which is represented by a list of dates, and nitems.

    There are a few maintenance issues due to the movement abilities. The widget
    currently is able to capture motion events when the mouse is outside
    the widget and the button is pressed if it was initially pressed inside
    the widget. This event mask magic leaves a few flaws open.
    """
    _selected = (0,)
    padding = 2
    bottom_padding = 23
    top_padding = 2
    wcolumn = 12
    xincrement = wcolumn + padding
    start_x_padding = 2
    max_width = xincrement
    column_radius = 0
    stroke_width = 1
    stroke_offset = 0
    min_column_height = 4
    max_column_height = 101
    gc = None
    pangofont = None
    _disable_mouse_motion = False
    selected_range = 0
    _highlighted = tuple()
    _last_location = -1
    _single_day_only = False
    colors = {
        "bg" : (1, 1, 1, 1),
        "base" : (1, 1, 1, 1),
        "column_normal" :  (1, 1, 1, 1),
        "column_selected" : (1, 1, 1, 1),
        "column_alternative" : (1, 1, 1, 1),
        "column_selected_alternative" : (1, 1, 1, 1),
        "font_color" : (0, 0, 0, 0),
        "stroke" : (1, 1, 1, 0),
        "shadow" : (1, 1, 1, 0),
        }

    # Today button stuff
    _today_width = 0
    _today_text = ""
    _today_area = None
    _today_hover = False

    _datastore = None
    __gsignals__ = {
        # the index of the first selected item in the datastore.
        "selection-set" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                           (gobject.TYPE_INT,gobject.TYPE_INT)),
        "data-updated" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,()),
        "column_clicked" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                            (gobject.TYPE_INT,))
        }
    _connections = {"style-set": "change_style",
                       "expose_event": "_expose",
                       "button_press_event": "mouse_press_interaction",
                       "motion_notify_event": "mouse_motion_interaction",
                       "key_press_event": "keyboard_interaction",
                       "scroll-event" : "mouse_scroll_interaction",
                       "selection-set": "check_for_today",
                       }
    _events = (gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON_MOTION_MASK |
                  gtk.gdk.POINTER_MOTION_HINT_MASK | gtk.gdk.BUTTON_RELEASE_MASK |
                  gtk.gdk.BUTTON_PRESS_MASK)

    def __init__(self, datastore = None, selected_range = 0):
        """
        Arguments:
        - datastore: The.CairoHistograms two dimensional list of dates and nitems
        - selected_range: the number of days displayed at once
        """
        super(CairoHistogram, self).__init__()
        self.set_events(self._events)
        self.set_flags(gtk.CAN_FOCUS)
        for key, val in self._connections.iteritems():
            self.connect(key, getattr(self, val))
        self.font_name = self.style.font_desc.get_family()
        self.set_datastore(datastore if datastore else [], draw = False)
        self.selected_range = selected_range

    def change_style(self, widget, old_style):
        """
        Sets the widgets style and coloring
        """
        self.colors = self.colors.copy()
        self.colors["bg"] = get_gtk_rgba(self.style, "bg", 0)
        self.colors["base"] = get_gtk_rgba(self.style, "base", 0)
        self.colors["column_normal"] =  get_gtk_rgba(self.style, "text", 4, 1.17)
        self.colors["column_selected"] = get_gtk_rgba(self.style, "bg", 3)
        pal = get_gtk_rgba(self.style, "bg", 3, 1.2)
        self.colors["column_alternative"] = (pal[2], pal[1], pal[0], 1)
        self.colors["column_selected_alternative"] = get_gtk_rgba(self.style, "bg", 3, 0.6)
        self.colors["stroke"] = get_gtk_rgba(self.style, "text", 4)
        self.colors["shadow"] = get_gtk_rgba(self.style, "text", 4)
        self.font_size = self.style.font_desc.get_size()/1024
        self.pangofont = pango.FontDescription(self.font_name + " %d" % self.font_size)
        self.pangofont.set_weight(pango.WEIGHT_BOLD)
        self.bottom_padding = self.font_size + 9 + widget.style.ythickness
        self.gc = get_gc_from_colormap(widget, 0.6)

    def set_selected_range(self, selected_range):
        """
        Set the number of days to be colored as selected

        Arguments:
        - selected_range: the range to be used when setting selected coloring
        """
        self.selected_range = selected_range
        return True

    def set_datastore(self, datastore, draw = True):
        """
        Sets the objects datastore attribute using a list

        Arguments:
        -datastore: A list that is comprised of rows containing
          a int time and a int nitems
        """
        if isinstance(datastore, list):
            self._datastore = datastore
            self.largest = 1
            for date, nitems in self._datastore:
                if nitems > self.largest: self.largest = nitems
            if self.largest > self.max_column_height: self.largest = self.max_column_height
            self.max_width = self.xincrement + (self.xincrement *len(datastore))
        else:
            raise TypeError("Datastore is not a <list>")
        self.emit("data-updated")
        self.set_selected(len(datastore) - self.selected_range)

    def get_datastore(self):
        return self._datastore

    def prepend_data(self, newdatastore):
        """
        Adds the items of a new list before the items of the current datastore

        Arguments:
        - newdatastore: the new list to be prepended

        ## WARNING SELECTION WILL CHANGE WHEN DOING THIS TO BE FIXED ##
        """
        selected = self.get_selected()[-1]
        self._datastore = newdatastore + self._datastore
        self.queue_draw()
        self.set_selected(len(newdatastore) + selected)

    def _expose(self, widget, event):
        """
        The major drawing method that the expose event calls directly

        Arguments:
        - widget: the widget
        - event: a gtk event with x and y values
        """
        context = widget.window.cairo_create()
        self.expose(widget, event, context)
        if len(self._today_text):
            self.draw_today(widget, event, context)

    def expose(self, widget, event, context):
        """
        The minor drawing method

        Arguments:
        - widget: the widget
        - event: a gtk event with x and y values
        - context: The drawingarea's cairo context from the expose event
        """
        if not self.pangofont:
            self.pangofont = pango.FontDescription(self.font_name + " %d" % self.font_size)
            self.pangofont.set_weight(pango.WEIGHT_BOLD)
        if not self.gc:
            self.gc = get_gc_from_colormap(widget, 0.6)
        context.set_source_rgba(*self.colors["base"])
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()
        context.set_source_rgba(*self.colors["bg"])
        context.rectangle(event.area.x, event.area.height - self.bottom_padding, event.area.width, event.area.height)
        context.fill()
        self.draw_columns_from_datastore(context, event, self.get_selected())
        context.set_line_width(1)
        if type(self) == CairoHistogram:
            widget.style.paint_shadow(widget.window, gtk.STATE_NORMAL, gtk.SHADOW_IN,
                                      event.area, widget, "treeview", event.area.x, event.area.y,
                                      event.area.width, event.area.height - self.bottom_padding)
        if self.is_focus():
            widget.style.paint_focus(widget.window, gtk.STATE_NORMAL, event.area, widget, None, event.area.x, event.area.y,
                                     event.area.width, event.area.height - self.bottom_padding)

    def draw_today(self, widget, event, context):
        """
        """
        layout = widget.create_pango_layout(self._today_text)
        pangofont = pango.FontDescription(widget.font_name + " %d" % (widget.font_size - 1))
        if not widget.gc:
            widget.gc = get_gc_from_colormap(widget, 0.6)
        layout.set_font_description(pangofont)
        w, h = layout.get_pixel_size()
        self._today_width = w + 10
        self._today_area = (
            int(event.area.x + event.area.width - self._today_width),
            int(event.area.height - widget.bottom_padding + 2),
            self._today_width,
            widget.bottom_padding - 2)
        state = gtk.STATE_PRELIGHT
        shadow = gtk.SHADOW_OUT
        widget.style.paint_box(
            widget.window, state, shadow, event.area, widget, "button", *self._today_area)
        widget.window.draw_layout(
            widget.gc, int(event.area.x + event.area.width - w -5),
            int(event.area.height - widget.bottom_padding/2 - h/2), layout)

    def draw_columns_from_datastore(self, context, event, selected):
        """
        Draws columns from a datastore

        Arguments:
        - context: The drawingarea's cairo context from the expose event
        - event: a gtk event with x and y values
        - selected: a list of the selected columns
        """
        x = self.start_x_padding
        months_positions = []
        i = 0
        for date, nitems in self._datastore:
            if datetime.date.fromtimestamp(date).day == 1:
                months_positions += [(date, x)]
            if len(self._highlighted) > 0 and i >= self._highlighted[0] and i <= self._highlighted[-1] and i in self._highlighted:
                color = self.colors["column_selected_alternative"] if i in selected else self.colors["column_alternative"]
            elif not selected:
                color = self.colors["column_normal"]
            elif self._single_day_only  and i != selected[-1]:
                color = self.colors["column_normal"]
            elif i >= selected[0] and i <= selected[-1] and i in selected:
                color = self.colors["column_selected"]
            else:
                color = self.colors["column_normal"]
            self.draw_column(context, x, event.area.height, nitems, color)
            x += self.xincrement
            i += 1
        if x > event.area.width: # Check for resize
            self.set_size_request(x+self.xincrement, event.area.height)
        for date, xpos in months_positions:
            self.draw_month(context, xpos - self.padding, event.area.height, date)
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
        elif nitems > self.max_column_height:
            nitems = self.max_column_height
        maxheight = maxheight - self.bottom_padding
        height = int(((float(nitems)/self.largest)*(maxheight-2))) - self.top_padding
        if height < self.min_column_height:
            height = self.min_column_height
        y = maxheight - height
        context.set_source_rgba(*color)
        context.move_to(x + self.column_radius, y)
        context.new_sub_path()
        if nitems > 4:
            context.arc(self.column_radius + x, self.column_radius + y, self.column_radius, PI, 3 * PI /2)
            context.arc(x + self.wcolumn - self.column_radius, self.column_radius + y, self.column_radius, 3 * PI / 2, 0)
            context.rectangle(x, y + self.column_radius, self.wcolumn, height - self.column_radius)
        else:
            context.rectangle(x, y, self.wcolumn, height)
        context.close_path()
        context.fill()

    def draw_month(self, context, x, height, date):
        """
        Draws a line signifying the start of a month
        """
        context.set_source_rgba(*self.colors["stroke"])
        context.set_line_width(self.stroke_width)
        context.move_to(x+self.stroke_offset, 0)
        context.line_to(x+self.stroke_offset, height - self.bottom_padding)
        context.stroke()
        date = datetime.date.fromtimestamp(date)
        month = calendar.month_name[date.month]
        date = "%s %d" % (month, date.year)
        layout = self.create_pango_layout(date)
        layout.set_font_description(self.pangofont)
        w, h = layout.get_pixel_size()
        self.window.draw_layout(self.gc, int(x + 3), int(height - self.bottom_padding/2 - h/2), layout)

    def set_selected(self, i):
        """
        Set the selected items using a int or a list of the selections
        If you pass this method a int it will select the index + selected_range

        Emits:
         self._selected[0] and self._selected[-1]

        Arguments:
        - i: a list or a int where the int will select i + selected_range
        """
        if len(self._selected):
            if i == self._selected[0]:
                return False
        if isinstance(i, int):
            self._selected = range(i, i + self.selected_range)
            self.emit("selection-set", max(i, 0), max(i + self.selected_range - 1, 0))
        else: self._selected = (-1,)
        self.queue_draw()
        return True

    def get_selected(self):
        """
        returns a list of selected indices
        """
        return self._selected

    def clear_selection(self):
        """
        clears the selected items
        """
        self._selected = range(len(self._datastore))[-self.selected_range:]
        self.queue_draw()

    def set_highlighted(self, highlighted):
        """
        Sets the widgets which should be highlighted with an alternative color
        Argument:
        - highlighted: a list of indexes to be highlighted
        """
        if isinstance(highlighted, list):
            self._highlighted = highlighted
        else: raise TypeError("highlighted is not a list")
        self.queue_draw()

    def clear_highlighted(self):
        """Clears the highlighted color"""
        self._highlighted = []
        self.queue_draw()

    def set_single_day(self, choice):
        """
        Allows the cal to enter a mode where the trailing days are not selected but still kept
        """
        self._single_day_only = choice
        self.queue_draw()

    def get_datastore_index_from_cartesian(self, x, y):
        """
        Gets the datastore index from a x, y value
        """
        return int((x - self.start_x_padding) / self.xincrement)

    def keyboard_interaction(self, widget, event):
        if event.keyval in (gtk.keysyms.space, gtk.keysyms.Right, gtk.keysyms.Left, gtk.keysyms.BackSpace):
            i = self.get_selected()
            if isinstance(i, list) and len(i) > 0: i = i[-1]
            if event.keyval in (gtk.keysyms.space, gtk.keysyms.Right):
                i += 1
            elif event.keyval in (gtk.keysyms.Left, gtk.keysyms.BackSpace):
                i -= 1
            if i < len(self.get_datastore()):
                self.change_location(i)

    def mouse_motion_interaction(self, widget, event, *args, **kwargs):
        """
        Reacts to mouse moving (while pressed), and clicks
        """
        #if (event.state == gtk.gdk.BUTTON1_MASK and not self._disable_mouse_motion):
        location = min((self.get_datastore_index_from_cartesian(event.x, event.y), len(self._datastore) - 1))
        if location != self._last_location:
            self.change_location(location)
            self._last_location = location
            #return True
        return False

    def mouse_press_interaction(self, widget, event, *args, **kwargs):
        if (event.y > self.get_size_request()[1] - self.bottom_padding and
            event.y < self.get_size_request()[1]):
            return False
        location = min((self.get_datastore_index_from_cartesian(event.x, event.y), len(self._datastore) - 1))
        if location != self._last_location:
            self.change_location(location)
            self._last_location = location
        return True

    def mouse_scroll_interaction(self, widget, event):
        i = self.get_selected()[-1]
        if (event.direction in (gtk.gdk.SCROLL_UP, gtk.gdk.SCROLL_RIGHT)):
            if i+1< len(self.get_datastore()):
                self.change_location(i+1)
        elif (event.direction in (gtk.gdk.SCROLL_DOWN, gtk.gdk.SCROLL_LEFT)):
            if 0 <= i-1:
                self.change_location(i-1)

    def change_location(self, location):
        """
        Handles click events
        """
        if location < 0:
            return False
        self.set_selected(max(location - self.selected_range + 1, 0))
        self.emit("column_clicked", location)
        return True

    # Today stuff
    def check_for_today(self, widget, i, ii):
        """
        Changes today to a empty string if the selected item is not today
        """
        if ii == len(self.get_datastore())-1:
            self._today_text = ""
            self._today_area = None
        elif len(self._today_text) == 0:
            self._today_text = _("Today") + " »"
        self.queue_draw()
        return True


def _in_area(coord_x, coord_y, area):
    """check if some given X,Y coordinates are within an area.
    area is either None or a (top_left_x, top_left_y, width, height)-tuple"""
    if area is None:
        return False
    area_x, area_y, area_width, area_height = area
    return (area_x <= coord_x <= area_x + area_width) and \
        (area_y <= coord_y <= area_y + area_height)


def _in_area(coord_x, coord_y, area):
    """check if some given X,Y coordinates are within an area.
    area is either None or a (top_left_x, top_left_y, width, height)-tuple"""
    if area is None:
        return False
    area_x, area_y, area_width, area_height = area
    return (area_x <= coord_x <= area_x + area_width) and \
        (area_y <= coord_y <= area_y + area_height)

class TooltipEventBox(gtk.EventBox):
    """
    A event box housing the tool tip logic that can be used for a CairoHistogram.
    Otherwise it interferes with the scrubbing mask code
    """
    _saved_tooltip_location = None
    def __init__(self, histogram, container):
        super(TooltipEventBox, self).__init__()
        self.add(histogram)
        self.histogram = histogram
        self.container = container
        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.query_tooltip)

    def query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        if y < self.histogram.get_size_request()[1] - self.histogram.bottom_padding:
            location = self.histogram.get_datastore_index_from_cartesian(x, y)
            if location != self._saved_tooltip_location:
                # don't show the previous tooltip if we moved to another
                # location
                self._saved_tooltip_location = location
                return False
            try:
                timestamp, count = self.histogram.get_datastore()[location]
            except IndexError:
                # there is no bar for at this location
                # don't show a tooltip
                return False
            date = datetime.date.fromtimestamp(timestamp).strftime("%A, %d %B, %Y")
            tooltip.set_text("%s\n%i %s" % (date, count,
                                            gettext.ngettext("item", "items", count)))
        elif self.container.histogram._today_text and _in_area(x, y, self.container.histogram._today_area):
            tooltip.set_text(_("Click today to return to today"))
        else:
            return False
        return True


class JournalHistogram(CairoHistogram):
    """
    A subclass of CairoHistogram with theming to fit into Journal
    """
    padding = 2
    column_radius = 1.3
    top_padding = 6
    bottom_padding = 29
    wcolumn = 10
    xincrement = wcolumn + padding
    column_radius = 2
    stroke_width = 2
    stroke_offset = 1
    font_size = 12
    min_column_height = 2

    def change_style(self, widget, *args, **kwargs):
        self.colors = self.colors.copy()
        self.colors["bg"] = get_gtk_rgba(self.style, "bg", 0)
        self.colors["color"] = get_gtk_rgba(self.style, "base", 0)
        self.colors["column_normal"] =  get_gtk_rgba(self.style, "bg", 1)
        self.colors["column_selected"] = get_gtk_rgba(self.style, "bg", 3)
        self.colors["column_selected_alternative"] = get_gtk_rgba(self.style, "bg", 3, 0.7)
        self.colors["column_alternative"] = get_gtk_rgba(self.style, "text", 2)
        self.colors["stroke"] = get_gtk_rgba(self.style, "bg", 0)
        self.colors["shadow"] = get_gtk_rgba(self.style, "bg", 0, 0.98)
        self.font_size = self.style.font_desc.get_size()/1024
        self.bottom_padding = self.font_size + 9 + widget.style.ythickness
        self.gc = self.style.text_gc[gtk.STATE_NORMAL]
        self.pangofont = pango.FontDescription(self.font_name + " %d" % self.font_size)
        self.pangofont.set_weight(pango.WEIGHT_BOLD)


class HistogramWidget(gtk.Viewport):
    """
    A container for a CairoHistogram which allows you to scroll
    """


    def __init__(self, histo_type, size = (600, 75)):
        """
        Arguments:
        - histo_type = a CairoHistogram or a derivative
        """
        super(HistogramWidget, self).__init__()
        self.set_shadow_type(gtk.SHADOW_NONE)
        self.histogram = histo_type()
        self.eventbox = TooltipEventBox(self.histogram, self)
        self.set_size_request(*size)
        self.add(self.eventbox)
        self.histogram.connect("button_press_event", self.footer_clicked)
        self.histogram.connect("selection-set", self.scrubbing_fix)
        self.histogram.queue_draw()
        self.queue_draw()

    def footer_clicked(self, widget, event):
        """
        Handles all rejected clicks from bellow the histogram internal view and
        checks to see if they were inside of the today text
        """
        hadjustment = self.get_hadjustment()
        # Check for today button click
        if (widget._today_text and event.x > hadjustment.value + hadjustment.page_size - widget._today_width):
            self.histogram.change_location(len(self.histogram.get_datastore()) - 1)
            return True
        else:
            pass # Drag here
        return False

    def scroll_to_end(self, *args, **kwargs):
        """
        Scroll to the end of the drawing area's viewport
        """
        hadjustment = self.get_hadjustment()
        hadjustment.set_value(1)
        hadjustment.set_value(self.histogram.max_width - hadjustment.page_size)

    def scrubbing_fix(self, widget, i, ii):
        """
        Allows scrubbing to scroll the scroll window
        """
        hadjustment = self.get_hadjustment()
        proposed_xa = ((i) * self.histogram.xincrement) + self.histogram.start_x_padding
        proposed_xb = ((i + self.histogram.selected_range) * self.histogram.xincrement) + self.histogram.start_x_padding
        if proposed_xa < hadjustment.value:
            hadjustment.set_value(proposed_xa)
        elif proposed_xb > hadjustment.value + hadjustment.page_size:
            hadjustment.set_value(proposed_xb - hadjustment.page_size)
