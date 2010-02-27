# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
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

# Purpose:

import cairo
import gobject
import gtk
import pango
import pangocairo
import string
import time
import math
import operator
import threading

from zeitgeist.datamodel import Interpretation
from gio_file import GioFile
from widgets import StaticPreviewTooltip, VideoPreviewTooltip, ContextMenu
from common import *
from thumb import PreviewRenderer

def make_area_from_event(timestamp, duration):
    """
    Generates a time box based on a objects timestamp and duration over 1.
    Multiply the results by the width to get usable positions

    :param timestamp: a timestamp int or string from which to calulate the start position
    :param duration: the length to calulate the width
    """
    w = max(duration/3600.0/1000.0/24.0, 0)
    x = ((int(timestamp)/1000.0 - time.timezone)%86400)/3600/24.0
    return [x, w]

def text_handler(obj):
    """
    A default text handler that returns the text to be drawn by the
    draw_event_widget

    :param obj: a :class:`Events <zeitgeist.datamodel.Event>`
    """
    text = get_event_text(obj)
    interpretation = get_event_interpretation(obj)
    t = (FILETYPESNAMES[interpretation] if
          interpretation in FILETYPESNAMES.keys() else "Unknown")
    text = text.replace("%", "%%")
    t1 = "<span color='!color!'><b>" + t + "</b></span>"
    t2 = "<span color='!color!'>" + text + "</span> "
    return (str(t1) + "\n" + str(t2) + "").replace("&", "&amp;").replace("!color!", "%s")


class Plug(object):
    """
    A pointer/reference holder that makes up for the inability to access a
    model directly from within a cellrenderer. So instances holds a reference
    to a object in 'obj'.
    """
    obj = None


class TimelineRenderer(gtk.GenericCellRenderer):
    """
    Renders timeline columns, and text for a for properties
    """

    __gtype_name__ = "TimelineRenderer"
    __gproperties__ = {
        "phases" :
        (gobject.TYPE_PYOBJECT,
         "The time phases to be drawn",
         "A list of time phases",
         gobject.PARAM_READWRITE,
         ),
        "event" :
        (gobject.TYPE_PYOBJECT,
         "event to be displayed",
         "event to be displayed",
         gobject.PARAM_READWRITE,
         ),
        "color" :
        (gobject.TYPE_PYOBJECT,
         "color to be displayed",
         "color to be displayed",
         gobject.PARAM_READWRITE,
         ),
        "text":
        (gobject.TYPE_STRING,
         "text to be displayed",
         "text",
         "",
         gobject.PARAM_READWRITE,
         ),
        "pixbuf_plug" :
        (gobject.TYPE_PYOBJECT,
         "A pixbuf representation",
         "A gtk.gdk.Pixbuf",
         gobject.PARAM_READWRITE,
         ),
        "usethumb" :
        (gobject.TYPE_BOOLEAN,
         "Should the renderer use a thumb",
         "True if pixbuf should be a thumb",
         False,
         gobject.PARAM_READWRITE),

    }

    width = 32
    height = 48
    barsize = 5
    properties = {}

    textcolor = {gtk.STATE_NORMAL : ("#ff", "#ff"),
                 gtk.STATE_SELECTED : ("#ff", "#ff")}

    @property
    def phases(self):
        return self.get_property("phases")
    @property
    def event(self):
        return self.get_property("event")
    @property
    def color(self):
        return self.get_property("color")
    @property
    def text(self):
        return self.get_property("text")

    @property
    def pixbuf_plug(self):
        return self.get_property("pixbuf_plug")
    #@property
    def __pixbuf(self):
        return self.pixbuf_plug.obj
    #@pixbuf.setter
    def __pixbuf_setter(self, obj):
        self.pixbuf_plug.obj = obj
    # For compatibility with Python 2.5
    pixbuf = property(__pixbuf, __pixbuf_setter)

    @property
    def usethumb(self):
        return self.get_property("usethumb")

    def __init__(self):
        super(TimelineRenderer, self).__init__()
        self.properties = {}
        self.set_fixed_size(self.width, self.height)
        self.set_property("mode", gtk.CELL_RENDERER_MODE_ACTIVATABLE)

    def do_set_property(self, pspec, value):
        self.properties[pspec.name] = value

    def do_get_property(self, pspec):
        return self.properties[pspec.name]

    def on_get_size(self, widget, area):
        if area:
            return (0, 0, area.width, area.height)
        return (0,0,0,0)

    def on_render(self, window, widget, background_area, cell_area, expose_area, flags):
        """
        The primary rendering function. It calls either the classes rendering functions
        or special one defined in the rendering_functions dict
        """
        x = int(cell_area.x)
        y = int(cell_area.y)
        w = int(cell_area.width)
        h = int(cell_area.height)
        self.render_phases(window, widget, x, y, w, h, flags)
        return True

    def render_phases(self, window, widget, x, y, w, h, flags):
        context = window.cairo_create()
        phases = self.phases
        for start, end in phases:
            context.set_source_rgb(*self.color)
            start = int(start * w)
            end = max(int(end * w), 8)
            if start + 8 > w:
                start = w - 8
            context.rectangle(x+ start, y, end, self.barsize)
            context.fill()
            i = (TANGOCOLORS.index(self.color)/3)*3
            if i == TANGOCOLORS.index(self.color): i += 1
            color = TANGOCOLORS[i]
            context.set_source_rgb(*color)
            context.set_line_width(1)
            context.rectangle(x + start+0.5, y+0.5, end, self.barsize)
            context.stroke()
        x = int(phases[0][0]*w)
        # Pixbuf related junk which is really dirty
        uri = get_event_uri(self.event)
        thumb = False
        if not self.pixbuf:
            if PIXBUFCACHE.has_key(uri) and self.usethumb:
                pixbuf, thumb = PIXBUFCACHE[uri]
                self.pixbuf = pixbuf.scale_simple(32, 24, gtk.gdk.INTERP_TILES)
            else:
                self.pixbuf = get_event_icon(self.event, 24)
        if PIXBUFCACHE.has_key(uri) and self.usethumb and self.pixbuf != PIXBUFCACHE[uri][0]:
            pixbuf, thumb = PIXBUFCACHE[uri]
            self.pixbuf = pixbuf.scale_simple(32, 24, gtk.gdk.INTERP_TILES)
        self.render_text_with_pixbuf(window, widget, x, y, w, h, flags, drawframe = thumb)
        return True

    def render_text_with_pixbuf(self, window, widget, x, y, w, h, flags, drawframe = True):
        uri = get_event_uri(self.event)
        imgw, imgh = self.pixbuf.get_width(), self.pixbuf.get_height()
        x = max(x + imgw/2 + 4, 0 + imgw + 4)
        x, y = self.render_text(window, widget, x, y, w, h, flags)
        x -= imgw + 4
        y += self.barsize + 3
        render_pixbuf(window, x, y, self.pixbuf, drawframe=drawframe)

    def render_text(self, window, widget, x, y, w, h, flags):
        w = window.get_geometry()[2]
        y+= 2
        x += 5
        state = gtk.STATE_SELECTED if gtk.CELL_RENDERER_SELECTED & flags else gtk.STATE_NORMAL
        color1, color2 = self.textcolor[state]
        text = self.text % (color1.to_string(), color2.to_string())
        layout = widget.create_pango_layout("")
        layout.set_markup(text)

        textw, texth = layout.get_pixel_size()
        if textw + x > w:
            layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
            layout.set_width(200*1024)
            textw, texth = layout.get_pixel_size()
            if x + textw > w:
                x = w - textw
        context = window.cairo_create()
        pcontext = pangocairo.CairoContext(context)
        pcontext.set_source_rgb(0, 0, 0)
        pcontext.move_to(x, y + self.barsize)
        pcontext.show_layout(layout)
        return x, y

    def on_start_editing(self, event, widget, path, background_area, cell_area, flags):
        pass

    def on_activate(self, event, widget, path, background_area, cell_area, flags):
        pass


