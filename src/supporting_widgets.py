# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Siegfried Gevatter <siegfried@gevatter.com>
# Copyright © 2010 Markus Korn <thekorn@gmx.de>
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
# Copyright © 2010 Stefano Candori <stefano.candori@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement
import cairo
import os
import gobject
import gtk
import gettext
import datetime
import math
import time
import pango
import gio
import threading
from dbus.exceptions import DBusException
try:
    import gst
except ImportError:
    gst = None

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType

from common import *
import content_objects
from config import BASE_PATH, VERSION, settings, PluginManager, get_icon_path, get_data_path, bookmarker, SUPPORTED_SOURCES
from store import STORE, get_related_events_for_uri, CLIENT


class DayLabel(gtk.DrawingArea):

    _events = (
        gtk.gdk.ENTER_NOTIFY_MASK | gtk.gdk.LEAVE_NOTIFY_MASK |
        gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON_MOTION_MASK |
        gtk.gdk.POINTER_MOTION_HINT_MASK | gtk.gdk.BUTTON_RELEASE_MASK |
        gtk.gdk.BUTTON_PRESS_MASK
    )

    def __init__(self,date=None):
        super(DayLabel, self).__init__()
        self.set_events(self._events)
        self.connect("expose_event", self.expose)
        if date:
            self.date = date
        else:
            self.date = datetime.date.today()
        self.set_size_request(100, 60)

    @property
    def date_string(self):
        return self.date.strftime("%x")

    @property
    def weekday_string(self):
        if self.date == datetime.date.today():
            return "Today"
        timedelta = datetime.date.today() -self.date
        if timedelta.days == 1:
            return "Yesterday"
        return self.date.strftime("%A")

    @property
    def leading(self):
        if self.date == datetime.date.today():
            return True

    def set_date(self, date):
        self.date = date
        self.queue_draw()

    def expose(self, widget, event):
        context = widget.window.cairo_create()
        self.context = context

        self.font_name = self.style.font_desc.get_family()
        widget.style.set_background(widget.window, gtk.STATE_NORMAL)

        # set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()
        self.draw(widget, event, context)
        self.day_text(widget, event, context)
        return False

    def day_text(self, widget, event, context):
        actual_y = self.get_size_request()[1]
        if actual_y > event.area.height:
            y = actual_y
        else:
            y = event.area.height
        x = event.area.width
        gc = self.style.fg_gc[gtk.STATE_SELECTED if self.leading else gtk.STATE_NORMAL]
        layout = widget.create_pango_layout(self.weekday_string)
        layout.set_font_description(pango.FontDescription(self.font_name + " Bold 15"))
        w, h = layout.get_pixel_size()
        widget.window.draw_layout(gc, (x-w)/2, (y)/2 - h + 5, layout)
        self.date_text(widget, event, context, (y)/2 + 5)

    def date_text(self, widget, event, context, lastfontheight):
        gc = self.style.fg_gc[gtk.STATE_SELECTED if self.leading else gtk.STATE_INSENSITIVE]
        layout = widget.create_pango_layout(self.date_string)
        layout.set_font_description(pango.FontDescription(self.font_name + " 10"))
        w, h = layout.get_pixel_size()
        widget.window.draw_layout(gc, (event.area.width-w)/2, lastfontheight, layout)

    def draw(self, widget, event, context):
        if self.leading:
            bg = self.style.bg[gtk.STATE_SELECTED]
            red, green, blue = bg.red/65535.0, bg.green/65535.0, bg.blue/65535.0
        else:
            bg = self.style.bg[gtk.STATE_NORMAL]
            red = (bg.red * 125 / 100)/65535.0
            green = (bg.green * 125 / 100)/65535.0
            blue = (bg.blue * 125 / 100)/65535.0
        x = 0; y = 0
        r = 5
        w, h = event.area.width, event.area.height
        context.set_source_rgba(red, green, blue, 1)
        context.new_sub_path()
        context.arc(r+x, r+y, r, math.pi, 3 * math.pi /2)
        context.arc(w-r, r+y, r, 3 * math.pi / 2, 0)
        context.close_path()
        context.rectangle(0, r, w, h)
        context.fill_preserve()


