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
import os
import pango
import pangocairo
import time
import math
import operator
import threading

from zeitgeist.datamodel import Interpretation

from widgets import StaticPreviewTooltip, VideoPreviewTooltip, shade_gdk_color
from gio_file import GioFile, SIZE_LARGE, SIZE_NORMAL


TIMELABELS = [_("Morning"), _("Afternoon"), _("Evening")]
ICON_THEME = gtk.icon_theme_get_default()

FILETYPESNAMES = {
    Interpretation.VIDEO.uri : _("Video"),
    Interpretation.MUSIC.uri : _("Music"),
    Interpretation.DOCUMENT.uri : _("Document"),
    Interpretation.IMAGE.uri : _("Image"),
    Interpretation.SOURCECODE.uri : _("Source Code"),
    Interpretation.UNKNOWN.uri : _("Unknown"),
    }


class PixbufCache(dict):
    def __init__(self, *args, **kwargs):
        """"""
        super(PixbufCache, self).__init__()

    def check_cache(self, uri):
        return self[uri]

    def get_buff(self, key):
        thumbpath = os.path.expanduser("~/.cache/GAJ/1_" + str(hash(key)))
        iconpath = os.path.expanduser("~/.cache/GAJ/0_" + str(hash(key)))
        if os.path.exists(thumbpath):
            self[key] = (gtk.gdk.pixbuf_new_from_file(thumbpath), True)
            return self[key]
        elif os.path.exists(iconpath):
            self[key] = (gtk.gdk.pixbuf_new_from_file(iconpath), False)
            return self[key]
        return None

    def __getitem__(self, key):
        if self.has_key(key):
            return super(PixbufCache, self).__getitem__(key)
        return self.get_buff(key)

    def __setitem__(self, key, (pb, isthumb)):
        dir_ = os.path.expanduser("~/.cache/GAJ/")
        if not os.path.exists(os.path.expanduser("~/.cache/GAJ/")):
            os.makedirs(dir_)
        path = dir_ + str(hash(isthumb)) + "_" + str(hash(key))
        if not os.path.exists(path):
            open(path, 'w').close()
            pb.save(path, "png", {"quality":"100"})
        return super(PixbufCache, self).__setitem__(key, (pb, isthumb))

PIXBUFCACHE = PixbufCache()


def launch_event(event):
    gfile = GioFile(get_uri(event))
    gfile.launch()

def get_interpretation(event):
    return event.subjects[0].interpretation

def get_typename(event):
    return FILETYPESNAMES[event.subjects[0].interpretation]

def get_mimetype(event):
    return event.subjects[0].mimetype

def get_text(event):
    return event.subjects[0].text

def get_uri(event):
    return event.subjects[0].uri#[7:].replace("%20", " ")

def get_timestamp(event):
    if hasattr(self, "_event"):
        return float(event.timestamp)

def get_timetext(event):
    t = time.localtime(get_timestamp(event)/1000)
    return time.strftime("%H:%M, %d %B", t)

def get_pixbuf_from_uri(uri, size=SIZE_LARGE, iconscale=1, w=0, h=0):
    """
    Return a pixbuf and True if a thumbnail was found, else False

    Arguments:
    -- size: a size tuple from thumbfactory
    -- iconscale: a factor to reduce other icons by
    """
    try:
        cached = PIXBUFCACHE.check_cache(uri)
    except gobject.GError:
        cached = None
    if cached:
        return cached
    gfile = GioFile(uri)
    thumb = True
    if gfile:
        if gfile.has_preview():
            pb = gfile.get_thumbnail(size=size)
        else:
            iconsize = int(size[0]*iconscale)
            pb = gfile.get_icon(size=iconsize)
            thumb = False
    else: pb = None
    if not pb:
        pb = ICON_THEME.lookup_icon(gtk.STOCK_MISSING_IMAGE, int(size[0]*iconscale), gtk.ICON_LOOKUP_FORCE_SVG).load_icon()
        thumb = False
    if thumb:
        pb = scale_to_fill(pb, w, h)
        PIXBUFCACHE[uri] = (pb, thumb)
    return pb, thumb

