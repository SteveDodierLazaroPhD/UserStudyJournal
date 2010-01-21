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
                timestamp, count = self.histogram.datastore[location]
            except IndexError:
                # there is no bar for at this location
                # don't show a tooltip
                return False
            date = datetime.date.fromtimestamp(timestamp).strftime("%A, %d %B, %Y")
            tooltip.set_text("%s\n%i %s" % (date, count,
                                            gettext.ngettext("item", "items", count)))
        elif len(self.container.__today_text__) > 0:
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
        self.eventbox = TooltipEventBox(self.histogram, self)
        self.viewport.set_size_request(600,75)
        self.viewport.add(self.eventbox)
        align = gtk.Alignment(0,0,1,1)
        align.set_padding(0, 0, 0, 0)
        align.add(self.viewport)
        self.histogram.connect("expose-event", self.today_expose)
        self.histogram.connect("month-frame-clicked", self.today_clicked)
        self.histogram.connect("selection-set", self.check_for_today)
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
        self.backward_button.connect("released", self.release_handler)
        self.forward_button.connect("released", self.release_handler)
        self.backward_button.connect("key_press_event", self.keyboard_interaction, int(-self.histogram.xincrement/2))
        self.forward_button.connect("key_press_event", self.keyboard_interaction, int(self.histogram.xincrement/2))
        self.histogram.connect("selection-set", self.scrubbing_fix)
        self.histogram.queue_draw()
        self.viewport.queue_draw()
        self.set_focus_chain((self.backward_button, self.forward_button, self.histogram))

    def today_expose(self, widget, event, *args, **kwargs):
        """
        A double drawing hack to draw twice on a drawing areas window. It should
        draw today on the drawing area window
        """
        if len(self.__today_text__):
            context = widget.window.cairo_create()
            context.set_source_rgba(*widget.bg_color)
            layout = widget.create_pango_layout(self.__today_text__)
            pangofont = pango.FontDescription(widget.font_name + " %d" % (widget.font_size - 1))
            if not widget.gc:
                widget.gc = get_gc_from_colormap(widget, 0.6)
            layout.set_font_description(pangofont)
            w, h = layout.get_pixel_size()
            self.__today_width__ = w + 10
            widget.style.paint_box(widget.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT, event.area,
                                   widget, "button", int(self.adjustment.value + self.adjustment.page_size - self.__today_width__),
                                   int(event.area.height - widget.bottom_padding + 2), self.__today_width__, widget.bottom_padding - 2)
            widget.window.draw_layout(widget.gc,
                                      int(self.adjustment.value + self.adjustment.page_size - w -5),
                                      int(event.area.height - widget.bottom_padding/2 - h/2), layout)

    def today_clicked(self, widget, x, y):
        """
        Handles all rejected clicks from the outer-click signal and checks to
        see if they were inside of the today text
        """
        if x > self.adjustment.value + self.adjustment.page_size - self.__today_width__:
            self.histogram.change_location(len(self.histogram.get_datastore()) - 1)

    def check_for_today(self, widget, i):
        """
        Changes today to a empty string if the selected item is not today
        """
        if i + self.histogram.selected_range == len(self.histogram.get_datastore()):
            self.__today_text__ = ""
            self.histogram.queue_draw()
        elif len(self.__today_text__) == 0:
            self.__today_text__ = _("Today") + " »"

    def release_handler(self, *args, **kwargs):
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

    def scrubbing_fix(self, widget, i, *args, **kwargs):
        """
        Allows scrubbing to scroll the scroll window
        """
        proposed_xa = ((i) * self.histogram.xincrement) + self.histogram.start_x_padding
        proposed_xb = ((i + self.histogram.selected_range) * self.histogram.xincrement) + self.histogram.start_x_padding
        if proposed_xa < self.adjustment.value:
            self.adjustment.set_value(proposed_xa)
        elif proposed_xb > self.adjustment.value + self.adjustment.page_size:
            self.adjustment.set_value(proposed_xb - self.adjustment.page_size)