class DayButton(gtk.DrawingArea):
    leading = False
    pressed = False
    today_pressed = False
    sensitive = True
    today_hover = False
    hover = False
    header_size = 60
    bg_color = (0, 0, 0, 0)
    header_color = (1, 1, 1, 1)
    leading_header_color = (1, 1, 1, 1)
    internal_color = (0, 1, 0, 1)
    arrow_color = (1, 1, 1, 1)
    arrow_color_selected = (1, 1, 1, 1)

    __gsignals__ = {
        "clicked":  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,()),
        "jump-to-today": (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,()),
        }
    _events = (
        gtk.gdk.ENTER_NOTIFY_MASK | gtk.gdk.LEAVE_NOTIFY_MASK |
        gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.BUTTON_PRESS_MASK |
        gtk.gdk.MOTION_NOTIFY |   gtk.gdk.POINTER_MOTION_MASK
    )

    @classmethod
    def new(cls, side = 0, sensitive=True):
        button = DayButton(side, sensitive)
        def query_tooltip(widget, x, y, keyboard_mode, tooltip, ebutton):
            if not ebutton.sensitive:
                return False
            elif y < ebutton.header_size and ebutton.side == 1:
                text = _("Go to Today")
            elif y >= ebutton.header_size:
                text = _("Go to the previous day ") if ebutton.side == 0 else _("Go to the next day")
            else:
                return False
            tooltip.set_text(text)
            return True
        evbox = gtk.EventBox()
        evbox.connect("query-tooltip", query_tooltip, button)
        evbox.set_property("has-tooltip", True)
        evbox.add(button)

        return button, evbox

    def __init__(self, side = 0, sensitive=True):
        super(DayButton, self).__init__()
        self.set_events(self._events)
        self.set_flags(gtk.CAN_FOCUS)
        self.side = side
        self.connect("button_press_event", self.on_press)
        self.connect("button_release_event", self.clicked_sender)
        self.connect("key_press_event", self.keyboard_clicked_sender)
        self.connect("motion_notify_event", self.on_hover)
        self.connect("leave_notify_event", self._enter_leave_notify, False)
        self.connect("expose_event", self.expose)
        self.connect("style-set", self.change_style)
        self.set_size_request(20, -1)
        self.set_sensitive(sensitive)

    def set_leading(self, leading):
        self.leading = leading

    def set_sensitive(self, case):
        self.sensitive = case
        self.queue_draw()

    def _enter_leave_notify(self, widget, event, bol):
        self.hover = bol
        self.today_hover = bol
        self.queue_draw()

    def on_hover(self, widget, event):
        if event.y > self.header_size:
            if not self.hover:
                self.hover = True
            else:
                self.today_hover = False
        else:
            if self.hover:
                self.hover = False
            else:
                self.today_hover = True
        self.queue_draw()
        return False

    def on_press(self, widget, event):
        if event.y > self.header_size:
            self.pressed = True
        else:
            self.today_pressed = True
        self.queue_draw()

    def keyboard_clicked_sender(self, widget, event):
        if event.keyval in (gtk.keysyms.Return, gtk.keysyms.space):
            if self.sensitive:
                self.emit("clicked")
            self.pressed = False
            self.queue_draw()
            return True
        return False

    def clicked_sender(self, widget, event):
        if event.y > self.header_size:
            if self.sensitive:
                self.emit("clicked")
        elif event.y < self.header_size:
            self.emit("jump-to-today")
        self.pressed = False
        self.today_pressed = False;
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
        size = 20
        if self.sensitive:
            context.set_source_rgba(*(self.leading_header_color if self.leading else self.header_color))
            context.new_sub_path()
            context.move_to(x+r,y)
            context.line_to(x+w-r,y)
            context.curve_to(x+w,y,x+w,y,x+w,y+r)
            context.line_to(x+w,y+h-r)
            context.curve_to(x+w,y+h,x+w,y+h,x+w-r,y+h)
            context.line_to(x+r,y+h)
            context.curve_to(x,y+h,x,y+h,x,y+h-r)
            context.line_to(x,y+r)
            context.curve_to(x,y,x,y,x+r,y)
            # What's this for, exactly? Appears to have been already set.
            #context.set_source_rgba(*(self.leading_header_color if self.leading else self.header_color))
            context.close_path()
            context.rectangle(0, r, w,  self.header_size)
            context.fill()
            context.set_source_rgba(*self.internal_color)
            context.rectangle(0, self.header_size, w,  h)
            context.fill()
            if self.hover:
                widget.style.paint_box(widget.window, gtk.STATE_PRELIGHT, gtk.SHADOW_OUT,
                                         event.area, widget, "button",
                                         event.area.x, self.header_size,
                                         w, h-self.header_size)
            if self.side > 0 and self.today_hover:
                widget.style.paint_box(widget.window, gtk.STATE_PRELIGHT, gtk.SHADOW_OUT,
                                         event.area, widget, "button",
                                         event.area.x, 0,
                                         w, self.header_size)
        size = 10
        if not self.sensitive:
            state = gtk.STATE_INSENSITIVE
        elif self.is_focus() or self.pressed:
            widget.style.paint_focus(widget.window, gtk.STATE_ACTIVE, event.area,
                                     widget, None, event.area.x, self.header_size,
                                     w, h-self.header_size)
            state = gtk.STATE_SELECTED
        else:
            state = gtk.STATE_NORMAL
        arrow = gtk.ARROW_RIGHT if self.side else gtk.ARROW_LEFT
        self.style.paint_arrow(widget.window, state, gtk.SHADOW_NONE, None,
                               self, "arrow", arrow, True,
                               w/2-size/2, h/2 + size/2, size, size)
        size = 7
        
        # Paint today button arrows.
        if self.sensitive and self.side > 0:
            if self.today_hover:
                if self.today_pressed:
                    self.style.paint_arrow(widget.window, gtk.STATE_SELECTED, gtk.SHADOW_NONE, None,
                                         self, "arrow", arrow, True,
                                         w/2, self.header_size/2 - size/2, size, size)
                    self.style.paint_arrow(widget.window, gtk.STATE_SELECTED, gtk.SHADOW_OUT, None,
                                         self, "arrow", arrow, True,
                                         w/2-size/2, self.header_size/2 - size/2, size, size)
                
                else:
                    self.style.paint_arrow(widget.window, state, gtk.SHADOW_NONE, None,
                                         self, "arrow", arrow, True,
                                         w/2, self.header_size/2 - size/2, size, size)
                    self.style.paint_arrow(widget.window, state, gtk.SHADOW_OUT, None,
                                         self, "arrow", arrow, True,
                                         w/2-size/2, self.header_size/2 - size/2, size, size)
            else:
                self.style.paint_arrow(widget.window, gtk.STATE_SELECTED, gtk.SHADOW_NONE, None,
                                        self, "arrow", arrow, True,
                                        w/2, self.header_size/2 - size/2, size, size)
                self.style.paint_arrow(widget.window, gtk.STATE_SELECTED, gtk.SHADOW_OUT, None,
                                        self, "arrow", arrow, True,
                                        w/2-size/2, self.header_size/2 - size/2, size, size)
        #return


