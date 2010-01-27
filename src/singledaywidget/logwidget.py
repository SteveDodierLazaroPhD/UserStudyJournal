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
from gtk import gdk
import pango
import time
import random
import math

from zeitgeist.datamodel import Interpretation


TIMES = ("4:00", "8:00", "12:00", "16:00",
         "20:00", "22:00",)

tangocolors = (
    (252/255.0, 234/255.0,  79/255.0),#0
    (237/255.0, 212/255.0,   0/255.0),
    (196/255.0, 160/255.0,   0/255.0),

    (252/255.0, 175/255.0,  62/255.0),#3
    (245/255.0, 121/255.0,   0/255.0),
    (206/255.0,  92/255.0,   0/255.0),

    (233/255.0, 185/255.0, 110/255.0),#6
    (193/255.0, 125/255.0,  17/255.0),
    (143/255.0,  89/255.0,  02/255.0),

    (138/255.0, 226/255.0,  52/255.0),#9
    (115/255.0, 210/255.0,  22/255.0),
    ( 78/255.0, 154/255.0,  06/255.0),

    (114/255.0, 159/255.0, 207/255.0),#12
    ( 52/255.0, 101/255.0, 164/255.0),
    ( 32/255.0,  74/255.0, 135/255.0),

    (173/255.0, 127/255.0, 168/255.0),#15
    (117/255.0,  80/255.0, 123/255.0),
    ( 92/255.0,  53/255.0, 102/255.0),

    (239/255.0,  41/255.0,  41/255.0),#18
    (204/255.0,   0/255.0,   0/255.0),
    (164/255.0,   0/255.0,   0/255.0),

    (136/255.0, 138/255.0, 133/255.0),#21
    ( 85/255.0,  87/255.0,  83/255.0),
    ( 46/255.0,  52/255.0,  54/255.0),
    )

FILETYPES ={
    Interpretation.VIDEO.uri : 0,
    Interpretation.MUSIC.uri : 3,
    Interpretation.DOCUMENT.uri : 12,
    Interpretation.IMAGE.uri : 15,
    Interpretation.SOURCECODE.uri : 12,
    Interpretation.UNKNOWN.uri : 21,
    }

FILETYPESNAMES ={
    Interpretation.VIDEO.uri : "Video",
    Interpretation.MUSIC.uri : "Music",
    Interpretation.DOCUMENT.uri : "Document",
    Interpretation.IMAGE.uri : "Image",
    Interpretation.SOURCECODE.uri : "Source Code",
    Interpretation.UNKNOWN.uri : "Unknown",
    }


def make_area_from_event(x, max_width, timestamp, duration):
    """
    Generates a time box based on a objects timestamp and duration

    Arguments
    - x: The start x postion
    - max_width: The max gdk.window width
    - timestamp: a timestamp int or string from which to calulate the start position
    - duration: the length to calulate the width
    """
    _f = lambda duration: max(duration/3600.0/1000.0/24.0 * max_width, max_width/48)
    _e = lambda timestamp: max(((int(timestamp)/1000.0 - time.timezone)%86400)/3600/24.0 * max_width, 2)
    x = x + _e(int(timestamp))
    width = min(_f(duration), max_width-x)
    return [x, int(width)]


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
    raise TypeError("Not a valid gdk.Color")


def get_gc_from_colormap(style, palette, i, shade=1):
    """
    Gets a gdk.GC and modifies the color by shade
    """
    gc = getattr(style, palette)[i]
    if gc and shade != 1:
        color = style.text[4]
        f = lambda num: min((num * shade, 65535.0))
        color.red = f(color.red)
        color.green = f(color.green)
        color.blue = f(color.blue)
        gc.set_rgb_fg_color(color)
    return gc


def draw_text(window, layout, gc, text, x, y, width, height, xcenter = False,
              ycenter = False, xoffset= 0, yoffset= 0, maxw = 0):
    """
    draw text using this function

    Arguments:
    - window: a window to draw on
    - layout: a pango layout to use for writing
    - gc: a text_gc from style
    - text: the text to draw
    - x: The start x postion
    - y: The start y position
    - width: The width of the container box
    - height: The height of the box
    - xcenter(optional) True/False. Should we center text on x/y
    - ycenter(optional)
    - xoffset: amount to offset the x
    - yoffset: amount to offset the y
    - maxw: max string width
    """
    x += xoffset
    y += yoffset
    layout.set_markup(text)
    layout.set_spacing(1024)
    text_w, text_h = layout.get_pixel_size()
    layout.set_width(maxw*1024)
    layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
    window.draw_layout(
        gc, int(x + text_w/2 if xcenter else x),
        int(y + text_h/2 if ycenter else y), layout)
    layout.set_spacing(0)
    return text_h, text_w

