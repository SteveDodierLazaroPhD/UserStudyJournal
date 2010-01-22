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
Takes a two dementional lis store of ints and turns it into a graph based on
the first value a int date, and the second value the number of items on that date
where items are
datastore = []
datastore.append(time, nitems)
CairoHistogram.set_datastore(datastore)
"""

import cairo
import gobject
import gtk
from gtk import gdk
from math import pi as PI
import datetime
import calendar
import pango


def check_for_new_month(date):
    if datetime.date.fromtimestamp(date).day == 1:
        return True
    return False

def get_gtk_rgba(style, palette, i, shade = 1, alpha = 1):
    """Takes a gtk style and returns a RGB tuple

    Arguments:
    - style: a gtk_style object
    - palette: a string representing the palette you want to pull a color from
        Example: "bg", "fg"
    - shade: how much you want to shade the color
    """
    f = lambda num: (num/65535.0) * shade
    color = getattr(style, palette)[i]
    if isinstance(color, gdk.Color):
        red = f(color.red)
        green = f(color.green)
        blue = f(color.blue)

        return (min(red, 1), min(green, 1), min(blue, 1), alpha)
    else: raise TypeError("Not a valid gdk.Color")

def get_gc_from_colormap(widget, shade):
    """
    Gets a gdk.GC and modifies the color by shade
    """
    gc = widget.style.text_gc[gtk.STATE_INSENSITIVE]
    if gc:
        color = widget.style.text[4]
        f = lambda num: min((num * shade, 65535.0))
        color.red = f(color.red)
        color.green = f(color.green)
        color.blue = f(color.blue)
        gc.set_rgb_fg_color(color)
    return gc


class CairoHistogram(gtk.DrawingArea):
    """
    A histogram which is represented by a list of dates, and nitems
    """
    __selected__ = (0,)
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
    gc = None
    pangofont = None
    __disable_mouse_motion__ = False
    selected_range = 0
    __highlighted__ = tuple()
    __callbacks__ = None
    __last_location__ = -1
    bg_color = (1, 1, 1, 1)
    base_color = (1, 1, 1, 1)
    column_color_normal =  (1, 1, 1, 1)
    column_color_selected = (1, 1, 1, 1)
    column_color_alternative = (1, 1, 1, 1)
    font_color = (0, 0, 0, 0)
    stroke_color = (1, 1, 1, 0)
    shadow_color = (1, 1, 1, 0)

    __datastore__ = None
    __gsignals__ = {
        # the index of the first selected item in the datastore.
        "selection-set": (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                          (gobject.TYPE_INT,gobject.TYPE_INT)),
        "data-updated":  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,()),
        }
    __connections__ = {"style-set": "change_style",
                       "expose_event": "__expose__",
                       "button_press_event": "mouse_press_interaction",
                       "button_release_event": "mouse_release_interaction",
                       "motion_notify_event": "mouse_motion_interaction",
                       "key_press_event": "keyboard_interaction",
                       "scroll-event" : "mouse_scroll_interaction"}
    __events__ = (gdk.KEY_PRESS_MASK | gdk.LEAVE_NOTIFY_MASK |
                  gdk.POINTER_MOTION_MASK  | gdk.BUTTON_RELEASE_MASK |
                  gdk.BUTTON_PRESS_MASK| gdk.SCROLL_MASK)

    def __init__(self, datastore = None, selected_range = 0):
        """
        Arguments:
        - datastore: The.CairoHistograms two dimensional list of dates and nitems
        - selected_range: the number of days displayed at once
        """
        super(CairoHistogram, self).__init__()
        self.set_events(self.__events__)
        self.set_flags(gtk.CAN_FOCUS)
        for key, val in self.__connections__.iteritems():
            self.connect(key, getattr(self, val))
        self.font_name = self.style.font_desc.get_family()
        self.set_datastore(datastore if datastore else [], draw = False)
        self.selected_range = selected_range

    def change_style(self, widget, old_style):
        """
        Sets the widgets style and coloring
        """
        self.bg_color = get_gtk_rgba(self.style, "bg", 0)
        self.base_color = get_gtk_rgba(self.style, "base", 0)
        self.column_color_normal =  get_gtk_rgba(self.style, "text", 4, 1.17)
        self.column_color_selected = get_gtk_rgba(self.style, "bg", 3)
        pal = get_gtk_rgba(self.style, "bg", 3, 1.2)
        self.column_color_alternative = (pal[2], pal[1], pal[0], 1)
        self.column_color_selected_alternative = get_gtk_rgba(self.style, "bg", 3, 0.6)
        fg = self.style.fg[gtk.STATE_NORMAL]
        bg = self.style.bg[gtk.STATE_NORMAL]
        self.stroke_color = get_gtk_rgba(self.style, "text", 4)
        self.shadow_color = get_gtk_rgba(self.style, "text", 4)
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
            self.__datastore__ = datastore
            self.largest = 1
            for date, nitems in self.__datastore__:
                if nitems > self.largest: self.largest = nitems
            self.max_width = self.xincrement + (self.xincrement *len(datastore))
        else:
            raise TypeError("Datastore is not a <list>")
        self.emit("data-updated")
        self.set_selected(len(datastore) - self.selected_range)

    def get_datastore(self):
        return self.__datastore__

    def prepend_data(self, newdatastore):
        """
        Adds the items of a new list before the items of the current datastore

        Arguments:
        - newdatastore: the new list to be prepended

        ## WARNING SELECTION WILL CHANGE WHEN DOING THIS TO BE FIXED ##
        """
        selected = self.get_selected()[-1]
        self.__datastore__ = newdatastore + self.__datastore__
        self.queue_draw()
        self.set_selected(len(newdatastore) + selected)

    def __expose__(self, widget, event):
        """
        The major drawing method that the expose event calls directly

        Arguments:
        - widget: the widget
        - event: a gtk event with x and y values
        """
        context = widget.window.cairo_create()
        self.expose(widget, event, context)

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
        context.set_source_rgba(*self.base_color)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()
        context.set_source_rgba(*self.bg_color)
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

    def draw_columns_from_datastore(self, context, event, selected):
        """
        Draws columns from a datastore

        Arguments:
        - context: The drawingarea's cairo context from the expose event
        - event: a gtk event with x and y values
        - selected: a list of the selected columns
        """
        x = self.start_x_padding
        y = event.area.height

        months_positions = []
        i = 0
        for date, nitems in self.__datastore__:
            if check_for_new_month(date):
                months_positions += [(date, x)]
            if len(self.__highlighted__) > 0 and i >= self.__highlighted__[0] and i <= self.__highlighted__[-1] and i in self.__highlighted__:
                color = self.column_color_selected_alternative if i in selected else self.column_color_alternative
            elif not selected:
                color = self.column_color_normal
            elif i >= selected[0] and i <= selected[-1] and i in selected:
                color = self.column_color_selected
            else:
                color = self.column_color_normal
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
        context.set_source_rgba(*self.stroke_color)
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
         self.__selected__[0] and self.__selected__[-1]

        Arguments:
        - i: a list or a int where the int will select i + selected_range
        """
        self.__selected__ = i
        if isinstance(i, int):
            self.__selected__ = range(i, i + self.selected_range)
            self.emit("selection-set", max(i, 0), max(i + self.selected_range - 1, 0))
        else: self.__selected__ = []
        self.queue_draw()
        return True

    def get_selected(self):
        """
        returns a list of selected indices
        """
        return self.__selected__

    def clear_selection(self):
        """
        clears the selected items
        """
        self.__selected__ = range(len(self.__datastore__))[-self.selected_range:]
        self.queue_draw()

    def set_highlighted(self, highlighted):
        """
        Sets the widgets which should be highlighted with an alternative color
        Argument:
        - highlighted: a list of indexes to be highlighted
        """
        if isinstance(highlighted, list):
            self.__highlighted__ = highlighted
        else: raise TypeError("highlighted is not a list")
        self.queue_draw()

    def clear_highlighted(self):
        """Clears the highlighted color"""
        self.__highlighted__ = []
        self.queue_draw()

    def add_selection_callback(self, callback):
        """
        add a callback for clicked to call when a item is clicked.
        clicked passes this widget, a datastore list, and i to the function

        Arguments:
        - callback: the callback to add
        """
        if callable(callback):
            if not self.__callbacks__:
                self.__callbacks__ = [callback]
            elif isinstance(self.__callbacks__, list):
                self.__callbacks__.append(callback)
        else:
            raise TypeError("Callback is not a function")

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
        if (event.state == gdk.BUTTON1_MASK and not self.__disable_mouse_motion__):
            location = min((self.get_datastore_index_from_cartesian(event.x, event.y), len(self.__datastore__) - 1))
            if location != self.__last_location__:
                self.change_location(location)
                self.__last_location__ = location
            return True
        return False

    def mouse_press_interaction(self, widget, event, *args, **kwargs):
        if (event.y > self.get_size_request()[1] - self.bottom_padding and
            event.y < self.get_size_request()[1]):
            if not self.__disable_mouse_motion__: self.__disable_mouse_motion__ = True
            return False
        location = min((self.get_datastore_index_from_cartesian(event.x, event.y), len(self.__datastore__) - 1))
        if location != self.__last_location__:
            self.change_location(location)
            self.__last_location__ = location
        return True

    def mouse_release_interaction(self, widget, event):
        if self.__disable_mouse_motion__: self.__disable_mouse_motion__ = False

    def mouse_scroll_interaction(self, widget, event):
        i = self.get_selected()[-1]
        if (event.direction in (gdk.SCROLL_UP, gdk.SCROLL_RIGHT)):
            if i+1< len(self.get_datastore()):
                self.change_location(i+1)
        elif (event.direction in (gdk.SCROLL_DOWN, gdk.SCROLL_LEFT)):
            if 0 <= i-1:
                self.change_location(i-1)

    def change_location(self, location):
        """Handles click events

        By wrapping this and using the returned location you can do nifty stuff
        with the datastore object

        Calls a calback set by connect_selection_callback
        """
        if location < 0:
            return False
        self.set_selected(max(location - self.selected_range + 1, 0))
        if isinstance(self.__callbacks__, list):
            for callback in self.__callbacks__:
                if callable(callback):
                    callback(self, self.__datastore__, location)
        return True
