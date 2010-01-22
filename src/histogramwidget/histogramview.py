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
        elif self.container.__today_text__ and _in_area(x, y, self.container.__today_area__):
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
        self.bg_color = get_gtk_rgba(self.style, "bg", 0)
        self.base_color = get_gtk_rgba(self.style, "base", 0)
        self.column_color_normal =  get_gtk_rgba(self.style, "bg", 1)
        self.column_color_selected = get_gtk_rgba(self.style, "bg", 3)
        self.column_color_selected_alternative = get_gtk_rgba(self.style, "bg", 3, 0.7)
        self.column_color_alternative = get_gtk_rgba(self.style, "text", 2)
        self.stroke_color = get_gtk_rgba(self.style, "bg", 0)
        self.shadow_color = get_gtk_rgba(self.style, "bg", 0, 0.98)
        self.font_size = self.style.font_desc.get_size()/1024
        self.bottom_padding = self.font_size + 9 + widget.style.ythickness
        self.gc = self.style.text_gc[gtk.STATE_NORMAL]
        self.pangofont = pango.FontDescription(self.font_name + " %d" % self.font_size)
        self.pangofont.set_weight(pango.WEIGHT_BOLD)


class HistogramWidget(gtk.Viewport):
    """
    A container for a CairoHistogram which allows you to scroll
    """
    __today_width__ = 0
    __today_text__ = ""
    __today_area__ = None
    __today_hover__ = False

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
        self.histogram.connect("expose-event", self.today_expose)
        self.histogram.connect("button_press_event", self.footer_clicked)
        #self.histogram.connect("motion_notify_event", self.footer_hovered)
        #self.histogram.connect("leave_notify_event", self.__widget_leave_handler__)
        self.histogram.connect("selection-set", self.check_for_today)
        self.histogram.connect("data-updated", self.scroll_to_end)
        self.histogram.connect("data-updated", self.scroll_to_end)
        hadjustment = self.get_hadjustment()
        hadjustment.set_value(1) # Needs to be set twice to work
        hadjustment.set_value(self.histogram.max_width - hadjustment.page_size)
        self.histogram.connect("selection-set", self.scrubbing_fix)
        self.histogram.queue_draw()
        self.queue_draw()

    def today_expose(self, widget, event):
        """
        A double drawing hack to draw twice on a drawing areas window. It should
        draw today on the drawing area window
        """
        if len(self.__today_text__):
            hadjustment = self.get_hadjustment()
            context = widget.window.cairo_create()
            context.set_source_rgba(*widget.bg_color)
            layout = widget.create_pango_layout(self.__today_text__)
            pangofont = pango.FontDescription(widget.font_name + " %d" % (widget.font_size - 1))
            if not widget.gc:
                widget.gc = get_gc_from_colormap(widget, 0.6)
            layout.set_font_description(pangofont)
            w, h = layout.get_pixel_size()
            self.__today_width__ = w + 10
            self.__today_area__ = (
                int(hadjustment.value + hadjustment.page_size - self.__today_width__),
                int(event.area.height - widget.bottom_padding + 2),
                self.__today_width__,
                widget.bottom_padding - 2)
            state = gtk.STATE_PRELIGHT if self.__today_hover__ else gtk.STATE_NORMAL
            shadow = gtk.SHADOW_IN if self.__today_hover__ else gtk.SHADOW_OUT
            widget.style.paint_box(widget.window, state, gtk.SHADOW_OUT, event.area, widget, "button", *self.__today_area__)
            if self.__today_hover__:
                widget.style.paint_focus(widget.window, state, event.area, widget, "button", *self.__today_area__)
            widget.window.draw_layout(widget.gc, int(hadjustment.value + hadjustment.page_size - w -5),
                                      int(event.area.height - widget.bottom_padding/2 - h/2), layout)
            return True
        return False

    def __widget_leave_handler__(self, widget, event):
        """
        Clears hover effects when you leave the widget
        """
        self.__today_hover__ = False
        self.queue_draw()
        return True

    def footer_hovered(self, widget, event):
        """
        Highlights the today button if you hover over it
        """
        hadjustment = self.get_hadjustment()
        # Check if the today section of the footer was hovered
        if (self.__today_text__ and
            event.y > self.get_size_request()[1] - self.histogram.bottom_padding and
            event.x > hadjustment.value + hadjustment.page_size - self.__today_width__):
            if not self.__today_hover__:
                self.__today_hover__ = True
                self.histogram.queue_draw()
            return True
        if self.__today_hover__:
            self.__today_hover__ = False
            self.histogram.queue_draw()
        return False

    def footer_clicked(self, widget, event):
        """
        Handles all rejected clicks from bellow the histogram internal view and
        checks to see if they were inside of the today text
        """
        hadjustment = self.get_hadjustment()
        # Check for today button click
        if (self.__today_text__ and event.x > hadjustment.value + hadjustment.page_size - self.__today_width__):
            self.histogram.change_location(len(self.histogram.get_datastore()) - 1)
            return True
        else:
            pass # Drag here
        return False

    def check_for_today(self, widget, i, ii):
        """
        Changes today to a empty string if the selected item is not today
        """
        if ii == len(self.histogram.get_datastore())-1:
            self.__today_text__ = ""
            self.__today_area__ = None
            self.histogram.queue_draw()
        elif len(self.__today_text__) == 0:
            self.__today_text__ = _("Today") + " »"
        return True

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