class SearchBox(gtk.ToolItem):

    __gsignals__ = {
        "clear" : (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   ()),
        "search" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_PYOBJECT,))
    }

    def __init__(self):
        gtk.ToolItem.__init__(self)

        self.text = ""
        self.callback = None
        self.set_border_width(3)
        self.hbox = gtk.HBox()
        self.add(self.hbox)
        self.results = []
        self.search = SearchEntry()
        self.hbox.pack_start(self.search)
        self.category = {}

        for source in SUPPORTED_SOURCES.keys():
            s = SUPPORTED_SOURCES[source]._desc_pl
            self.category[s] = source

        self._init_combobox()
        self.show_all()

        def change_style(widget, style):

            rc_style = self.style
            color = rc_style.bg[gtk.STATE_NORMAL]
            color = shade_gdk_color(color, 102/100.0)
            self.modify_bg(gtk.STATE_NORMAL, color)

            color = rc_style.bg[gtk.STATE_NORMAL]
            fcolor = rc_style.fg[gtk.STATE_NORMAL]
            color = combine_gdk_color(color, fcolor)

            self.search.modify_text(gtk.STATE_NORMAL, color)

        self.hbox.connect("style-set", change_style)
        self.search.connect("search", self.set_search)
        self.search.connect("clear", self.clear)
        self.connect("search", self.__search)

    def clear(self, widget):
        if self.text.strip() != "" and self.text.strip() != self.search.default_text: 
            self.text = ""
            self.search.set_text("")
            self.results = [] 
            self.emit("clear")  

    def _init_combobox(self):
        self.combobox = gtk.combo_box_new_text()
        self.combobox.set_focus_on_click(False)
        self.hbox.pack_end(self.combobox, False, False, 6)
        self.combobox.append_text("All activities")
        self.combobox.set_active(0)
        for cat in self.category.keys():
            self.combobox.append_text(cat)

    def set_search(self, widget, text=None):
        if not self.text.strip() == text.strip():
            self.text = text
            def callback(results):
                self.results = results
                self.emit("search", results)
            if not text:
                text = self.search.get_text()
            if text == self.search.default_text or text.strip() == "":
                pass
            else:
                cat = self.combobox.get_active()
                if cat == 0:
                    interpretation = None
                else:
                    cat = self.category[self.combobox.get_active_text()]
                    interpretation = self.category[self.combobox.get_active_text()]
            if interpretation:
                return self.do_search(text, callback, interpretation)
            return self.do_search(text, callback)

    def do_search(self, text, callback=None, interpretation=None):
        if not callback: return
        self.do_search_objs(text, callback, interpretation)

    @staticmethod
    def do_search_objs(text, callback, interpretation=None):
        def _search(text, callback):
            matching = []
            for obj in content_objects.ContentObject.instances:
                subject = obj.event.subjects[0]
                if text.lower() in subject.text.lower() or text in subject.uri:
                    if interpretation:
                        try:
                            if subject.interpretation != interpretation:
                                continue
                        except: continue
                    matching.append(obj)
            gtk.gdk.threads_enter()
            callback(matching)
            gtk.gdk.threads_leave()
        thread = threading.Thread(target=_search, args=(text, callback))
        thread.start()

    def do_search_using_zeitgeist(self, text, callback=None, interpretation=""):
        if not text: return
        self.callback = callback
        templates = [
            Event.new_for_values(subject_text="*"+text+"*", subject_interpretation=interpretation),
            Event.new_for_values(subject_uri="*"+text+"*", subject_interpretation=interpretation)
        ]
        CLIENT.find_event_ids_for_templates(templates, self._search_callback, storage_state=2, num_events=20, result_type=0)

    def _search_callback(self, ids):
        objs = []
        for id_ in ids:
            try:
                obj.append(STORE[id_])
            except KeyError:
                continue
        if self.callback:
            self.callback(objs)

    def toggle_visibility(self):
        if self.get_property("visible"):
            self.clear(None)
            self.hide()
            return False
        self.show()
        return True

    def __search(self, this, results):
        content_objects.ContentObject.clear_search_matches()
        for obj in results:
            setattr(obj, "matches_search", True)


class SearchEntry(gtk.Entry):

    __gsignals__ = {
        "clear" : (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   ()),
        "search" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_STRING,)),
        "close" : (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   ()),
    }

    default_text = _("Type here to search...")
    # TODO: What is this?
    search_timeout = 0

    def __init__(self, accel_group = None):
        gtk.Entry.__init__(self)

        self.set_width_chars(30)
        self.set_text(self.default_text)
        self.connect("changed", lambda w: self._queue_search())
        self.connect("focus-in-event", self._entry_focus_in)
        self.connect("focus-out-event", self._entry_focus_out)
        self.set_icon_from_stock(0, gtk.STOCK_CANCEL)
        self.set_icon_from_stock(1, gtk.STOCK_CLEAR)
        self.connect("icon-press", self._icon_press)
        self.show_all()

    def _icon_press(self, widget, pos, event):
        if int(pos) == 1 and not self.get_text() == self.default_text:
            self._entry_clear_no_change_handler()
        elif event.button == 1 and pos == 0:
            self.emit("close")

    def _entry_focus_in(self, widget, x):
        if self.get_text() == self.default_text:
            self.set_text("")
            #self.modify_font(self.font_style)

    def _entry_focus_out(self, widget, x):
        if self.get_text() == "":
            self.set_text(self.default_text)
            #self.modify_font(self.font_style)

    def _entry_clear_no_change_handler(self):
        if not self.get_text() == self.default_text:
            self.set_text("")

    def _queue_search(self):
        if self.search_timeout != 0:
            gobject.source_remove(self.search_timeout)
            self.search_timeout = 0

        if self.get_text() == self.default_text or len(self.get_text()) == 0:
            self.emit("clear")
        else:
            self.search_timeout = gobject.timeout_add(200, self._typing_timeout)

    def _typing_timeout(self):
        if len(self.get_text()) > 0:
            self.emit("search", self.get_text())

        self.search_timeout = 0
        return False


class PreviewTooltip(gtk.Window):

    # per default we are using thumbs at a size of 128 * 128 px
    # in tooltips. For preview of text files we are using 256 * 256 px
    # which is dynamically defined in StaticPreviewTooltip.preview()
    TOOLTIP_SIZE = SIZE_NORMAL

    def __init__(self):
        gtk.Window.__init__(self, type=gtk.WINDOW_POPUP)

    def preview(self, gio_file):
        return False


