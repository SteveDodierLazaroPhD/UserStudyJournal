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

import cairo
import gobject
import gtk
import pango
import time
import math
import operator

import common
import drawing


class PreviewRenderer(gtk.GenericCellRenderer):
    """
    A IconView renderer to be added to a celllayout. It displays a pixbuf and
    data based on the event property
    """

    __gtype_name__ = "PreviewRenderer"
    __gproperties__ = {
        "pixbuf" :
        (gtk.gdk.Pixbuf,
         "pixbuf to be displayed",
         "pixbuf to be displayed",
         gobject.PARAM_READWRITE,
         ),
        "emblems" :
        (gobject.TYPE_PYOBJECT,
         "emblems to be displayed",
         "emblems to be displayed",
         gobject.PARAM_READWRITE,
         ),
        "active":
        (gobject.TYPE_BOOLEAN,
         "If the item is active",
         "True if active",
         False,
         gobject.PARAM_READWRITE,
         ),
        "event" :
        (gobject.TYPE_PYOBJECT,
         "event to be displayed",
         "event to be displayed",
         gobject.PARAM_READWRITE,
         ),
        "isthumb" :
        (gobject.TYPE_BOOLEAN,
         "Is the pixbuf a thumb",
         "True if pixbuf is thumb",
         False,
         gobject.PARAM_READWRITE),
    }

    width = 96
    height = int(96*3/4.0)
    properties = {}

    @property
    def emblems(self):
        return self.get_property("emblems")
    @property
    def pixbuf(self):
        return self.get_property("pixbuf")
    @property
    def active(self):
        return self.get_property("active")
    @property
    def event(self):
        return self.get_property("event")
    @property
    def isthumb(self):
        return self.get_property("isthumb")

    def __init__(self):
        super(PreviewRenderer, self).__init__()
        self.properties = {}
        self.set_fixed_size(self.width, self.height)
        self.set_property("mode", gtk.CELL_RENDERER_MODE_ACTIVATABLE)

    def do_set_property(self, pspec, value):
        self.properties[pspec.name] = value

    def do_get_property(self, pspec):
        return self.properties[pspec.name]

    def on_get_size(self, widget, area):
        if area:
            #return (area.x, area.y, area.width, area.height)
            return (0, 0, area.width, area.height)
        return (0,0,0,0)

    def on_render(self, window, widget, background_area, cell_area, expose_area, flags):
        """
        The primary rendering function. It calls either the classes rendering functions
        or special one defined in the rendering_functions dict
        """
        x = cell_area.x
        y = cell_area.y
        w = cell_area.width
        h = cell_area.height
        if self.isthumb:
            self.render_pixbuf(window, widget, x, y, h, w)
        else: file_render_pixbuf(self, window, widget, x, y, h, w)
        self.render_emblems(window, widget, x, y, h, w)
        if self.active:
            gobject.timeout_add(2, self.render_info_box, window, widget, cell_area, expose_area, self.event)
        return True

    def render_pixbuf(self, window, widget, x, y, h, w):
        """
        Renders a pixbuf to be displayed on the cell
        """
        pixbuf = self.pixbuf
        imgw, imgh = pixbuf.get_width(), pixbuf.get_height()
        context = window.cairo_create()
        x += (self.width - imgw)/2
        y += self.height - imgh
        context.rectangle(x, y, imgw, imgh)
        context.set_source_rgb(1, 1, 1)
        context.fill_preserve()
        context.set_source_pixbuf(pixbuf, x, y)
        context.fill()
        # Frame
        drawing.draw_frame(context, x, y, imgw, imgh)

    def render_emblems(self, window, widget, x, y, w, h):
        """
        Renders the defined emblems from the emblems property
        """
        w = max(self.width, w)
        corners = [[x, y],
                   [x+w, y],
                   [x, y+h],
                   [x+w, y+h]]
        context = window.cairo_create()
        emblems = self.emblems
        for i in xrange(len(emblems)):
            i = i % len(emblems)
            pixbuf = emblems[i]
            pbw, pbh = pixbuf.get_width()/2, pixbuf.get_height()/2
            context.set_source_pixbuf(pixbuf, corners[i][0]-pbw, corners[i][1]-pbh)
            context.rectangle(corners[i][0]-pbw, corners[i][1]-pbh, pbw*2, pbh*2)
            context.fill()

    def render_info_box(self, window, widget, cell_area, expose_area, event):
        """
        Renders a info box when the item is active
        """
        x = cell_area.x
        y = cell_area.y - 10
        w = cell_area.width
        h = cell_area.height
        context = window.cairo_create()
        text = common.get_event_markup(event)
        layout = widget.create_pango_layout(text)
        layout.set_markup(text)
        textw, texth = layout.get_pixel_size()
        popuph = max(h/3 + 5, texth)
        nw = w + 26
        x = x - (nw - w)/2
        width, height = window.get_geometry()[2:4]
        popupy = min(y+h+10, height-popuph-5-1) - 5
        drawing.draw_speech_bubble(context, layout, x, popupy, nw, popuph)
        context.fill()
        return False

    def on_start_editing(self, event, widget, path, background_area, cell_area, flags):
        pass

    def on_activate(self, event, widget, path, background_area, cell_area, flags):
        common.launch_event(self.event)
        return True


gobject.type_register(PreviewRenderer)


# Special rendering functions
def file_render_pixbuf(self, window, widget, x, y, h, w):
    pixbuf = self.pixbuf
    imgw, imgh = pixbuf.get_width(), pixbuf.get_height()
    context = window.cairo_create()
    ix = x + (self.width - imgw)
    iy = y + self.height - imgh
    context.rectangle(x, y, w, h)
    context.set_source_rgb(1, 1, 1)
    context.fill_preserve()
    context.set_source_pixbuf(pixbuf, ix, iy)
    context.fill()
    drawing.draw_frame(context, x, y, w, h)
    context = window.cairo_create()
    text = common.get_text(self.event)
    layout = widget.create_pango_layout(text)
    drawing.draw_text(context, layout, text, x+5, y+5, self.width-10)