def get_event_icon(event, size):
    """
    Returns a icon from a event at size
    """
    gfile = GioFile(get_uri(event))
    if gfile:
        pb = gfile.get_icon(size=size)
        if pb:
            return pb
    return False

def get_event_markup(event):
    """
    Returns a typename and event formatted to be displayed in a info bubble
    """
    t0 = get_typename(event)
    t1 = get_text(event)
    return ("<span size='10240'>%s</span>\n<span size='8192'>%s</span>" % (t0, t1)).replace("&", "&amp;")

def get_pixbuf(event, w, h):
    """
    Returns a pixbuf and a bool depending on what type of representation it is to display
    """
    uri = get_uri(event)
    pb, isthumb = get_pixbuf_from_uri(uri, SIZE_LARGE, iconscale=0.1875, w=w, h=h)
    return pb, isthumb

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
    context.set_source_rgba(0.5, 0.5, 0.5)#0.3, 0.3, 0.3)
    context.stroke()
    context.set_source_rgba(0.7, 0.7, 0.7)
    context.rectangle(x, y, w, h)
    context.stroke()
    context.set_source_rgba(0.4, 0.4, 0.4)
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
        draw_frame(context, x, y, imgw, imgh)

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
        text = get_event_markup(event)
        layout = widget.create_pango_layout(text)
        layout.set_markup(text)
        textw, texth = layout.get_pixel_size()
        popuph = max(h/3 + 5, texth)
        nw = w + 26
        x = x - (nw - w)/2
        width, height = window.get_geometry()[2:4]
        popupy = min(y+h+10, height-popuph-5-1) - 5
        draw_speech_bubble(context, layout, x, popupy, nw, popuph)
        context.fill()
        return False

    def on_start_editing(self, event, widget, path, background_area, cell_area, flags):
        pass

    def on_activate(self, event, widget, path, background_area, cell_area, flags):
        launch_event(self.event)
        return True

gobject.type_register(PreviewRenderer)


# Special rendering functions
def file_render_pixbuf(self, window, widget, x, y, h, w):
    """
    Renders a icon and file name for non-thumb objects
    """
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
    draw_frame(context, x, y, w, h)
    context = window.cairo_create()
    text = get_text(self.event)
    layout = widget.create_pango_layout(text)
    draw_text(context, layout, text, x+5, y+5, self.width-10)