def draw_text_box(window, context, layout, gc, basecolor, text, x, y, maxwidth, maxheight,
                  innercolor = (0, 0, 0, 0), ftype=None, fmime="", bars = None):
    """
    Draws a box around the marker box and draws the text in a box on the side

    Arguments:
    - a window to draw on
    - context: A cairo context to draw on
    - layout: a pango layout to use for writing
    - gc: a text_gc from style
    - basecolor: a rgba tuple for the outer tab
    - text: the text to draw
    - x: The start x postion
    - y: The start y position
    - maxwidth: The boxes max width
    - maxheight: The max height of the box
    - innercolor(*optional): a rgba tuple for the outer tab
    - ftype(optional): the file type
    - fmime(optional): the mimetype
    - a list of bar tuples with (x, width) values to draw
    """
    if ftype:
        if ftype in FILETYPES.keys():
            i = FILETYPES[ftype]
            l = int(math.fabs(hash(fmime))) % 3
            innercolor = tangocolors[min(i+l, len(tangocolors)-1)]
        else:
            innercolor = (136/255.0, 138/255.0, 133/255.0)
    bar_height = 3
    edge = 0
    layout.set_markup(text)
    text_width, text_height  = layout.get_pixel_size()
    text_width+=bar_height
    if bars and len(bars) > 1:
        width = (bars[-1][0] + bars[-1][1]) - bars[0][0]
    else:
        width = max(text_width, bars[0][1])
    if x + text_width > maxwidth:
        area = (max(maxwidth-text_width, maxwidth-200), y, text_width, maxheight)
    else:
        area = (x, y, max(text_width, width), maxheight)
    if x > maxwidth - 10:
        x = maxwidth - 10
        width +=10
    tw, th = draw_text(window, layout, gc, text, area[0], area[1]+2*bar_height, area[2], area[3], maxw = 200, xoffset=bar_height)
    if bars:
        if bars[0][0] > maxwidth - 6:
            bars[0][0] = maxwidth - 6; bars[0][1] = 6
        for bar in bars:
            paint_box(context, innercolor, 0, 0, bar[0], y, bar[1], bar_height)
    return [int(a) for a in area]

def paint_box(context, color, xpadding, ypadding, x, y, width, height, rounded = 0, border_color = None):
    """
    Paint a box

    Arguments:
    - context: A cairo context to draw on
    - color: a rgba tuple
    - xpadding: amount to decrese the boxes size horizontally
    - ypadding: amount to decrese the boxes size vertically
    - x: The start x postion
    - y: The start y position
    - width: The boxes width
    - height: The height of the box
    - rounded(optional): Make rounded using this radius
    - border_color(optional): a border color
    """
    x = x + xpadding
    y = y + ypadding
    width = width - 2*xpadding
    height = height - 2*ypadding
    context.set_source_rgba(*color)
    if rounded:
        w, h, r = width, height, rounded
        context.move_to(x+r,y)
        context.line_to(x+w-r,y)
        context.curve_to(x+w,y,x+w,y,x+w,y+r)
        context.line_to(x+w,y+h-r)
        context.curve_to(x+w,y+h,x+w,y+h,x+w-r,y+h)
        context.line_to(x+r,y+h)
        context.curve_to(x,y+h,x,y+h,x,y+h-r)
        context.line_to(x,y+r)
        context.curve_to(x,y,x,y,x+r,y)
    else:
        context.rectangle(x+0.5, y, width, height)
    context.fill()
    if border_color:
        context.set_line_width(1)
        context.set_source_rgba
        context.stroke()

def draw_time_markers(window, event, layout, gc, height):
    """
    Draws strings and lines representing times
    """
    maxheight = window.get_geometry()[3]
    e =  event.area.width
    v = 6.0
    points = [e*(x/v) for x in xrange(1, int(v))]
    i = 0
    for point in points:
        layout.set_markup("<b>"+TIMES[i]+"</b>")
        w, h = layout.get_pixel_size()
        window.draw_layout(gc, int(point - w/2), int((height-h)/2), layout)
        i += 1
    return