class StaticPreviewTooltip(PreviewTooltip):

    def __init__(self):
        super(StaticPreviewTooltip, self).__init__()
        self.__current = None
        self.__monitor = None

    def replace_content(self, content):
        children = self.get_children()
        if children:
            self.remove(children[0])
            # hack to force the tooltip to have the exact same size
            # as the child image
            self.resize(1,1)
        self.add(content)

    def preview(self, gio_file):
        if gio_file == self.__current:
            return bool(self.__current)
        if self.__monitor is not None:
            self.__monitor.cancel()
        self.__current = gio_file
        self.__monitor = gio_file.get_monitor()
        self.__monitor.connect("changed", self._do_update_preview)
        # for text previews we are always using SIZE_LARGE
        if "text-x-generic" in gio_file.icon_names or "text-x-script" in gio_file.icon_names:
            size = SIZE_LARGE
        else:
            size = self.TOOLTIP_SIZE
        if not isinstance(gio_file, GioFile): return False
        pixbuf = gio_file.get_thumbnail(size=size, border=1)
        if pixbuf is None:
            self.__current = None
            return False
        img = gtk.image_new_from_pixbuf(pixbuf)
        img.set_alignment(0.5, 0.5)
        img.show_all()
        self.replace_content(img)
        del pixbuf, size
        return True

    def _do_update_preview(self, monitor, file, other_file, event_type):
        if event_type == gio.FILE_MONITOR_EVENT_CHANGES_DONE_HINT:
            if self.__current is not None:
                self.__current.refresh()
            self.__current = None
            gtk.tooltip_trigger_tooltip_query(gtk.gdk.display_get_default())


class VideoPreviewTooltip(PreviewTooltip):

    def __init__(self):
        PreviewTooltip.__init__(self)
        hbox = gtk.HBox()
        self.movie_window = gtk.DrawingArea()
        hbox.pack_start(self.movie_window)
        self.add(hbox)
        self.player = gst.element_factory_make("playbin", "player")
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)
        self.connect("hide", self._handle_hide)
        self.connect("show", self._handle_show)
        self.set_default_size(*SIZE_LARGE)

    def _handle_hide(self, widget):
        self.hide_all()
        self.player.set_state(gst.STATE_NULL)

    def _handle_show(self, widget):
        self.show_all()
        self.player.set_state(gst.STATE_PLAYING)

    def preview(self, gio_file):
        if gio_file.uri == self.player.get_property("uri"):
            return True
        self.player.set_property("uri", gio_file.uri)
        return True

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
            self.hide_all()
        elif t == gst.MESSAGE_ERROR:
            self.player.set_state(gst.STATE_NULL)
            err, debug = message.parse_error()
            print "Error: %s" % err, debug

    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            gtk.gdk.threads_enter()
            try:
                imagesink.set_xwindow_id(self.movie_window.window.xid)
            finally:
                gtk.gdk.threads_leave()

class AudioPreviewTooltip(PreviewTooltip):

    def __init__(self):
        PreviewTooltip.__init__(self)     
        #Playing label stuffs
        screen = self.get_screen()
        rgba = screen.get_rgba_colormap()
	self.set_colormap(rgba)
	self.set_app_paintable(True)
	img = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY,gtk.ICON_SIZE_LARGE_TOOLBAR)
	self.image = AnimatedImage(get_data_path("zlogo/zg%d.png"), 150, size=20)
        self.image.start()
        label = gtk.Label()
        label.set_markup(_("<b>Playing...</b>"))
        hbox = gtk.HBox()
        hal = gtk.Alignment()
        hal.set_padding(0,0,5,0)
        hal.add(label)
        hbox.pack_start(self.image)
        hbox.pack_end(hal)
        self.resize(1,1)
        self.add(hbox)
        #GStreamer stuffs
        self.player = gst.element_factory_make("playbin2", "player")
        fakesink = gst.element_factory_make("fakesink", "fakesink")
        self.player.set_property("video-sink", fakesink)
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)
        self.connect("hide", self._handle_hide)
        self.connect("show", self._handle_show)
        self.connect("expose-event", self.transparent_expose)
        
    def transparent_expose(self, widget, event):
	cr = widget.window.cairo_create()
	cr.set_operator(cairo.OPERATOR_CLEAR)
	region = gtk.gdk.region_rectangle(event.area)
	cr.region(region)
	cr.fill()
	return False

    def _handle_hide(self, widget):
        self.image.stop()
        self.player.set_state(gst.STATE_NULL)

    def _handle_show(self, widget):
        self.image.start()
        self.show_all()
        self.player.set_state(gst.STATE_PLAYING)

    def preview(self, gio_file):
        if gio_file.uri == self.player.get_property("uri"):
            return True
        self.player.set_property("uri", gio_file.uri)
        return True

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
        elif t == gst.MESSAGE_ERROR:
            self.player.set_state(gst.STATE_NULL)
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            
    def replace_content(self, content):
        children = self.get_children()
        if children:
            self.remove(children[0])
            # hack to force the tooltip to have the exact same size
            # as the child image
            self.resize(1,1)
        self.add(content)

class AnimatedImage(gtk.Image):
    animating = None
    mod = 7
    i = 0
    speed = 100
    def __init__(self, uri, speed = 0, size = 16):
        super(AnimatedImage, self).__init__()
        if speed: self.speed = speed
        self.frames = []
        for i in (6, 5, 4, 3, 2, 1, 0):
            self.frames.append(gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(uri % i), size, size))
        self.set_from_pixbuf(self.frames[0])

    def next(self):
        """
        Move to next frame
        """
        self.set_from_pixbuf(self.frames[self.i % self.mod])
        self.i += 1
        return True

    def start(self):
        """
        start the image's animation
        """
        if self.animating: gobject.source_remove(self.animating)
        self.animating = gobject.timeout_add(self.speed, self.next)

    def stop(self):
        """
        stop the image's animation
        """
        if self.animating: gobject.source_remove(self.animating)
        self.animating = None
        return False

    def animate_for_seconds(self, seconds):
        """
        :param seconds: int seconds for the amount of time when you want
        animate the throbber
        """
        self.start()
        gobject.timeout_add_seconds(seconds, self.stop)


