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
import time
import math
import operator
import threading

from widgets import StaticPreviewTooltip, VideoPreviewTooltip
from gio_file import GioFile

import thumbrenderers.common as common
from thumbrenderers.renderers import PreviewRenderer


TIMELABELS = [_("Morning"), _("Afternoon"), _("Evening")]


class ImageView(gtk.IconView):
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
            pb, isthumb = common.get_pixbuf(event, self.child_width, self.child_height)
            emblems = tuple()
            if isthumb and common.get_interpretation(event) != common.Interpretation.IMAGE.uri:
                emblem = common.get_event_icon(event, 16)
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
            uri = common.get_uri(model[path[0]][3])
            interpretation = common.get_interpretation(model[path[0]][3])
            tooltip_window = widget.get_tooltip_window()
            if interpretation == common.Interpretation.VIDEO.uri:
                self.set_tooltip_window(VideoPreviewTooltip)
            else:
                self.set_tooltip_window(StaticPreviewTooltip)
            gio_file = GioFile.create(uri)
            return tooltip_window.preview(gio_file)
        return False


class ThumbBox(gtk.VBox):
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
        color.red = min(65535, color.red * 0.95)
        color.green = min(65535, color.green * 0.95)
        color.blue = min(65535, color.blue * 0.95)
        for label in self.labels:
            label.modify_fg(0, color)



