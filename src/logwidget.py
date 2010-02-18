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
import time
import math
import operator

from zeitgeist.datamodel import Interpretation
from widgets import StaticPreviewTooltip, VideoPreviewTooltip
from gio_file import GioFile

gdk = gtk.gdk


TIMES = ("4:00", "8:00", "12:00", "16:00",
         "20:00", "22:00",)

TANGOCOLORS = (
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

FILETYPES = {
    Interpretation.VIDEO.uri : 0,
    Interpretation.MUSIC.uri : 3,
    Interpretation.DOCUMENT.uri : 12,
    Interpretation.IMAGE.uri : 15,
    Interpretation.SOURCECODE.uri : 12,
    Interpretation.UNKNOWN.uri : 21,
    }

FILETYPESNAMES = {
    Interpretation.VIDEO.uri : _("Video"),
    Interpretation.MUSIC.uri : _("Music"),
    Interpretation.DOCUMENT.uri : _("Document"),
    Interpretation.IMAGE.uri : _("Image"),
    Interpretation.SOURCECODE.uri : _("Source Code"),
    Interpretation.UNKNOWN.uri : _("Unknown"),
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

def get_file_color(ftype, fmime):
    """Uses hashing to choose a shade from a hue in the color tuple above
    """
    if ftype in FILETYPES.keys():
        i = FILETYPES[ftype]
        l = int(math.fabs(hash(fmime))) % 3
        return TANGOCOLORS[min(i+l, len(TANGOCOLORS)-1)]
    return (136/255.0, 138/255.0, 133/255.0)

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


def draw_text(widget, gc, text, x, y, xcenter = False,
              ycenter = False, xoffset= 0, yoffset= 0, maxw = 0):
    """
    draw text using this function

    Arguments:
    - widget: a widget with a window to draw on
    - gc: a text_gc from style
    - text: the text to draw
    - x: The start x postion
    - y: The start y position
    - xcenter(optional) True/False. Should we center text on x/y
    - ycenter(optional)
    - xoffset: amount to offset the x
    - yoffset: amount to offset the y
    - maxw: max string width
    """
    x += xoffset
    y += yoffset
    layout = widget.create_pango_layout("")
    layout.set_markup(text)
    layout.set_spacing(1024)
    text_w, text_h = layout.get_pixel_size()
    layout.set_width(maxw*1024)
    layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
    widget.window.draw_layout(
        gc, int(x + text_w/2 if xcenter else x),
        int(y + text_h/2 if ycenter else y), layout)
    layout.set_spacing(0)
    return text_h, text_w

def paint_box(context, color, xpadding, ypadding, x, y, width,
              height, rounded = 0, border_color = None):
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
        context.rectangle(int(x), int(y), int(width), int(height))
    context.fill()
    if border_color:
        context.set_line_width(1)
        context.set_source_rgba(border_color)
        context.stroke()

def draw_event_widget(widget, gc, basecolor, innercolor, text, x, y, maxwidth, maxheight, bars):
    """
    Draws text with time signifiers

    Arguments:
    - widget: a widget with a window to draw on
    - gc: a text_gc from style
    - basecolor: a rgba tuple for the backdrop bar
    - innercolor: the bar color
    - text: the text to draw
    - x: The start x postion
    - y: The start y position
    - maxwidth: The boxes max width
    - maxheight: The max height of the box
    - bars: a list of bar tuples with (x, width) values to draw
    """
    layout = widget.create_pango_layout("")
    layout.set_width(150*1024)
    layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
    context = widget.window.cairo_create()
    bar_height = 3
    layout.set_markup(text)
    text_width, text_height  = layout.get_pixel_size()
    width = (bars[-1][0] + bars[-1][1]) - bars[0][0]
    if x + text_width > maxwidth:
        area = (maxwidth - text_width, y, text_width, maxheight)
    else: area = (x, y, max(text_width, width), maxheight)
    tw, th = draw_text(widget, gc, text, area[0], area[1]+2*bar_height, maxw = 150, xoffset=bar_height)
    paint_box(context, basecolor, 0, 0, area[0], y, area[2], bar_height)
    if bars[0][0] > maxwidth - 6:
        bars[0][0] = maxwidth - 6; bars[0][1] = 6
    for bar in bars:
        paint_box(context, innercolor, 0, 0, bar[0], y, bar[1], bar_height)
    return [int(a) for a in area]

def draw_time_markers(window, event, layout, gc, height):
    """
    Draws strings and lines representing times
    """
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
    _datastore = tuple()
    __gsignals__ = {
        # Sent when data is updated
        "data-updated" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,()),
        # Sent when a public area is clicked
        "area-clicked" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        # Sent when a private area is clicked
        "private-area-clicked" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
    }
    _events = (
        gdk.ENTER_NOTIFY_MASK | gdk.LEAVE_NOTIFY_MASK |
        gdk.KEY_PRESS_MASK | gdk.BUTTON_RELEASE_MASK | gdk.BUTTON_PRESS_MASK |
        gdk.MOTION_NOTIFY
    )
    _connections = {
        "expose-event":"_expose",
        "button_press_event": "button_press_handler",
        "button_release_event": "button_release_handler",
        "motion_notify_event": "motion_notify_handler",
        "style-set": "change_style",
        "key_press_event": "key_press_handler",
        "query-tooltip" : "query_tooltip", # Enable to enable tooltips
        "focus-out-event" : "focus_out_handler",
    }
    # Click handling areas
    _private_areas = {}
    _areas = {}
    _active_area =  tuple()
    # Geometry stuff
    _header_height = 15
    _row_height = 32
    _spacing = 4
    yincrement = _row_height + _spacing
    # Style stuff
    gc = None
    lightgc = None
    pangofont = None
    font_name = ""
    font_size =  7*1024
    colors = {
        "bg" : (1, 1, 1, 1),
        "base" : (1, 1, 1, 1),
        "font" : (0, 0, 0, 0),
        "f" : "#b3b3b3"
        }

    # new stuff for clicking and tooltips
    _currently_active_obj = None

    def __init__(self, fn=None):
        super(DetailedView, self).__init__()
        if fn: self.set_text_handler(fn)
        self.set_size_request(600, 800)
        self.set_events(self._events)
        self.set_property("has-tooltip", True)
        self.set_tooltip_window(StaticPreviewTooltip)
        self.set_flags(gtk.CAN_FOCUS)
        self.handcursor = gtk.gdk.Cursor(gtk.gdk.HAND2)
        for key, val in self._connections.iteritems():
            self.connect(key, getattr(self, val))
        self.clear_registered_areas()

    def text_handler(self, obj):
        """
        A default text handler that returns the text to be drawn by the
        draw_event_widget

        Arguments:
        - obj: A event object
        """
        text = obj.subjects[0].text
        interpretation = obj.subjects[0].interpretation
        t1 = (FILETYPESNAMES[interpretation] if
              interpretation in FILETYPESNAMES.keys() else "Unknown")
        t1 = "<b>" + t1 + "</b>"
        t2 = "<span color='%s'>%s</span> " % (self.colors["f"], text)
        return (str(t1) + "\n" + str(t2) + "").replace("&", "&amp;")

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
            self._private_areas[(x, y, width, height)] = obj
        else:
            self._areas[(x, y, width, height)] = obj

    def clear_registered_areas(self, private = False):
        """
        Clear registered areas

        Arguments:
        - private(Optional): If True we clear private areas as well
        """
        if private: self._private_areas = {}
        self._areas = {}

    def check_area(self, mousex, mousey):
        """
        Returns a the area of the clicked area, and the associated object
        or False if no area matched

        Arguments:
        - mousex: x mouse cord to check
        - mousey: y mouse cord to check
        """
        if self._private_areas:
            for (x, y, width, height), obj in self._private_areas.iteritems():
                if y <= mousey <= y + height:
                    if x <= mousex <= x + width:
                        return (x, y, width, height), obj
        if self._areas:
            for (x, y, width, height), obj in self._areas.iteritems():
                if y <= mousey <= y + height:
                    if x <= mousex <= x + width:
                        return (x, y, width, height), obj
        return False

    def focus_out_handler(self, widget, event):
        self._active_area = None
        self.queue_draw()

    def query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """
        Uses _currently_active_obj to check the tooltip
        _currently_active_obj is a zeitgeist event

        There is a important issue here, I switch tooltip types depending on
        the interpretation, but that is very inefficient. We really need a
        tooltip class which can decide what type it is when givin the uri. Until
        then we have this issue.
        """
        if widget._currently_active_obj:
            interpretation = widget._currently_active_obj.subjects[0].interpretation
            if interpretation == Interpretation.VIDEO.uri:
                self.set_tooltip_window(VideoPreviewTooltip)
            else:
                self.set_tooltip_window(StaticPreviewTooltip)
            tooltip_window = widget.get_tooltip_window()
            gio_file = GioFile.create(widget._currently_active_obj.subjects[0].uri)
            return tooltip_window.preview(gio_file)
        return False

    def motion_notify_handler(self, widget, event):
        """
        Changes the cursor on motion and also sets the _currently_active_obj property
        so query_tooltip does not have to think
        """
        val = self.check_area(event.x, event.y)
        if val:
            widget.window.set_cursor(self.handcursor)
            self._currently_active_obj = val[1]
            return True
        widget.window.set_cursor(None)
        self._currently_active_obj = None
        return False

    def button_press_handler(self, widget, event):
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
            self._active_area = None
            self.queue_draw()
            return False
        area, obj = val
        self._active_area = area
        if obj in self._private_areas.values():
            self.emit("private-area-clicked", obj)
            return True
        self.emit("area-clicked", obj)
        self.queue_draw()
        return True

    def button_release_handler(self, widget, event):
        """ Disables the active area on a released click
        """
        self._active_area = None
        self.queue_draw()

    def key_press_handler(self, widget, event):
        """
        Handles keyboard navigation

        Up, Down, and Space are all used
        """
        if event.keyval in (gtk.keysyms.Down, gtk.keysyms.Up, gtk.keysyms.space):
            areas = self._areas.keys()
            areas.sort(key=operator.itemgetter(1))
            if not self._active_area:
                self._active_area = areas[0]
            elif event.keyval == gtk.keysyms.space:
                if self._active_area:
                    obj = self._areas[self._active_area]
                    self.emit("area-clicked", obj)
            elif self._active_area and self._areas:
                try:
                    i = areas.index(self._active_area)
                    if event.keyval == gtk.keysyms.Down:
                        i += 1
                    else:
                        i -= 1
                    i = min(max(i, 0), len(areas)-1)
                    self._active_area = areas[i]
                except ValueError:
                    self._active_area = areas[0]
            self.queue_draw()
            return True
        return False

    def _expose(self, widget, event):
        """
        The main expose method that calls all the child functions and methods
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
        draw_time_markers(widget.window, event, layout, self.lightgc, self._header_height)
        self.expose(widget, event, context, layout)

    def expose(self, widget, event, context, layout):
        """The minor expose method that handles item drawing"""
        y = 2 * self._header_height
        for rows in self.get_datastore():
            obj, duration = rows[0]
            subject = obj.subjects[0]
            bars = [make_area_from_event(0, event.area.width, row[0].timestamp, row[1])
                        for row in rows]
            text = self.text_handler(obj)
            color = get_file_color(subject.interpretation, subject.mimetype)
            area = draw_event_widget(widget, self.gc, self.colors["bg"], color,
                                     text, bars[0][0], y, event.area.width,
                                     self._row_height, bars)
            if self._active_area == tuple(area):
                widget.style.paint_focus(widget.window, gtk.STATE_ACTIVE,
                                         event.area, widget, None, *area)
            self.register_area(obj, *area)
            y += self.yincrement
        self.set_size_request(int(event.area.width), int(y + self._spacing))
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
                self._datastore = datastore
            else:
                raise TypeError("Datastore is not a <list>")
        else:
            self._datastore = []
        self.clear_registered_areas(private=True)
        self.clear_registered_areas()
        self.emit("data-updated")
        self.queue_draw()

    def get_datastore(self):
        """
        Returns the instances datastore
        """
        return self._datastore

    def change_style(self, widget, old_style):
        """
        Sets the widgets style and coloring
        """
        self.handcursor = gtk.gdk.Cursor(gtk.gdk.HAND2)
        self.font_name = self.style.font_desc.get_family()
        self.colors["bg"] = get_gtk_rgba(self.style, "bg", 0, 1.04)
        self.colors["base"] = get_gtk_rgba(self.style, "base", 0,)
        f_color = widget.style.text[4]
        f_color.red = max(f_color.red * 60/100, 0)
        f_color.green = max(f_color.green * 60/100, 0)
        f_color.blue = max(f_color.blue * 60/100, 0)
        self.colors["f"] = f_color
        self.font_size = self.style.font_desc.get_size()
        self._header_height = self.font_size/1024 + self._spacing*2
        self.pangofont = pango.FontDescription(self.font_name)
        self.pangofont.set_size(self.font_size)
        layout = widget.create_pango_layout("SPpq|I\nSPpqI|")
        layout.set_font_description(widget.pangofont)
        yw, th = layout.get_pixel_size()
        self._row_height = max(th*1.3, DetailedView._row_height)
        self.yincrement = self._row_height + self._spacing
        self.gc = get_gc_from_colormap(widget.style, "text_gc", 0)
        self.queue_draw()
