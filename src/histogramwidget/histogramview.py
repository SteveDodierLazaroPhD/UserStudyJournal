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

from gtkhistogram import *


class JournalHistogram(CairoHistogram):
    """
    A subclass of CairoHistogram with theming to fit into Journal
    """
    padding = 2
    column_radius = 1.3
    font_size = 12
    bottom_padding = 25
    top_padding = 6
    wcolumn = 9
    xincrement = wcolumn + padding
    start_x_padding = xincrement

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
        context.move_to(x+1, height - self.bottom_padding)
        context.line_to(x+1, height - self.bottom_padding/3)
        context.stroke()

        context.select_font_face(self.font_name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(self.font_size)
        date = datetime.date.fromtimestamp(date)
        month = calendar.month_name[date.month]
        date = "%s %d" % (month, date.year)
        xbearing, ybearing, width, oheight, xadvance, yadvance = context.text_extents(date)
        context.move_to(x + 8, height - self.bottom_padding/3)
        context.show_text(date)


class HistogramWidget(gtk.HBox):
    """
    A container for a CairoHistogram
    """
    def __init__(self, use_themed_histogram = False):
        super(gtk.HBox, self).__init__()
        viewport = gtk.Viewport()
        if use_themed_histogram:
            viewport.set_shadow_type(gtk.SHADOW_NONE)
            self.histogram = JournalHistogram()
        else:
            viewport.set_shadow_type(gtk.SHADOW_IN)
            self.histogram = CairoHistogram()
            
        self.eventbox = TooltipEventBox(self.histogram)
        viewport.set_size_request(600,70)
        viewport.add(self.eventbox)
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
                   self.histogram, -30*self.histogram.xincrement)
        b2.connect("clicked", self.scroll_viewport, viewport,
                   self.histogram, 30*self.histogram.xincrement)
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

