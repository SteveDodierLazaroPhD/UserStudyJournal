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
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
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

class DayButton(gtk.DrawingArea):
    leading = False
    pressed = False
    sensitive = True
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
        self.set_events(gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK |
                        gtk.gdk.BUTTON_PRESS_MASK)
        self.set_flags(gtk.CAN_FOCUS)
        self.leading = leading
        self.side = side
        self.connect("button_press_event", self.__on_press__)
        self.connect("button_release_event", self.__clicked_sender__)
        self.connect("key_press_event", self.__keyboard_clicked_sender__)
        self.connect("expose_event", self.expose)
        self.connect("style-set", self.change_style)
        self.set_size_request(20, -1)

    def set_sensitive(self, case):
        self.sensitive = case
        self.queue_draw()

    def __on_press__(self, widget, event):
        self.pressed = True
        self.queue_draw()

    def __keyboard_clicked_sender__(self, widget, event):
        if event.keyval in (gtk.keysyms.Return, gtk.keysyms.space):
            if self.sensitive:
                self.emit("clicked")
            self.pressed = False
            self.queue_draw()
            return True
        return False

    def __clicked_sender__(self, widget, event):
        if self.sensitive:
            self.emit("clicked")
        self.pressed = False
        self.queue_draw()
        return True

    def change_style(self, *args, **kwargs):
        self.bg_color = get_gtk_rgba(self.style, "bg", 0)
        self.header_color = get_gtk_rgba(self.style, "bg", 0, 1.25)
        self.leading_header_color = get_gtk_rgba(self.style, "bg", 3)
        self.internal_color = get_gtk_rgba(self.style, "bg", 0, 1.02)
        self.arrow_color = get_gtk_rgba(self.style, "text", 0, 0.6)
        self.arrow_color_selected = get_gtk_rgba(self.style, "bg", 3)
        self.arrow_color_insensitive = get_gtk_rgba(self.style, "text", 4)

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
        if self.sensitive:
            context.set_source_rgba(*(self.leading_header_color if self.leading else self.header_color))
            context.new_sub_path()
            context.arc(r+x, r+y, r, math.pi, 3 * math.pi /2)
            context.arc(w-r, r+y, r, 3 * math.pi / 2, 0)
            context.close_path()
            if self.side:
                context.rectangle(w/2, 0, w, self.header_size)
            else:
                context.rectangle(0, 0, w/2, self.header_size)
            context.rectangle(0, r, w,  self.header_size)
            context.fill()
            context.set_source_rgba(*self.internal_color)
            context.rectangle(0, self.header_size, w,  h)
            context.fill()
        if not self.sensitive:
            state = gtk.STATE_INSENSITIVE
        elif self.is_focus():
            state = gtk.STATE_SELECTED
        else:
            state = gtk.STATE_NORMAL
        arrow = gtk.ARROW_RIGHT if self.side else gtk.ARROW_LEFT
        self.style.paint_arrow(widget.window, state, gtk.SHADOW_NONE, None,
                               self, "arrow", arrow, True,
                               w/2, h/2, 5, 5)
