# -.- coding: utf-8 -.-
#
# Filename
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
import os
import pango
import pangocairo
import time
import math
import operator
import threading

from zeitgeist.datamodel import Interpretation

from eventgatherer import event_exists
from widgets import StaticPreviewTooltip, VideoPreviewTooltip, ContextMenu
from gio_file import GioFile, SIZE_LARGE, SIZE_NORMAL
from common import *


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
            render_pixbuf(window, x, y, self.pixbuf)
        else: self.file_render_pixbuf(window, widget, x, y, w, h)
        render_emblems(window, x, y, w, h, self.emblems)
        if self.active:
            gobject.timeout_add(2, self.render_info_box, window, widget, cell_area, expose_area, self.event)
        return True

    def file_render_pixbuf(self, window, widget, x, y, w, h):
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
        text = get_event_text(self.event).replace("&", "&amp;")
        layout = widget.create_pango_layout(text)
        draw_text(context, layout, text, x+5, y+5, self.width-10)

    @staticmethod
    def render_info_box(window, widget, cell_area, expose_area, event):
        """
        Renders a info box when the item is active
        """
        x = cell_area.x
        y = cell_area.y - 10
        w = cell_area.width
        h = cell_area.height
        context = window.cairo_create()
        t0 = get_event_typename(event)
        t1 = get_event_text(event)
        text = ("<span size='10240'>%s</span>\n<span size='8192'>%s</span>" % (t0, t1)).replace("&", "&amp;")
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

# Registed the type to avoid errors using it as a renderer
gobject.type_register(PreviewRenderer)



# Display widgets
class ImageView(gtk.IconView):
    """
    A iconview which uses a custom cellrenderer to render square pixbufs
    based on zeitgeist events
    """
    last_active = -1
    child_width = PreviewRenderer.width
    child_height = PreviewRenderer.height
    def __init__(self):
        super(ImageView, self).__init__()
        self.popupmenu = ContextMenu
        self.add_events(gtk.gdk.LEAVE_NOTIFY_MASK)
        self.connect("button-press-event", self.on_button_press)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("leave-notify-event", self.on_leave_notify)
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
        """
        A threaded which generates pixbufs and emblems for a list of events.
        It takes those properties and appends them to the view's model
        """
        lock = threading.Lock()
        liststore = gtk.ListStore(gtk.gdk.Pixbuf, gobject.TYPE_PYOBJECT, gobject.TYPE_BOOLEAN, gobject.TYPE_PYOBJECT, gobject.TYPE_BOOLEAN)
        gtk.gdk.threads_enter()
        self.set_model(liststore)
        gtk.gdk.threads_leave()
        for event in events:
            uri = get_event_uri(event)
            if not event_exists(uri): continue
            pb, isthumb = PIXBUFCACHE.get_pixbuf_from_uri(uri, SIZE_LARGE, iconscale=0.1875, w=self.child_width, h=self.child_height)
            emblems = tuple()
            if isthumb and get_event_interpretation(event) != Interpretation.IMAGE.uri:
                emblem = get_event_icon(event, 16)
                if emblem:
                    emblems = (emblem,)
            gtk.gdk.threads_enter()
            lock.acquire()
            liststore.append((pb, emblems, False, event, isthumb))
            lock.release()
            gtk.gdk.threads_leave()


    def set_model_from_list(self, events):
        """
        Sets creates/sets a model from a list of zeitgeist events
        :param events: a list of :class:`Events <zeitgeist.datamodel.Event>`
        """
        self.last_active = -1
        if not events:
            self.set_model(None)
            return
        thread = threading.Thread(target=self._set_model_in_thread, args=(events,))
        thread.start()

    def on_button_press(self, widget, event):
        if event.button == 3:
            val = self.get_item_at_pos(int(event.x), int(event.y))
            if val:
                path, cell = val
                model = self.get_model()
                uri = get_event_uri(model[path[0]][3])
                self.popupmenu.do_popup(event.time, [uri])
        return False

    def on_leave_notify(self, widget, event):
        model = self.get_model()
        if model:
            try:
                model[self.last_active][2] = False
            except IndexError:pass
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
            uri = get_event_uri(model[path[0]][3])
            interpretation = get_event_interpretation(model[path[0]][3])
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

        :param i: a index for the three items in self.views. 0:Morning,1:AfterNoon,2:Evening
        :param events: a list of :class:`Events <zeitgeist.datamodel.Event>`
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