class ThrobberPopupButton(gtk.ToolItem):

    def __init__(self):
        super(ThrobberPopupButton, self).__init__()
        box = gtk.HBox()
        self.button = button = gtk.ToggleButton()
        button.set_relief(gtk.RELIEF_NONE)
        self.image = image = AnimatedImage(get_data_path("zlogo/zg%d.png"), 150)
        image.set_tooltip_text(_("Preferences"))
        arrow = gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_NONE)
        arrow.set_size_request(10, 10)
        box.pack_start(image, True, True, 1)
        box.pack_start(arrow, True, True, 1)
        button.add(box)
        self.add(button)

        self.menu = gtk.Menu()
        self.about = get_menu_item_with_stock_id_and_text(gtk.STOCK_ABOUT, _("About"))
        self.preferences = get_menu_item_with_stock_id_and_text(gtk.STOCK_PREFERENCES, _("Preferences"))
        for item in (self.about, self.preferences): self.menu.insert(item, 0)
        self.about.connect("activate", self.show_about_window)
        self.menu.show_all()
        button.connect("toggled", self.on_toggle)
        self.preferences.connect("activate", lambda *args: self.preferences.toggle())
        self.menu.connect("hide", self.on_hide)

    def on_hide(self, *args):
        self.button.set_active(False)
        self.menu.popdown()
        return False

    def on_toggle(self, widget):
        alloc = self.get_allocation()
        x, y = self.window.get_position()
        func = lambda a:(x+alloc.x, y+alloc.y+alloc.height, True)
        #print func(1,2)
        self.menu.popup(None, None, func, 0, 0)

    def show_about_window(self, *etc):
        aboutwindow = AboutDialog()
        window = self.get_toplevel()
        aboutwindow.set_transient_for(window)
        aboutwindow.run()
        aboutwindow.destroy()
        self.preferences.toggle()


class AboutDialog(gtk.AboutDialog):
    name = "Activity Journal"
    authors = (
        "Seif Lotfy <seif@lotfy.com>",
        "Randal Barlow <email.tehk@gmail.com>",
        "Siegfried-Angel Gevatter <siegfried@gevatter.com>",
        "Peter Lund <peterfirefly@gmail.com>",
        "Hylke Bons <hylkebons@gmail.com>",
        "Markus Korn <thekorn@gmx.de>",
        "Mikkel Kamstrup <mikkel.kamstrup@gmail.com>",
        "Thorsten Prante <thorsten@prante.eu>",
        "Stefano Candori <stefano.candori@gmail.com>"
        )
    artists = (
               "Hylke Bons <hylkebons@gmail.com>",
               "Thorsten Prante <thorsten@prante.eu>"
                )
    copyright_ = "Copyright © 2009-2011 Activity Journal authors"
    comment = "A viewport into the past powered by Zeitgeist"
    version = VERSION
    def __init__(self):
        super(AboutDialog, self).__init__()
        self.set_name(self.name)
        self.set_version(self.version)
        self.set_comments(self.comment)
        self.set_copyright(self.copyright_)
        self.set_authors(self.authors)
        self.set_artists(self.artists)

        license = None
        for name in ("/usr/share/common-licenses/GPL",
            os.path.join(BASE_PATH, "COPYING")):
            if os.path.isfile(name):
                with open(name) as licensefile:
                    license = licensefile.read()
                    break
        if not license:
            license = "GNU General Public License, version 3 or later."

        self.set_license(license)
        #self.set_logo_icon_name("gnome-activity-journal")
        self.set_logo(gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(
            "hicolor/scalable/apps/gnome-activity-journal.svg"), 48, 48))


class ContextMenu(gtk.Menu):
    subjects = []# A list of Zeitgeist event uris
    informationwindow = None
    def __init__(self):
        super(ContextMenu, self).__init__()
        self.infowindow = None
        self.menuitems = {
            "open" : gtk.ImageMenuItem(gtk.STOCK_OPEN),
            "unpin" : gtk.MenuItem(_("Remove Pin")),
            "pin" : gtk.MenuItem(_("Add Pin")),
            "delete" : get_menu_item_with_stock_id_and_text(gtk.STOCK_DELETE, _("Delete item from Journal")),
            "delete_uri" : gtk.MenuItem(_("Delete all events with this URI")),
            "info" : get_menu_item_with_stock_id_and_text(gtk.STOCK_INFO, _("More Information")),
            }
        callbacks = {
            "open" : self.do_open,
            "unpin" : self.do_unbookmark,
            "pin" : self.do_bookmark,
            "delete" : self.do_delete,
            "delete_uri" : self.do_delete_events_with_shared_uri,
            "info" : self.do_show_info,
            }
        names = ["open", "unpin", "pin", "delete", "delete_uri", "info"]
        if is_command_available("nautilus-sendto"):
            self.menuitems["sendto"] = get_menu_item_with_stock_id_and_text(gtk.STOCK_CONNECT, _("Send To..."))
            callbacks["sendto"] = self.do_send_to
            names.append("sendto")
        for name in names:
            item = self.menuitems[name]
            self.append(item)
            item.connect("activate", callbacks[name])
        self.show_all()

    def do_popup(self, time, subjects):
        """
        Call this method to popup the context menu

        :param time: the event time from the button press event
        :param subjects: a list of uris
        """
        self.subjects = subjects
        if len(subjects) == 1:
            uri = subjects[0].uri
            if bookmarker.is_bookmarked(uri):
                self.menuitems["pin"].hide()
                self.menuitems["unpin"].show()
            else:
                self.menuitems["pin"].show()
                self.menuitems["unpin"].hide()

        self.popup(None, None, None, 3, time)

    def do_open(self, menuitem):
        for obj in self.subjects:
            obj.launch()

    def do_show_info(self, menuitem):
        if self.subjects:
            if self.infowindow:
                self.infowindow.destroy()
            self.infowindow = InformationContainer()
            self.infowindow.set_position(gtk.WIN_POS_CENTER)
            self.infowindow.set_content_object(self.subjects[0])
            self.infowindow.set_size_request(400,400)
            self.infowindow.show_all()

    def do_bookmark(self, menuitem):
        for obj in self.subjects:
            uri = obj.uri
            uri = unicode(uri)
            isbookmarked = bookmarker.is_bookmarked(uri)
            if not isbookmarked:
                bookmarker.bookmark(uri)

    def do_unbookmark(self, menuitem):
        for obj in self.subjects:
            uri = obj.uri
            uri = unicode(uri)
            isbookmarked = bookmarker.is_bookmarked(uri)
            if isbookmarked:               
                bookmarker.unbookmark(uri)

    def do_delete(self, menuitem):
        for obj in self.subjects:
            CLIENT.find_event_ids_for_template(
                Event.new_for_values(subject_uri=obj.uri),
                lambda ids: CLIENT.delete_events(map(int, ids)),
                timerange=DayParts.get_day_part_range_for_item(obj))

    def do_delete_events_with_shared_uri(self, menuitem):
        for uri in map(lambda obj: obj.uri, self.subjects):
            CLIENT.find_event_ids_for_template(
                Event.new_for_values(subject_uri=uri),
                lambda ids: CLIENT.delete_events(map(int, ids)))

    def do_send_to(self, menuitem):
        launch_command("nautilus-sendto", map(lambda obj: obj.uri, self.subjects))