class DetailedView(gtk.DrawingArea):
    """
    A gtk widget which displays a bunch of rows with items representing a
    section of time where they were used
    """
    __datastore__ = tuple()
    __gsignals__ = {
        # Sent when data is updated
        "data-updated" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,()),
        # Sent when a public area is clicked
        "area-clicked" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        # Sent when a private area is clicked
        "private-area-clicked" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
    }
    __events__ = (
        gdk.ENTER_NOTIFY_MASK | gdk.LEAVE_NOTIFY_MASK |
        gdk.KEY_PRESS_MASK | gdk.BUTTON_RELEASE_MASK | gdk.BUTTON_PRESS_MASK |
        gdk.MOTION_NOTIFY
    )
    __connections__ = {
        "expose-event":"__expose__",
        "button_press_event": "__button_press_handler__",
        "button_release_event": "__button_release_handler__",
        "motion_notify_event": "__motion_notify_handler__",
        "style-set": "change_style",
    }
    # Click handling areas
    __private_areas__ = {}
    __areas__ = {}
    __active_area__ =  tuple()
    # Geometry stuff
    header_height = 15
    row_height = 50
    spacing = 4
    yincrement = row_height + spacing
    # Style stuff
    gc = None
    lightgc = None
    pangofont = None
    font_name = ""
    font_size =  7*1024
    bg_color = (1, 1, 1, 1)
    base_color = (1, 1, 1, 1)
    font_color = (0, 0, 0, 0)
    stroke_color = (1, 1, 1, 1)
    selected_color = (1, 1, 1, 1)
    selected_color_alternative = (1, 1, 1, 1)
    __last_width__ = 0

    def __init__(self, fn=None):
        super(DetailedView, self).__init__()
        if fn: self.set_text_handler(fn)
        self.set_size_request(600, 800)
        self.set_events(self.__events__)
        self.set_property("has-tooltip", True)
        self.handcursor = gtk.gdk.Cursor(gtk.gdk.HAND2)
        for key, val in self.__connections__.iteritems():
            self.connect(key, getattr(self, val))
        self.clear_registered_areas()

    def text_handler(self, obj):
        """
        A default text handler that returns the text to be drawn by the
        draw_text_box

        Arguments:
        - obj: A event object
        """
        text = obj.subjects[0].text
        t1 = "<b>" + text + "</b>"
        interpretation = obj.subjects[0].interpretation
        t2 = FILETYPESNAMES[obj.subjects[0].interpretation] if interpretation in FILETYPESNAMES.keys() else "Unknown"
        t3 = time.strftime("%H:%M", time.localtime(int(obj.timestamp)/1000))
        return str(t1) + "\n" + str(t2) + ", " + str(t3)

    def set_text_handler(self, fn):
        """
        Sets the instances text handler function

        Arguments:
        - fn: A text handler function
        """
        if callable(fn):
            self.text_handler = fn
            return
        raise TypeError("fn is not callable")

    def register_area(self, obj, x, y, width, height, private = False):
        """
        Register a area that contains a object

        Arguments:
        - obj: a zeitgeist event object
        - x: The start x postion
        - y: The start y position
        - width: The boxes width
        - height: The height of the box
        - private(optional): Add the item to the private areas
        """
        if private:
            self.__private_areas__[(x, y, width, height)] = obj
        else:
            self.__areas__[(x, y, width, height)] = obj

    def clear_registered_areas(self, private = False):
        """
        Clear registered areas

        Arguments:
        - private(Optional): If True we clear private areas as well
        """
        if private: self.__private_areas__ = {}
        self.__areas__ = {}

    def check_area(self, mousex, mousey):
        """
        Returns a the area of the clicked area, and the associated object
        or False if no area matched

        Arguments:
        - mousex: x mouse cord to check
        - mousey: y mouse cord to check
        """
        if self.__private_areas__:
            for (x, y, width, height), obj in self.__private_areas__.iteritems():
                if y <= mousey <= y + height:
                    if x <= mousex <= x + width:
                        return (x, y, width, height), obj
        if self.__areas__:
            for (x, y, width, height), obj in self.__areas__.iteritems():
                if y <= mousey <= y + height:
                    if x <= mousex <= x + width:
                        return (x, y, width, height), obj
        return False

    def __motion_notify_handler__(self, widget, event):
        val = self.check_area(event.x, event.y)
        if val:
            widget.window.set_cursor(self.handcursor)
            return True
        widget.window.set_cursor(None)
        return False

    def __button_press_handler__(self, widget, event):
        """
        A simple button press handler that emits signals based on matched areas

        Arguments:
        - widget: the clicked widget
        - event: the event

        Emits:
        - private-area-clicked: Emitted if a registered private area is clicked
        - area-clicked: Emitted when a registered area is clicked
        """
        val = self.check_area(event.x, event.y)
        if not val:
            self.__active_area__ = None
            self.queue_draw()
            return False
        area, obj = val
        self.__active_area__ = area
        if obj in self.__private_areas__.values():
            self.emit("private-area-clicked", obj)
            return True
        self.emit("area-clicked", obj)
        self.queue_draw()
        return True

    def __button_release_handler__(self, widget, event):
        """Place holder"""
        pass

    def __expose__(self, widget, event):
        """
        The main expose function
        """
        self.clear_registered_areas(private=True)
        widget.style.set_background(widget.window, gtk.STATE_NORMAL)
        context = widget.window.cairo_create()
        layout = widget.create_pango_layout("")
        if not self.gc:
            self.gc = get_gc_from_colormap(widget.style, "text_gc", 0)
        if not self.lightgc:
            self.lightgc = get_gc_from_colormap(widget.style, "text_gc", 4)
        layout.set_font_description(widget.pangofont)
        draw_time_markers(widget.window, event, layout, self.lightgc, self.header_height)
        self.expose(widget, event, context, layout)

    def expose(self, widget, event, context, layout):
        """The minor expose function"""
        style = widget.style
        shadow = gtk.SHADOW_OUT
        state = gtk.STATE_NORMAL
        y = 2 * self.header_height
        i = 0
        for rows in self.get_datastore():
            obj, duration = rows[0]
            barsizes = []
            for row in rows:
                barsizes.append(make_area_from_event(0, event.area.width, row[0].timestamp, row[1]))
            barsize = barsizes[0]
            text = self.text_handler(obj)
            area = draw_text_box(
                widget.window, context, layout, self.gc, self.base_color, text, barsize[0],
                y, event.area.width, self.row_height,
                ftype = obj.subjects[0].interpretation, fmime=obj.subjects[0].mimetype, bars = barsizes)
            if self.__active_area__ == tuple(area):
                widget.style.paint_focus(widget.window, gtk.STATE_ACTIVE, event.area, widget, None, *area)
            self.register_area(obj, *area)
            y += self.yincrement
            i += 1
        self.__last_width__ = event.area.width
        if y > event.area.height:
            self.set_size_request(event.area.width, y + self.spacing)
        return True

    def set_datastore(self, datastore, draw = True):
        """
        Sets the objects datastore attribute using a list

        Arguments:
        - datastore:
        """
        if datastore:
            if isinstance(datastore, tuple):
                datastore =  list(datastore)
            if isinstance(datastore, list):
                self.__datastore__ = datastore
            else:
                raise TypeError("Datastore is not a <list>")
        else:
            self.__datastore__ = []
        self.clear_registered_areas(private=True)
        self.emit("data-updated")
        self.queue_draw()

    def get_datastore(self):
        """
        Returns the instances datastore
        """
        return self.__datastore__

    def change_style(self, widget, old_style):
        """
        Sets the widgets style and coloring
        """
        self.handcursor = gtk.gdk.Cursor(gtk.gdk.HAND2)
        self.selected_color = get_gtk_rgba(self.style, "bg", 3)
        self.selected_color_alternative = (1, 0.68, 0.24, 1)
        self.font_name = self.style.font_desc.get_family()
        self.bg_color = get_gtk_rgba(self.style, "bg", 0)
        self.base_color = get_gtk_rgba(self.style, "base", 0,)
        self.stroke_color = get_gtk_rgba(self.style, "bg", 0, 0.95)
        self.font_size = self.style.font_desc.get_size()
        self.header_height = self.font_size/1024 + self.spacing*2
        self.pangofont = pango.FontDescription(self.font_name)
        self.pangofont.set_size(self.font_size)
        layout = widget.create_pango_layout("SAMPLE")
        layout.set_font_description(widget.pangofont)
        yw, th = layout.get_pixel_size()
        spacing = layout.get_spacing()
        spacing =  spacing if spacing else 1024
        h = (th)*2 + (spacing/1024)*4 + 10
        self.row_height = max(h, DetailedView.row_height)
        self.yincrement = self.row_height + self.spacing
        self.gc = get_gc_from_colormap(widget.style, "text_gc", 0)
        self.__last_width__ = 0
        self.queue_draw()
