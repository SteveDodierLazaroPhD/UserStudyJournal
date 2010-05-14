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
    _highlighted = []
    _last_location = -1
    _single_day_only = False
    colors = {
        "bg" : (1, 1, 1, 1),
        "base" : (1, 1, 1, 1),
        "column_normal" :  (1, 1, 1, 1),
        "column_selected" : (1, 1, 1, 1),
        "column_alternative" : (1, 1, 1, 1),
        "column_selected_alternative" : (1, 1, 1, 1),
        "font_color" : "#ffffff",
        "stroke" : (1, 1, 1, 0),
        "shadow" : (1, 1, 1, 0),
        }

    _store = None

    __gsignals__ = {
        "selection-set" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                           (gobject.TYPE_PYOBJECT,)),
        "data-updated" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,()),
        "column_clicked" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                            (gobject.TYPE_PYOBJECT,))
        }
    _connections = {"style-set": "change_style",
                       "expose_event": "_expose",
                       "button_press_event": "mouse_press_interaction",
                       "motion_notify_event": "mouse_motion_interaction",
                       "key_press_event": "keyboard_interaction",
                       "scroll-event" : "mouse_scroll_interaction",
                       }
    _events = (gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON_MOTION_MASK |
                  gtk.gdk.POINTER_MOTION_HINT_MASK | gtk.gdk.BUTTON_RELEASE_MASK |
                  gtk.gdk.BUTTON_PRESS_MASK)

    def __init__(self):
        """
        :param datastore: The.CairoHistograms two dimensional list of dates and nitems
        :param selected_range: the number of days displayed at once
        """
        super(CairoHistogram, self).__init__()
        self._selected = []
        self.set_events(self._events)
        self.set_flags(gtk.CAN_FOCUS)
        for key, val in self._connections.iteritems():
            self.connect(key, getattr(self, val))
        self.font_name = self.style.font_desc.get_family()

    def change_style(self, widget, old_style):
        """
        Sets the widgets style and coloring
        """
        self.colors = self.colors.copy()
        self.colors["bg"] = get_gtk_rgba(self.style, "bg", 0)
        self.colors["base"] = get_gtk_rgba(self.style, "base", 0)
        self.colors["column_normal"] =  get_gtk_rgba(self.style, "text", 4, 1.17)
        self.colors["column_selected"] = get_gtk_rgba(self.style, "bg", 3)
        color = self.style.bg[gtk.STATE_NORMAL]
        fcolor = self.style.fg[gtk.STATE_NORMAL]
        self.colors["font_color"] = combine_gdk_color(color, fcolor).to_string()

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

    def set_store(self, store):
        self._store = store
        self.largest = min(max(max(map(lambda x: len(x), store.days)), 1), 100)
        if not self.get_selected():
            self.set_selected([datetime.date.today()])
        else:
            self.set_selected(self.get_selected())
        self.queue_draw()
        self.last_updated = time.time()

    def get_store(self):
        return self._store

    def _expose(self, widget, event):
        """
        The major drawing method that the expose event calls directly
        """
        widget.style.set_background(widget.window, gtk.STATE_NORMAL)
        context = widget.window.cairo_create()
        self.expose(widget, event, context)

    def expose(self, widget, event, context):
        """
        The minor drawing method

        :param event: a gtk event with x and y values
        :param context: This drawingarea's cairo context from the expose event
        """
        if not self.pangofont:
            self.pangofont = pango.FontDescription(self.font_name + " %d" % self.font_size)
            self.pangofont.set_weight(pango.WEIGHT_BOLD)
        if not self.gc:
            self.gc = get_gc_from_colormap(widget, 0.6)
        context.set_source_rgba(*self.colors["base"])
        context.set_operator(cairo.OPERATOR_SOURCE)
        #context.paint()
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()
        #context.set_source_rgba(*self.colors["bg"])
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height - self.bottom_padding)
        context.fill()
        self.draw_columns_from_store(context, event, self.get_selected())
        context.set_line_width(1)
        if type(self) == CairoHistogram:
            widget.style.paint_shadow(widget.window, gtk.STATE_NORMAL, gtk.SHADOW_IN,
                                      event.area, widget, "treeview", event.area.x, event.area.y,
                                      event.area.width, event.area.height - self.bottom_padding)
        if self.is_focus():
            widget.style.paint_focus(widget.window, gtk.STATE_NORMAL, event.area, widget, None, event.area.x, event.area.y,
                                     event.area.width, event.area.height - self.bottom_padding)

    def draw_columns_from_store(self, context, event, selected):
        """
        Draws columns from a datastore

        :param context: This drawingarea's cairo context from the expose event
        :param event: a gtk event with x and y values
        :param selected: a list of the selected dates
        """
        x = self.start_x_padding
        months_positions = []
        for day in self.get_store().days:
            if day.date.day == 1:
                months_positions += [(day.date, x)]
            if day.date in self._highlighted:
                color = self.colors["column_selected_alternative"] if day.date in selected else self.colors["column_alternative"]
            elif day.date in selected:
                color = self.colors["column_selected"]
            else:
                color = self.colors["column_normal"]
            self.draw_column(context, x, event.area.height, len(day), color)
            x += self.xincrement
        if x > event.area.width: # Check for resize
            self.set_size_request(x+self.xincrement, event.area.height)
        for date, xpos in months_positions:
            edge = 0
            if (date, xpos) == months_positions[-1]:
                edge = len(self._store)*self.xincrement
            self.draw_month(context, xpos - self.padding, event.area.height, date, edge)
        self.max_width = x # remove me

    def draw_column(self, context, x, maxheight, nitems, color):
        """
        Draws a columns at x with height based on nitems, and maxheight

        :param context: The drawingarea's cairo context from the expose event
        :param x: The current position in the image
        :param maxheight: The event areas height
        :param nitems: The number of items in the column to be drawn
        :param color: A RGBA tuple Example: (0.3, 0.4, 0.8, 1)
        """
        if nitems < 2:
            nitems = 2
        elif nitems > self.max_column_height:
            nitems = self.max_column_height
        maxheight = maxheight - self.bottom_padding - 2
        #height = int((maxheight-self.top_padding-2) * (self.largest*math.log(nitems)/math.log(self.largest))/100)
        height = int(((float(nitems)/self.largest)*(maxheight-2))) - self.top_padding
        #height = min(int((maxheight*self.largest/100) * (1 - math.e**(-0.025*nitems))), maxheight)
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

    def draw_month(self, context, x, height, date, edge=0):
        """
        Draws a line signifying the start of a month
        """
        context.set_source_rgba(*self.colors["stroke"])
        context.set_line_width(self.stroke_width)
        context.move_to(x+self.stroke_offset, 0)
        context.line_to(x+self.stroke_offset, height - self.bottom_padding)
        context.stroke()
        month = calendar.month_name[date.month]
        date = "<span color='%s'>%s %d</span>" % (self.colors["font_color"], month, date.year)
        layout = self.create_pango_layout(date)
        layout.set_markup(date)
        layout.set_font_description(self.pangofont)
        w, h = layout.get_pixel_size()
        if edge:
            if x + w > edge: x = edge - w - 5
        self.window.draw_layout(self.gc, int(x + 3), int(height - self.bottom_padding/2 - h/2), layout)

    def set_selected(self, dates):
        if dates == self._selected:
            return False
        self._selected = dates
        if dates:
            date = dates[-1]
        self.emit("selection-set", dates)
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
        self._selected = []
        self.queue_draw()

    def set_highlighted(self, highlighted):
        """
        Sets the widgets which should be highlighted with an alternative color

        :param highlighted: a list of indexes to be highlighted
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

    def get_store_index_from_cartesian(self, x, y):
        """
        Gets the datastore index from a x, y value
        """
        return int((x - self.start_x_padding) / self.xincrement)

    def keyboard_interaction(self, widget, event):
        if event.keyval in (gtk.keysyms.space, gtk.keysyms.Right, gtk.keysyms.Left, gtk.keysyms.BackSpace):
            i = self.get_selected()
            if isinstance(i, list) and len(i) > 0: i = i[-1]
            if event.keyval in (gtk.keysyms.space, gtk.keysyms.Right):
                i = i + datetime.timedelta(days=1)
            elif event.keyval in (gtk.keysyms.Left, gtk.keysyms.BackSpace):
                i = i + datetime.timedelta(days=-1)
            if i < datetime.date.today() + datetime.timedelta(days=1):
                self.change_location(i)

    def mouse_motion_interaction(self, widget, event, *args, **kwargs):
        """
        Reacts to mouse moving (while pressed), and clicks
        """
        #if (event.state == gtk.gdk.BUTTON1_MASK and not self._disable_mouse_motion):
        location = min((self.get_store_index_from_cartesian(event.x, event.y), len(self._store.days) - 1))
        if location != self._last_location:
            self.change_location(location)
            self._last_location = location
            #return True
        return False

    def mouse_press_interaction(self, widget, event, *args, **kwargs):
        if (event.y > self.get_size_request()[1] - self.bottom_padding and
            event.y < self.get_size_request()[1]):
            return False
        location = min((self.get_store_index_from_cartesian(event.x, event.y), len(self._store.days) - 1))
        if location != self._last_location:
            self.change_location(location)
            self._last_location = location
        return True

    def mouse_scroll_interaction(self, widget, event):
        date = self.get_selected()[-1]
        i = self.get_store().dates.index(date)
        if (event.direction in (gtk.gdk.SCROLL_UP, gtk.gdk.SCROLL_RIGHT)):
            if i+1< len(self.get_store().days):
                self.change_location(i+1)
        elif (event.direction in (gtk.gdk.SCROLL_DOWN, gtk.gdk.SCROLL_LEFT)):
            if 0 <= i-1:
                self.change_location(i-1)

    def change_location(self, location):
        """
        Handles click events
        """
        if isinstance(location, int):
            if location < 0:
                return False
            store = self.get_store()
            date = store.days[location].date
        else: date = location
        self.emit("column_clicked", date)
        return True

    left_icon = get_icon_for_name("back", 16)
    right_icon = get_icon_for_name("forward", 16)
    def _expose_scroll_buttons(self, widget, event):
        render_pixbuf(widget.window, event.area.x + event.area.width-16, event.area.y+event.area.height-16, self.right_icon, False)
        render_pixbuf(widget.window, event.area.x, event.area.y+event.area.height-16, self.left_icon, False)


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
        #self.connect("query-tooltip", self.query_tooltip)

    def query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        if y < self.histogram.get_size_request()[1] - self.histogram.bottom_padding:
            location = self.histogram.get_store_index_from_cartesian(x, y)
            if location != self._saved_tooltip_location:
                # don't show the previous tooltip if we moved to another
                # location
                self._saved_tooltip_location = location
                return False
            try:
                timestamp, count = self.histogram.get_store()[location]
            except IndexError:
                # there is no bar for at this location
                # don't show a tooltip
                return False
            date = datetime.date.fromtimestamp(timestamp).strftime("%A, %d %B, %Y")
            tooltip.set_text("%s\n%i %s" % (date, count,
                                            gettext.ngettext("item", "items", count)))
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
    __gsignals__ = {
        # the index of the first selected item in the datastore.
        "date-changed" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                           (gobject.TYPE_PYOBJECT,)),
        }

    def __init__(self, histo_type=CairoHistogram, size = (600, 75)):
        """
        :param histo_type: a :class:`CairoHistogram <CairoHistogram>` or a derivative
        """
        super(HistogramWidget, self).__init__()
        self.set_shadow_type(gtk.SHADOW_NONE)
        self.histogram = histo_type()
        self.eventbox = TooltipEventBox(self.histogram, self)
        self.set_size_request(*size)
        self.add(self.eventbox)
        self.histogram.connect("column_clicked", self.date_changed)
        self.histogram.connect("selection-set", self.scrubbing_fix)
        self.histogram.queue_draw()
        self.queue_draw()
        self.connect("size-allocate", self.on_resize)
        self.histogram.connect("button-press-event", self.mouse_click_scroll)

    def mouse_click_scroll(self, widget, event):
        hadjustment = self.get_hadjustment()
        value = hadjustment.get_value()
        if event.x - value < 16:
            hadjustment.set_value(max(0, value-10))
        elif event.x > value + hadjustment.page_size - 16:
            hadjustment.set_value(min(self.histogram.max_width, value+10))
        self.histogram.queue_draw()

    def on_resize(self, widget, allocation):
        dates = self.histogram.get_selected()
        self.scrubbing_fix(self.histogram, dates)

    def date_changed(self, widget, date):
        self.emit("date-changed", date)

    def set_store(self, store):
        self.histogram.set_store(store)
        self.scroll_to_end()

    def set_dates(self, dates):
        self.histogram.set_selected(dates)

    def scroll_to_end(self, *args, **kwargs):
        """
        Scroll to the end of the drawing area's viewport
        """
        hadjustment = self.get_hadjustment()
        hadjustment.set_value(1)
        hadjustment.set_value(self.histogram.max_width - hadjustment.page_size)

    def scrubbing_fix(self, widget, dates):
        """
        Allows scrubbing to scroll the scroll window
        """
        if not len(dates):
            return
        store = widget.get_store()
        i = store.dates.index(dates[0])
        hadjustment = self.get_hadjustment()
        proposed_xa = ((i) * self.histogram.xincrement) + self.histogram.start_x_padding
        proposed_xb = ((i + len(dates)) * self.histogram.xincrement) + self.histogram.start_x_padding
        if proposed_xa < hadjustment.value:
            hadjustment.set_value(proposed_xa)
        elif proposed_xb > hadjustment.value + hadjustment.page_size:
            hadjustment.set_value(proposed_xb - hadjustment.page_size)