class ToolButton(gtk.RadioToolButton):
    def __init__(self, *args, **kwargs):
        super(ToolButton, self).__init__(*args, **kwargs)

    def set_label(self, text):
        super(ToolButton, self).set_label(text)
        self.set_tooltip_text(text)

    def set_tooltip_text(self, text):
        gtk.Widget.set_tooltip_text(self, text)

class InformationToolButton(gtk.ToolButton):
    def __init__(self, *args, **kwargs):
        super(InformationToolButton, self).__init__(*args, **kwargs)

    def set_label(self, text):
        super(InformationToolButton, self).set_label(text)
        self.set_tooltip_text(text)

    def set_tooltip_text(self, text):
        gtk.Widget.set_tooltip_text(self, text)


class Toolbar(gtk.Toolbar):
    @staticmethod
    def get_toolbutton(path, label_string,radio=True):
        if radio:
            button = ToolButton()
        else:
            button = InformationToolButton()
        pixbuf = gtk.gdk.pixbuf_new_from_file(path)
        image = gtk.Image()
        image.set_from_pixbuf(pixbuf)
        button.set_icon_widget(image)
        button.set_label(label_string)
        return button

    def __init__(self):
        super(Toolbar, self).__init__()
        #self.set_style(gtk.TOOLBAR_BOTH)
        #
        #self.append_space()
        self.search_button = sb = gtk.ToolButton(gtk.STOCK_FIND)
        self.search_dialog = sdialog = SearchBox
        self.search_dialog.search.connect("close", self.toggle_searchbox_visibility)
        self.search_button.connect("clicked", self.toggle_searchbox_visibility)

        sep1 = gtk.SeparatorToolItem()
        sep2 = gtk.SeparatorToolItem()
        for item in (sdialog, sb, sep1):
            self.insert(item, 0)
        #
        separator = gtk.SeparatorToolItem()
        separator.set_expand(True)
        separator.set_draw(False)
        self.throbber_popup_button = ThrobberPopupButton()
        for item in (separator, self.throbber_popup_button):
            self.insert(item, -1)

    def do_throb(self):
        self.throbber_popup_button.image.animate_for_seconds(1)

    def toggle_searchbox_visibility(self, w):
        result = self.search_dialog.toggle_visibility()
        if result:
            self.search_button.hide()
        else:
            self.search_button.show()

    def add_new_view_button(self, button, i=0):
        self.insert(button, i)
        button.show()

class StockIconButton(gtk.Button):
    def __init__(self, stock_id, label=None, size=gtk.ICON_SIZE_BUTTON):
        super(StockIconButton, self).__init__()
        self.size = size
        self.set_alignment(0, 0)
        self.set_relief(gtk.RELIEF_NONE)
        self.image = gtk.image_new_from_stock(stock_id, size)
        if not label:
            self.add(self.image)
        else:
            box = gtk.HBox()
            self.label = gtk.Label(label)
            box.pack_start(self.image, False, False, 2)
            box.pack_start(self.label)
            self.add(box)

    def set_stock(self, stock_id):
        self.image.set_from_stock(stock_id, self.size)


#######################
# More Information Pane
##

