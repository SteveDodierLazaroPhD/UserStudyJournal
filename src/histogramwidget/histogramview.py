# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
# Copyright © 2010 Markus Korn <thekorn@gmx.de>
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

"""
Takes a two dementional tuple or list and turns it into a graph based on
datastore[n][1]'s size

# datastore = [[raw_date, nitems]]
"""

import cairo
import gobject
import gettext
import gtk
import pango
import datetime
import calendar
import time

from gtkhistogram import *


def get_gc_from_colormap(widget, shade):
    gc = widget.style.text_gc[gtk.STATE_INSENSITIVE]
    color = widget.style.text[4]
    f = lambda num: min((num * shade, 65535.0))
    color.red = f(color.red)
    color.green = f(color.green)
    color.blue = f(color.blue)
    gc.set_rgb_fg_color(color)
    return gc


class TooltipEventBox(gtk.EventBox):
    """
    A event box housing the tool tip logic that can be used for a CairoHistogram.
    Otherwise it interferes with the scrubbing mask code
    """
    _saved_tooltip_location = None
    def __init__(self, histogram):
        super(TooltipEventBox, self).__init__()
        self.add(histogram)
        self.histogram = histogram
        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.query_tooltip)

    def query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        location = self.histogram.get_data_index_from_cartesian(x, y)
        if location != self._saved_tooltip_location:
            # don't show the previous tooltip if we moved to another
            # location
            self._saved_tooltip_location = location
            return False
        try:
            timestamp, count = self.histogram.datastore[location]
        except IndexError:
            # there is no bar for at this location
            # don't show a tooltip
            return False
        date = datetime.date.fromtimestamp(timestamp).strftime("%A, %d %B, %Y")
        tooltip.set_text("%s\n%i %s" % (date, count,
            gettext.ngettext("item", "items", count)))
        return True


class SectionedHistogram(CairoHistogram):
    """
    A subclass of CairoHistogram with theming to fit into Journal with a background colored bottom bar
    """
    padding = 2
    column_radius = 1.3
    font_size = 10
    bottom_padding = 18
    top_padding = 2
    wcolumn = 12
    xincrement = wcolumn + padding
    column_radius = 0
    text_pad = bottom_padding/3
    gc = None
    pangofont = None

    def change_style(self, widget, *args, **kwargs):
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
        #self.font_color = get_gtk_rgba(self.style, "text", 4, 0.6)
        self.stroke_color = get_gtk_rgba(self.style, "text", 4)
        self.shadow_color = get_gtk_rgba(self.style, "text", 4)
        self.font_size = self.style.font_desc.get_size()/1024
        self.pangofont = pango.FontDescription(self.font_name + " %d" % self.font_size)
        self.pangofont.set_weight(pango.WEIGHT_BOLD)
        self.bottom_padding = self.font_size + 9
        self.gc = get_gc_from_colormap(widget, 0.6)

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
        self.draw_columns_from_datastore(context, event, self._selected)
        context.set_line_width(1)
        context.set_source_rgba(*self.shadow_color)
        context.rectangle(event.area.x+0.5, event.area.y+0.5, event.area.width-1, event.area.height - self.bottom_padding)
        context.stroke()

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
        self.window.draw_layout(self.gc, int(x + 3), int(height - h), layout)


class JournalHistogram(SectionedHistogram):
    """
    A subclass of CairoHistogram with theming to fit into Journal
    """
    padding = 2
    column_radius = 1.3
    top_padding = 6
    bottom_padding = 23
    wcolumn = 10
    xincrement = wcolumn + padding
    column_radius = 2
    stroke_width = 2
    stroke_offset = 1
    font_size = 12
    text_pad = 5

    def change_style(self, widget, *args, **kwargs):
        self.bg_color = get_gtk_rgba(self.style, "bg", 0)
        self.base_color = get_gtk_rgba(self.style, "base", 0)
        self.column_color_normal =  get_gtk_rgba(self.style, "bg", 1)
        self.column_color_selected = get_gtk_rgba(self.style, "bg", 3)
        self.column_color_selected_alternative = get_gtk_rgba(self.style, "bg", 3, 0.7)
        self.column_color_alternative = get_gtk_rgba(self.style, "text", 2)
        #self.font_color = get_gtk_rgba(self.style, "text", 4, 0.6)
        self.stroke_color = get_gtk_rgba(self.style, "bg", 0)
        self.shadow_color = get_gtk_rgba(self.style, "bg", 0, 0.98)
        self.font_size = self.style.font_desc.get_size()/1024
        self.bottom_padding = self.font_size + 9
        self.gc = self.style.text_gc[gtk.STATE_NORMAL]
        self.pangofont = pango.FontDescription(self.font_name + " %d" % self.font_size)
        self.pangofont.set_weight(pango.WEIGHT_BOLD)