gobject.type_register(TimelineRenderer)


class TimelineView(gtk.TreeView):
    child_width = TimelineRenderer.width
    child_height = TimelineRenderer.height
    def __init__(self):
        super(TimelineView, self).__init__()
        self.popupmenu = ContextMenu
        self.add_events(gtk.gdk.LEAVE_NOTIFY_MASK)
        self.connect("button-press-event", self.on_button_press)
        # self.connect("motion-notify-event", self.on_motion_notify)
        # self.connect("leave-notify-event", self.on_leave_notify)
        self.connect("row-activated" , self.on_activate)
        self.connect("style-set", self.change_style)
        pcolumn = gtk.TreeViewColumn("Timeline")
        self.render = render = TimelineRenderer()
        pcolumn.pack_start(render)
        self.append_column(pcolumn)
        pcolumn.add_attribute(render, "phases", 0)
        pcolumn.add_attribute(render, "event", 1)
        pcolumn.add_attribute(render, "color", 2)
        pcolumn.add_attribute(render, "text", 3)
        pcolumn.add_attribute(render, "pixbuf_plug", 4)
        pcolumn.add_attribute(render, "usethumb", 5)
        self.set_headers_visible(False)
        self.connect("query-tooltip", self.query_tooltip)
        self.set_property("has-tooltip", True)
        self.set_tooltip_window(StaticPreviewTooltip)


    def set_model_from_list(self, events):
        """
        Sets creates/sets a model from a list of zeitgeist events

        :param events: a list of :class:`Events <zeitgeist.datamodel.Event>`
        """
        if not events:
            self.set_model(None)
            return
        liststore = gtk.ListStore(gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT,
                                  gobject.TYPE_PYOBJECT, gobject.TYPE_STRING,
                                  gobject.TYPE_PYOBJECT, gobject.TYPE_BOOLEAN)
        for row in events:
            event = row[0][0]
            interpretation = get_event_interpretation(event)
            mimetype = get_event_mimetype(event)
            color = get_file_color(interpretation, mimetype)
            bars = [make_area_from_event(event.timestamp, stop) for (event, stop) in row]
            text = text_handler(event)
            usethumb = (True if get_event_interpretation(event)
                        in MEDIAINTERPRETATIONS else False)
            liststore.append((bars, event, color, text, Plug(), usethumb))
        self.set_model(liststore)

    def on_button_press(self, widget, event):
        if event.button == 3:
            path = self.get_dest_row_at_pos(int(event.x), int(event.y))
            if path:
                model = self.get_model()
                uri = get_event_uri(model[path[0]][1])
                self.popupmenu.do_popup(event.time, [uri])
                return True
        return False

    def on_leave_notify(self, widget, event):
        return True

    def on_motion_notify(self, widget, event):
        return True

    def on_activate(self, widget, path, column):
        model = self.get_model()
        launch_event(model[path][1])

    def query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """
        Displays a tooltip based on x, y
        """
        model, paths = self.get_selection().get_selected_rows()
        path = self.get_dest_row_at_pos(int(x), int(y))
        if path and path[0] in paths:
            model = self.get_model()
            event = model[path[0]][1]
            uri = get_event_uri(event)
            interpretation = get_event_interpretation(event)
            tooltip_window = widget.get_tooltip_window()
            if interpretation == Interpretation.VIDEO.uri:
                self.set_tooltip_window(VideoPreviewTooltip)
            else:
                self.set_tooltip_window(StaticPreviewTooltip)
            gio_file = GioFile.create(uri)
            return tooltip_window.preview(gio_file)
        return False

    def change_style(self, widget, old_style):
        """
        Sets the widgets style and coloring
        """
        layout = self.create_pango_layout("")
        layout.set_markup("<b>qPqPqP|</b>\nqPqPqP|")
        tw, th = layout.get_pixel_size()
        self.render.height = max(TimelineRenderer.height, th + 3 + TimelineRenderer.barsize)
        if self.window:
            width = self.window.get_geometry()[2] - 4
            self.render.width = max(TimelineRenderer.width, width)
        self.render.set_fixed_size(self.render.width, self.render.height)
        def change_color(color, inc):
            color = shade_gdk_color(color, inc/100.0)
            return color
        normal = (self.style.text[gtk.STATE_NORMAL], change_color(self.style.text[gtk.STATE_INSENSITIVE], 70))
        selected = (self.style.text[gtk.STATE_SELECTED], self.style.text[gtk.STATE_SELECTED])
        self.render.textcolor[gtk.STATE_NORMAL] = normal
        self.render.textcolor[gtk.STATE_SELECTED] = selected