class InformationBox(gtk.VBox):
    """
    Holds widgets which display information about a uri
    """
    obj = None

    class _ImageDisplay(gtk.Image):
        """
        A display based on GtkImage to display a uri's thumb or icon using GioFile
        """
        def set_content_object(self, obj):
            if obj:
                if isinstance(obj, GioFile) and obj.has_preview():
                    pixbuf = obj.get_thumbnail(size=SIZE_NORMAL, border=3)
                else:
                    pixbuf = obj.get_icon(size=64)
                self.set_from_pixbuf(pixbuf)

    def __init__(self):
        super(InformationBox, self).__init__()
        vbox = gtk.VBox()
        self.box = gtk.Frame()
        self.label = gtk.Label()
        self.pathlabel = gtk.Label()
        self.pathlabel.modify_font(pango.FontDescription("Monospace 7"))
        self.box_label = gtk.EventBox()
        self.box_label.add(self.pathlabel)
        self.box_label.connect("button-press-event", self.on_path_label_clicked)
        self.box_label.connect("enter-notify-event", self.on_path_label_enter)
        self.box_label.connect("leave-notify-event", self.on_path_label_leave)
        self.box_label.connect("realize", self.on_realize_event)
        labelvbox = gtk.VBox()
        labelvbox.pack_start(self.label)
        labelvbox.pack_end(self.box_label)
        self.pack_start(labelvbox, True, True, 5)
        self.box.set_shadow_type(gtk.SHADOW_NONE)
        vbox.pack_start(self.box, True, True)
        self.pathlabel.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self.label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self.add(vbox)
        self.display_widget = self._ImageDisplay()
        self.box.add(self.display_widget)
        self.show_all()  

    def set_displaytype(self, obj):
        """
        Determines the ContentDisplay to use for a given uri
        """
        self.display_widget.set_content_object(obj)
        self.show_all()

    def set_content_object(self, obj):
        self.obj = obj
        self.set_displaytype(obj)
        text = get_text_or_uri(obj)
        self.label.set_markup("<span size='10336'>" + text + "</span>")
        path = obj.uri.replace("&", "&amp;").replace("%20", " ")
        self.is_file = path.startswith("file://")
        if self.is_file:
            self.textpath = os.path.dirname(path)[7:]
        else:
            self.textpath = path

        self.pathlabel.set_markup("<span color='#979797'>" + self.textpath + "</span>")

    def on_realize_event(self, parms):
        if self.is_file:
            hand = gtk.gdk.Cursor(gtk.gdk.HAND2)
            self.box_label.window.set_cursor(hand)    
   
    def on_path_label_clicked(self, wid, e):
        if self.is_file:
            os.system('xdg-open "%s"' % self.textpath)

    def on_path_label_enter(self, wid, e):
        if self.is_file:
            self.pathlabel.set_markup("<span color='#970000'><b>" + self.textpath+ "</b></span>")

    def on_path_label_leave(self, wid, e):
        if self.is_file:
            self.pathlabel.set_markup("<span color='#999797'>" + self.textpath + "</span>")

class _RelatedPane(gtk.TreeView):
    """
    . . . . .
    .       .
    .       . <--- Related files
    .       .
    . . . . .

    Displays related events using a widget based on gtk.TreeView
    """
    def __init__(self):
        super(_RelatedPane, self).__init__()
        self.popupmenu = ContextMenu
        self.connect("button-press-event", self.on_button_press)
        self.connect("row-activated", self.row_activated)
        pcolumn = gtk.TreeViewColumn(_("Used With"))
        pixbuf_render = gtk.CellRendererPixbuf()
        pcolumn.pack_start(pixbuf_render, False)
        pcolumn.set_cell_data_func(pixbuf_render, self.celldatamethod, "pixbuf")
        text_render = gtk.CellRendererText()
        text_render.set_property("ellipsize", pango.ELLIPSIZE_MIDDLE)
        pcolumn.pack_end(text_render, True)
        pcolumn.set_cell_data_func(text_render, self.celldatamethod, "text")
        self.append_column(pcolumn)
        self.set_headers_visible(True)

    def celldatamethod(self, column, cell, model, iter_, user_data):
        if model:
            obj = model.get_value(iter_, 0)
            if user_data == "text":
                text = get_text_or_uri(obj)
                cell.set_property("text", text)
            elif user_data == "pixbuf":
                cell.set_property("pixbuf", obj.icon)

    def _set_model_in_thread(self, structs):
        """
        A threaded which generates pixbufs and emblems for a list of structs.
        It takes those properties and appends them to the view's model
        """
        lock = threading.Lock()
        self.active_list = []
        liststore = gtk.ListStore(gobject.TYPE_PYOBJECT)
        self.set_model(liststore)
        for struct in structs:
            if not struct.content_object: continue
            self.active_list.append(False)
            liststore.append((struct.content_object,))

    def set_model_from_list(self, structs):
        self.last_active = -1
        if not structs:
            self.set_model(None)
            return
        thread = threading.Thread(target=self._set_model_in_thread, args=(structs,))
        thread.start()

    def on_button_press(self, widget, event):
        if event.button == 3:
            path = self.get_path_at_pos(int(event.x), int(event.y))
            if path:
                model = self.get_model()
                obj = model[path[0]][0]
                self.popupmenu.do_popup(event.time, [obj])
        return False

    def row_activated(self, widget, path, col, *args):
        if path:
            model = self.get_model()
            if model:
                obj = model[path[0]][0]
                obj.launch()