class HistogramWidget(gtk.HBox):
    """
    A container for a CairoHistogram which allows you to scroll
    """
    __pressed__ = False
    __today_width__ = 0
    __today_text__ = ""

    def __init__(self, histo_type = None):
        """
        Arguments:
        - used_themed_histogram: if true use JournalHistogram over CairoHistogram
        """
        super(gtk.HBox, self).__init__()
        self.viewport = gtk.Viewport()
        self.viewport.set_shadow_type(gtk.SHADOW_NONE)
        self.histogram = histo_type()
        self.eventbox = TooltipEventBox(self.histogram)
        self.viewport.set_size_request(600,75)
        self.viewport.add(self.eventbox)
        align = gtk.Alignment(0,0,1,1)
        align.set_padding(0, 0, 0, 0)
        align.add(self.viewport)
        if isinstance(self.histogram, SectionedHistogram):
            self.histogram.connect("expose-event", self.__today_expose__)
            self.histogram.connect("outer-click", self.__today_clicked__)
            self.histogram.connect("selection-set", self.__check_for_today__)
            self.histogram.connect("data-updated", self.scroll_to_end)
        self.backward_button = gtk.Button()
        self.backward_button.add(gtk.Arrow(gtk.ARROW_LEFT, gtk.SHADOW_NONE))
        self.backward_button.set_relief(gtk.RELIEF_NONE)
        self.backward_button.set_focus_on_click(False)
        self.forward_button = gtk.Button()
        self.forward_button.add(gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_NONE))
        self.forward_button.set_relief(gtk.RELIEF_NONE)
        self.forward_button.set_focus_on_click(False)
        self.backward_button.connect("pressed", self.smooth_scroll, self.backward_button, int(-self.histogram.xincrement/2))
        self.forward_button.connect("pressed", self.smooth_scroll, self.forward_button, int(self.histogram.xincrement/2))
        self.histogram.connect("data-updated", self.scroll_to_end)
        self.pack_start(self.backward_button, False, False)
        self.pack_start(align, True, True, 3)
        self.pack_end(self.forward_button, False, False)
        self.adjustment = self.viewport.get_hadjustment()
        self.adjustment.set_value(1) # Needs to be set twice to work
        self.adjustment.set_value(self.histogram.max_width - self.adjustment.page_size)
        self.backward_button.connect("released", self.__release_handler)
        self.forward_button.connect("released", self.__release_handler)
        self.backward_button.connect("key_press_event", self.keyboard_interaction, int(-self.histogram.xincrement/2))
        self.forward_button.connect("key_press_event", self.keyboard_interaction, int(self.histogram.xincrement/2))
        self.histogram.connect("selection-set", self.__scrubbing_fix__)
        self.histogram.queue_draw()
        self.viewport.queue_draw()
        self.set_focus_chain((self.backward_button, self.histogram, self.forward_button))

    def __today_expose__(self, widget, event, *args, **kwargs):
        """
        A double drawing hack to draw twice on a drawing areas window. It should
        draw today on the drawing area window
        """
        context = widget.window.cairo_create()
        context.set_source_rgba(*widget.bg_color)
        layout = widget.create_pango_layout(self.__today_text__)
        layout.set_font_description(widget.pangofont)
        w, h = layout.get_pixel_size()
        self.__today_width__ = w + 10
        context.rectangle(self.adjustment.value + self.adjustment.page_size - self.__today_width__,
                          event.area.height - widget.bottom_padding + 1, event.area.width, event.area.height)
        context.fill()
        if not widget.pangofont:
            widget.pangofont = pango.FontDescription(self.font_name + " %d" % self.font_size)
            widget.pangofont.set_weight(pango.WEIGHT_BOLD)
        if not widget.gc:
            widget.gc = get_gc_from_colormap(widget, 0.6)
        widget.window.draw_layout(widget.gc, int(self.adjustment.value + self.adjustment.page_size - w -5),
                                  int(event.area.height - h), layout)

    def __today_clicked__(self, widget, x, y):
        """
        Handles all rejected clicks from the outer-click signal and checks to
        see if they were inside of the today text
        """
        if x > self.adjustment.value + self.adjustment.page_size - self.__today_width__:
            self.histogram.change_location(len(self.histogram.get_data()) - 1)

    def __check_for_today__(self, widget, i):
        """
        Changes today to a empty string if the selected item is not today
        """
        if i + self.histogram.selected_range == len(self.histogram.get_data()):
            self.__today_text__ = ""
            self.histogram.queue_draw()
        elif len(self.__today_text__) == 0:
            self.__today_text__ = _("Today") + " »"

    def __release_handler(self, *args, **kwargs):
        """
        Clears scroll the button press varible
        """
        self.__pressed__ = False

    def smooth_scroll(self, widget, button, value):
        """
        Scrolls using a timeout while __pressed__
        """
        self.__pressed__ = True
        def _f(self, button, value):
            self.scroll_viewport(widget, value)
            if self.__pressed__: return True
            return False
        gobject.timeout_add(10, _f, self, button, value)
        
    def keyboard_interaction(self, widget, event, value):
        if event.keyval in (gtk.keysyms.space, gtk.keysyms.Return):
            self.scroll_viewport(widget, value)

    def scroll_viewport(self, widget, value, *args, **kwargs):
        """
        Scrolls the viewport over value number of days

        Arguments:
        - value: the number of pixels to scroll
          Use negative to scroll towards the left
        """
        adjustment = self.viewport.get_hadjustment()
        page_size = adjustment.get_page_size()
        if value < 1:
            newadjval = 0 if value > adjustment.value else (adjustment.value + value)
        elif adjustment.value + page_size > self.histogram.max_width - value:
            newadjval = self.histogram.max_width - page_size
        else:
            newadjval = adjustment.value + value
        adjustment.set_value(newadjval)
        self.histogram.queue_draw()

    def scroll_to_end(self, *args, **kwargs):
        """
        Scroll to the end of the drawing area's viewport
        """
        self.adjustment.set_value(1)
        self.adjustment.set_value(self.histogram.max_width - self.adjustment.page_size)

    def __scrubbing_fix__(self, widget, i, *args, **kwargs):
        """
        Allows scrubbing to scroll the scroll window
        """
        proposed_xa = ((i) * self.histogram.xincrement) + self.histogram.start_x_padding
        proposed_xb = ((i + self.histogram.selected_range) * self.histogram.xincrement) + self.histogram.start_x_padding
        if proposed_xa < self.adjustment.value:
            self.adjustment.set_value(proposed_xa)
        elif proposed_xb > self.adjustment.value + self.adjustment.page_size:
            self.adjustment.set_value(proposed_xb - self.adjustment.page_size)