class TimelineHeader(gtk.DrawingArea):
    time_text = {4:"4:00", 8:"8:00", 12:"12:00", 16:"16:00", 20:"20:00"}
    odd_line_height = 6
    even_line_height = 12

    line_color = (0, 0, 0, 1)
    def __init__(self):
        super(TimelineHeader, self).__init__()
        self.connect("expose-event", self.expose)
        self.connect("style-set", self.change_style)
        self.set_size_request(100, 12)

    def expose(self, widget, event):
        window = widget.window
        context = widget.window.cairo_create()
        layout = self.create_pango_layout("   ")
        width = event.area.width
        widget.style.set_background(window, gtk.STATE_NORMAL)
        context.set_source_rgba(*self.line_color)
        context.set_line_width(2)
        self.draw_lines(window, context, layout, width)

    def draw_text(self, window, context, layout, x, text):
        x = int(x)
        color = self.style.text[gtk.STATE_NORMAL]
        markup = "<span color='%s'>%s</span>" % (color.to_string(), text)
        pcontext = pangocairo.CairoContext(context)
        layout.set_markup(markup)
        xs, ys = layout.get_pixel_size()
        pcontext.move_to(x - xs/2, 0)
        pcontext.show_layout(layout)

    def draw_line(self, window, context, x, even):
        x = int(x)+0.5
        height = self.even_line_height if even else self.odd_line_height
        context.move_to(x, 0)
        context.line_to(x, height)
        context.stroke()

    def draw_lines(self, window, context, layout, width):
        xinc = width/24
        for hour in xrange(1, 24):
            if self.time_text.has_key(hour):
                self.draw_text(window, context, layout, xinc*hour, self.time_text[hour])
            else:
                self.draw_line(window, context, xinc*hour, bool(hour % 2))

    def change_style(self, widget, old_style):
        layout = self.create_pango_layout("")
        layout.set_markup("<b>qPqPqP|</b>")
        tw, th = layout.get_pixel_size()
        self.set_size_request(tw*5, th+4)
        self.line_color = get_gtk_rgba(widget.style, "bg", 0, 0.94)



