# -.- coding: utf-8 -.-
#
# Filename
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

# Purpose:

import cairo
import gobject
import gtk
import pango
import pangocairo
import time
import math
import operator
import threading

from zeitgeist.datamodel import Interpretation

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

def make_area_from_event(timestamp, duration):
    """
    Generates a time box based on a objects timestamp and duration

    Arguments
    - x: The start x postion
    - max_width: The max gdk.window width
    - timestamp: a timestamp int or string from which to calulate the start position
    - duration: the length to calulate the width
    """
    w = max(duration/3600.0/1000.0/24.0, 1/72.0)
    x = ((int(timestamp)/1000.0 - time.timezone)%86400)/3600/24.0
    return [x, w]

def get_file_color(ftype, fmime):
    """Uses hashing to choose a shade from a hue in the color tuple above
    """
    if ftype in FILETYPES.keys():
        i = FILETYPES[ftype]
        l = int(math.fabs(hash(fmime))) % 3
        return TANGOCOLORS[min(i+l, len(TANGOCOLORS)-1)]
    return (136/255.0, 138/255.0, 133/255.0)

def text_handler(obj):
    """
    A default text handler that returns the text to be drawn by the
    draw_event_widget

    Arguments:
    - obj: A event object
    """
    text = obj.subjects[0].text
    interpretation = obj.subjects[0].interpretation
    t = (FILETYPESNAMES[interpretation] if
          interpretation in FILETYPESNAMES.keys() else "Unknown")
    t1 = "<span color='!s'><b>%s</b></span>" % t
    t2 = "<span color='!s'>%s</span> " % (text)
    return (str(t1) + "\n" + str(t2) + "").replace("&", "&amp;").replace("!s", "%s")

def launch_event(event):
    gfile = GioFile(event.subjects[0].uri)
    gfile.launch()


class TimelineRenderer(gtk.GenericCellRenderer):

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
    }

    width = 32
    height = 48
    barsize = 5
    properties = {}

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

    def __init__(self):
        super(TimelineRenderer, self).__init__()
        self.properties = {}
        self.set_fixed_size(self.width, self.height)
        self.style = gtk.widget_get_default_style()
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
        x = cell_area.x
        y = cell_area.y
        w = cell_area.width
        h = cell_area.height
        # test
        #context = window.cairo_create()
        #context.set_source_rgb(1, 0, 1)
        #context.rectangle(x + 2, y + 2, w - 4, h - 4)
        #context.fill_preserve()
        #context.stroke()
        self.render_phases(window, widget, x, y, w, h, flags)
        return True

    def render_phases(self, window, widget, x, y, w, h, flags):
        context = window.cairo_create()
        context.set_source_rgb(*self.color)
        phases = self.phases
        for start, end in phases:
            start = start * w
            end = end * w
            context.rectangle(x+ start, y, end, self.barsize)
            context.fill()
        x = phases[0][0]*w
        self.render_text(window, widget, x, y, w, h, flags)

    def render_text(self, window, widget, x, y, w, h, flags):
        w = window.get_geometry()[2]
        x += 5
        color1, color2 = self._handle_text_coloring(flags)
        text = self.text % (color1, color2)
        layout = widget.create_pango_layout("")
        layout.set_markup(text)

        textw, texth = layout.get_pixel_size()
        if textw + x > w:
            layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
            layout.set_width(200*1024)
            textw, texth = layout.get_pixel_size()
            if x + textw > w:
                x = w - textw
            pass
        context = window.cairo_create()
        pcontext = pangocairo.CairoContext(context)
        pcontext.set_source_rgb(0, 0, 0)
        pcontext.move_to(x, y + self.barsize)
        pcontext.show_layout(layout)

    def _handle_text_coloring(self, flags):
        if flags  == gtk.CELL_RENDERER_SELECTED:
            color1 = self.style.text[gtk.STATE_SELECTED]
            color2 = self.style.text[gtk.STATE_SELECTED]
        else:
            color1 = self.style.text[gtk.STATE_NORMAL]
            color2 = self.style.text[gtk.STATE_INSENSITIVE]
        return color1, color2

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
        self.add_events(gtk.gdk.LEAVE_NOTIFY_MASK)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("leave-notify-event", self.on_leave_notify)
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
        self.set_headers_visible(False)

    def set_model_from_list(self, events):
        """
        Sets creates/sets a model from a list of zeitgeist events
        Arguments:
        -- events: a list of events
        """
        if not events:
            self.set_model(None)
            return
        liststore = gtk.ListStore(gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT,
                                  gobject.TYPE_PYOBJECT, gobject.TYPE_STRING)
        for row in events:
            subject = row[0][0].subjects[0]
            color = get_file_color(subject.interpretation, subject.mimetype)
            bars = [make_area_from_event(event.timestamp, stop) for (event, stop) in row]
            text = text_handler(row[0][0])
            liststore.append((bars, row[0][0], color, text))
        self.set_model(liststore)

    def on_leave_notify(self, widget, event):
        return True

    def on_motion_notify(self, widget, event):
        return True

    def on_activate(self, widget, path, column):
        model = self.get_model()
        launch_event(model[path][1])

    def change_style(self, widget, old_style):
        """
        Sets the widgets style and coloring
        """
        color = widget.style.bg[gtk.STATE_NORMAL]
        color.red = min(color.red * 102/100, 65535.0)
        color.green = min(color.green * 102/100, 65535.0)
        color.blue = min(color.blue * 102/100, 65535.0)
        if color != widget.style.base[gtk.STATE_NORMAL]:
            self.modify_base(gtk.STATE_NORMAL, color)
        # get size
        layout = self.create_pango_layout("")
        layout.set_markup("<b>qPqPqP|</b>\nqPqPqP|")
        tw, th = layout.get_pixel_size()
        self.render.height = max(TimelineRenderer.height, th + 3 + TimelineRenderer.barsize)
        self.render.set_fixed_size(self.render.width, self.render.height)