class InformationContainer(gtk.Window):
    """
    . . . . .
    .  URI  .
    . Info  .
    .       .
    . Tags  .
    . . . . .
    . . . . .
    .       .
    .       . <--- Related files
    .       .
    . . . . .

    A pane which holds the information pane and related pane
    """
    __gsignals__ = {
        "content-object-set":  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,()),
        }

    class _InformationToolbar(gtk.Toolbar):
        def __init__(self):
            gtk.Toolbar.__init__(self)
            self.set_icon_size(gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.open_button = ob = InformationToolButton(gtk.STOCK_OPEN)
            ob.set_label(_("Launch this subject"))
            self.delete_button = del_ = InformationToolButton(gtk.STOCK_DELETE)
            del_.set_label(_("Delete this subject"))
            self.pin_button = pin = Toolbar.get_toolbutton(
                get_icon_path("hicolor/24x24/status/pin.png"),
                _("Add Pin"),radio=False)
            sep = gtk.SeparatorToolItem()
            for item in (del_, pin, sep, ob):
                if item:
                    self.insert(item, 0)

    def __init__(self):
        super(gtk.Window, self).__init__()
        self.connect("destroy", self.hide_on_delete)
        box1 = gtk.VBox()
        box2 = gtk.VBox()
        vbox = gtk.VBox()
        self.toolbar = self._InformationToolbar()
        self.infopane = InformationBox()
        self.relatedpane = _RelatedPane()
        scrolledwindow = gtk.ScrolledWindow()
        box2.set_border_width(5)
        box1.pack_start(self.toolbar, False, False)
        box2.pack_start(self.infopane, False, False, 4)
        scrolledwindow.set_shadow_type(gtk.SHADOW_IN)
        scrolledwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolledwindow.add(self.relatedpane)
        vbox.pack_end(scrolledwindow, True, True)
        scrolledwindow.set_size_request(50, 100)
        box2.pack_end(vbox, True, True, 10)
        box1.pack_start(box2, True, True)
        self.add(box1)
        def _launch(w):
            self.obj.launch()
        self.toolbar.open_button.connect("clicked", _launch)
        self.toolbar.delete_button.connect("clicked", self.do_delete_events_with_shared_uri)
        self.toolbar.pin_button.connect("clicked", self.do_toggle_bookmark)
        self.connect("size-allocate", self.size_allocate)
        # Remove the close button
        separator = gtk.SeparatorToolItem()
        separator.set_expand(True)
        separator.set_draw(False)
        self.toolbar.insert(separator, -1)

    def size_allocate(self, widget, allocation):
        if allocation.height < 400:
            self.infopane.display_widget.hide()
        else:
            self.infopane.display_widget.show()

    def do_toggle_bookmark(self, *args):
        uri = unicode(self.obj.uri)
        if bookmarker.is_bookmarked(uri):
            bookmarker.unbookmark(uri)
        else:
            bookmarker.bookmark(uri)

    def do_delete_events_with_shared_uri(self, *args):
        CLIENT.find_event_ids_for_template(
            Event.new_for_values(subject_uri=self.obj.uri),
            lambda ids: CLIENT.delete_events(map(int, ids)))
        self.hide()

    def set_content_object(self, obj):
        self.obj = obj
        def _callback(events):
            self.relatedpane.set_model_from_list(events)
        get_related_events_for_uri(obj.uri, _callback)
        self.infopane.set_content_object(obj)
        self.set_title(_("More Information"))
        self.show()
        self.emit("content-object-set")

    def hide_on_delete(self, widget, *args):
        super(InformationContainer, self).hide_on_delete(widget)
        return True


class PreferencesDialog(gtk.Dialog):

    class _PluginTreeView(gtk.TreeView):
        def __init__(self):
            gtk.TreeView.__init__(self)
            self.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_VERTICAL)
            self.set_headers_visible(False)
            acolumn = gtk.TreeViewColumn("")
            toggle_render = gtk.CellRendererToggle()
            acolumn.pack_start(toggle_render, False)
            acolumn.add_attribute(toggle_render, "active", 1)
            self.append_column(acolumn)

            bcolumn = gtk.TreeViewColumn("")
            text_render = gtk.CellRendererText()
            text_render.set_property("ellipsize", pango.ELLIPSIZE_MIDDLE)
            bcolumn.pack_start(text_render, True)
            bcolumn.add_attribute(text_render, "markup", 0)
            self.append_column(bcolumn)
            self.set_property("rules-hint", True)
            self.connect("row-activated" , self.on_activate)

        def set_state(self, entry, state):
            PluginManager.plugin_settings._gconf.set_bool(entry.key, state)

        def on_activate(self, widget, path, column):
            model = self.get_model()
            model[path][1] = not model[path][1]
            self.set_state(model[path][2], model[path][1])
            bname = os.path.basename(model[path][2].key)
            if model[path][1]:
                self.manager.activate(name=bname)
            else:
                self.manager.deactivate(name=bname)

        def set_items(self, manager):
            entries = manager.plugin_settings._gconf.all_entries(PluginManager.plugin_settings._root)
            store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_BOOLEAN, gobject.TYPE_PYOBJECT)
            for entry in entries:
                bname = os.path.basename(entry.key)
                if manager.plugins.has_key(bname):
                    # Load the plugin if the plugin is found
                    module = manager.plugins[bname]
                    name = "<b>" + module.__plugin_name__ + "</b>"
                    desc = "\n<small>" + module.__description__ + "</small>"
                    store.append( [name+desc, False if entry.value is None else entry.value.get_bool(), entry])
                else:
                    # Remove the key if no plugin is found
                    manager.plugin_settings._gconf.unset(entry.key)
            self.manager = manager
            self.set_model(store)

    def __init__(self):
        super(PreferencesDialog, self).__init__()
        self.set_has_separator(False)
        self.set_title(_("Preferences"))
        self.set_size_request(400, 500)
        area = self.get_content_area()
        self.notebook = notebook = gtk.Notebook()
        area.pack_start(notebook)
        notebook.set_border_width(10)
        #Plugin page
        plugbox = gtk.VBox()
        plugbox.set_border_width(10)
        self.plug_tree = self._PluginTreeView()
        label = gtk.Label( _("Active Plugins:"))
        label.set_alignment(0, 0.5)
        plugbox.pack_start(label, False, False, 4)
        scroll_win = gtk.ScrolledWindow()
        scroll_win.set_shadow_type(gtk.SHADOW_IN)
        scroll_win.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll_win.add(self.plug_tree)
        plugbox.add(scroll_win)
        notebook.append_page(plugbox, gtk.Label( _("Plugins")))
        #Configuration page
        vbox = gtk.VBox()
        vbox.set_border_width(5)
        hbox_tray = gtk.HBox()
        label = gtk.Label(_("Show icon in system tray"))
        self.check_button = gtk.CheckButton()
        self.check_button.set_active(settings.get("tray_icon", False))
        self.check_button.connect("toggled", self.on_check_toggled)
        hbox_tray.pack_start(self.check_button,False,False)
        hbox_tray.pack_start(label, False,False)
        vbox.pack_start(hbox_tray,False,False)
        notebook.append_page(vbox, gtk.Label( _("Configuration")))

        self.connect("delete-event", lambda *args: (True, self.hide())[0])
        close_button = gtk.Button(stock=gtk.STOCK_CLOSE)
        self.add_action_widget(close_button, gtk.RESPONSE_DELETE_EVENT)
        close_button.connect("clicked", lambda *args: (True, self.hide())[0])

    def on_check_toggled(self, button, *args):
        settings.set("tray_icon", button.get_active())


###
if gst is not None:
    VideoPreviewTooltip = VideoPreviewTooltip()
    AudioPreviewTooltip = AudioPreviewTooltip()
else:
    VideoPreviewTooltip = None
    AudioPreviewTooltip = None
StaticPreviewTooltip = StaticPreviewTooltip()
ContextMenu = ContextMenu()
SearchBox = SearchBox()