# Display widgets
class ImageView(gtk.IconView):
    """
    A iconview which shows just formatted pixbufs
    """
    last_active = -1
    child_width = PreviewRenderer.width
    child_height = PreviewRenderer.height
    def __init__(self):
        super(ImageView, self).__init__()
        self.add_events(gtk.gdk.LEAVE_NOTIFY_MASK)
        self.connect("button-press-event", self.on_button_press)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("leave-notify-event", self.on_leave_notify)
        # self.connect("query-tooltip", self.query_tooltip)
        # self.set_property("has-tooltip", True)
        # self.set_tooltip_window(StaticPreviewTooltip)
        self.set_selection_mode(gtk.SELECTION_NONE)
        self.set_column_spacing(0)
        self.set_row_spacing(0)
        pcolumn = gtk.TreeViewColumn("Preview")
        render = PreviewRenderer()
        self.pack_end(render)
        self.add_attribute(render, "pixbuf", 0)
        self.add_attribute(render, "emblems", 1)
        self.add_attribute(render, "active", 2)
        self.add_attribute(render, "event", 3)
        self.add_attribute(render, "isthumb", 4)
        self.set_margin(10)

    def _set_model_in_thread(self, events):
        liststore = gtk.ListStore(gtk.gdk.Pixbuf, gobject.TYPE_PYOBJECT, gobject.TYPE_BOOLEAN, gobject.TYPE_PYOBJECT, gobject.TYPE_BOOLEAN)
        for event in events:
            pb, isthumb = get_pixbuf(event, self.child_width, self.child_height)
            emblems = tuple()
            if isthumb and get_interpretation(event) != Interpretation.IMAGE.uri:
                emblem = get_event_icon(event, 16)
                if emblem:
                    emblems = (emblem,)
            liststore.append((pb, emblems, False, event, isthumb))
        gtk.gdk.threads_enter()
        self.set_model(liststore)
        gtk.gdk.threads_leave()

    def set_model_from_list(self, events):
        """
        Sets creates/sets a model from a list of zeitgeist events
        Arguments:
        -- events: a list of events
        """
        self.last_active = -1
        if not events:
            self.set_model(None)
            return
        thread = threading.Thread(target=self._set_model_in_thread, args=(events,))
        thread.start()

    def on_button_press(self, widget, event):
        return False

    def on_leave_notify(self, widget, event):
        model = self.get_model()
        if model:
            model[self.last_active][2] = False
            self.last_active = -1

    def on_motion_notify(self, widget, event):
        val = self.get_item_at_pos(int(event.x), int(event.y))
        if val:
            path, cell = val
            if path[0] != self.last_active:
                model = self.get_model()
                model[self.last_active][2] = False
                model[path[0]][2] = True
                self.last_active = path[0]
        return True

    def query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """
        Displays a tooltip based on x, y
        """
        path = self.get_path_at_pos(int(x), int(y))
        if path:
            model = self.get_model()
            uri = get_uri(model[path[0]][3])
            interpretation = get_interpretation(model[path[0]][3])
            tooltip_window = widget.get_tooltip_window()
            if interpretation == Interpretation.VIDEO.uri:
                self.set_tooltip_window(VideoPreviewTooltip)
            else:
                self.set_tooltip_window(StaticPreviewTooltip)
            gio_file = GioFile.create(uri)
            return tooltip_window.preview(gio_file)
        return False


class ThumbBox(gtk.VBox):
    """
    A container for three image views representing periods in time
    """
    def __init__(self):
        """Woo"""
        gtk.VBox.__init__(self)
        self.views = [ImageView() for x in xrange(3)]
        self.labels = [gtk.Label() for x in xrange(3)]
        for i in xrange(3):
            text = TIMELABELS[i]
            line = 50 - len(text)
            self.labels[i].set_markup(
                "\n  <span size='10336'>%s <s>%s</s></span>" % (text, " "*line))
            self.labels[i].set_justify(gtk.JUSTIFY_RIGHT)
            self.labels[i].set_alignment(0, 0)
            self.pack_start(self.labels[i], False, False)
            self.pack_start(self.views[i], False, False)
        self.connect("style-set", self.change_style)

    def set_phase_events(self, i, events):
        """
        Set a time phases events

        Arguments:
        -- i: a index for the three items in self.views. 0:Morning,1:AfterNoon,2:Evening
        -- events: a list of zeitgeist events
        """
        view = self.views[i]
        label = self.labels[i]
        if not events or len(events) == 0:
            view.set_model_from_list(None)
            return False
        view.show_all()
        label.show_all()
        view.set_model_from_list(events)

        if len(events) == 0:
            view.hide_all()
            label.hide_all()

    def set_morning_events(self, events): self.set_phase_events(0, events)
    def set_afternoon_events(self, events): self.set_phase_events(1, events)
    def set_evening_events(self, events): self.set_phase_events(2, events)

    def change_style(self, widget, style):
        rc_style = self.style
        parent = self.get_parent()
        if parent:
            parent = self.get_parent()
        color = rc_style.bg[gtk.STATE_NORMAL]
        parent.modify_bg(gtk.STATE_NORMAL, color)
        for view in self.views: view.modify_base(gtk.STATE_NORMAL, color)
        color = rc_style.text[4]
        color = shade_gdk_color(color, 0.95)
        for label in self.labels:
            label.modify_fg(0, color)

