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

import gobject
import gtk
import pango
import pangocairo
import time
import math
import operator

import common

def crop(pb, src_x, src_y, width, height):
    """
    Crops a pixbuf
    """
    dest_pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, width, height)
    pb.copy_area(src_x, src_y, width, height, dest_pixbuf, 0, 0)
    return dest_pixbuf

def scale_to_fill(image, neww, newh):
    """
    Scales/crops a pixbuf to a width and height
    """
    imagew, imageh = image.get_width(), image.get_height()
    if (imagew, imageh) != (neww, newh):
        imageratio = float(imagew) / float(imageh)
        newratio = float(neww) / float(newh)
        if imageratio > newratio:
            transformw = int(round(newh * imageratio))
            image = image.scale_simple(transformw, newh, gtk.gdk.INTERP_BILINEAR)
            image = crop(image, 0, 0, neww, newh)
        elif imageratio < newratio:
            transformh = int(round(neww / imageratio))
            image = image.scale_simple(neww, transformh, gtk.gdk.INTERP_BILINEAR)
            image = crop(image, 0, 0, neww, newh)
        else:
            image = image.scale_simple(neww, newh, gtk.gdk.INTERP_BILINEAR)
    return image

def draw_frame(context, x, y, w, h):
    """
    Draws a 2 pixel frame around a area defined by x, y, w, h using a cairo context
    """
    x, y = int(x)+0.5, int(y)+0.5
    w, h = int(w), int(h)
    context.set_line_width(1)
    context.rectangle(x-1, y-1, w+2, h+2)
    context.set_source_rgba(0.3, 0.3, 0.3)
    context.stroke()
    context.set_source_rgba(1, 1, 1)
    context.rectangle(x, y, w, h)
    context.stroke()
    context.set_source_rgba(0.3, 0.3, 0.3)
    context.rectangle(x+1, y+1, w-2, h-2)
    context.stroke()

def draw_rounded_rectangle(context, x=0, y=0, w=1, h=1, r=0.05):
    """Draws a rounded rectangle"""
    context.new_sub_path()
    context.arc(r+x, r+y, r, math.pi, 3 * math.pi /2)
    context.arc(w-r+x, r+y, r, 3 * math.pi / 2, 0)
    context.arc(w-r+x, h-r+y, r, 0, math.pi/2)
    context.arc(r+x, h-r+y, r, math.pi/2, math.pi)
    context.close_path()
    #context.close_path()
    return context

def draw_speech_bubble(context, layout, x=0, y=0, w=1, h=1):
    """
    Draw a speech bubble at a position
    """
    layout.set_width((w-10)*1024)
    layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
    textw, texth = layout.get_pixel_size()
    context.new_path()
    context.move_to(x + 0.45*w, y+h*0.1 + 2)
    context.line_to(x + 0.5*w, y)
    context.line_to(x + 0.55*w, y+h*0.1 + 2)
    h = max(texth + 5, h)
    draw_rounded_rectangle(context, x, y+h*0.1, w, h, r = 5)
    context.close_path()
    context.set_line_width(2)
    context.set_source_rgb(168/255.0, 165/255.0, 134/255.0)
    context.stroke_preserve()
    context.set_source_rgb(253/255.0, 248/255.0, 202/255.0)
    context.fill()
    pcontext = pangocairo.CairoContext(context)
    pcontext.set_source_rgb(0, 0, 0)
    pcontext.move_to(x+5, y+5)
    pcontext.show_layout(layout)

def draw_text(context, layout, markup = "", x=0, y=0, maxw=0, color = (0.3, 0.3, 0.3)):
    """
    Draw text using a cairo context and a pango layout
    """
    pcontext = pangocairo.CairoContext(context)
    layout.set_markup(markup)
    layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
    pcontext.set_source_rgba(*color)
    if maxw:
        layout.set_width(maxw*1024)
    pcontext.move_to(x, y)
    pcontext.show_layout(layout)

def new_grayscale_pixbuf(pixbuf):
    """
    Makes a pixbuf grayscale
    """
    pixbuf2 = pixbuf.copy()
    pixbuf.saturate_and_pixelate(pixbuf2, 0.0, False)
    return pixbuf2
