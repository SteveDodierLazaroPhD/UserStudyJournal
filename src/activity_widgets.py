# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
# Copyright © 2010 Siegfried Gevatter <siegfried@gevatter.com>
# Copyright © 2010 Markus Korn <thekorn@gmx.de>
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

import datetime
import gobject
import gst
import gtk
import math
import urllib
import pango
import threading

from common import *
import content_objects
from config import event_exists, settings, bookmarker, SUPPORTED_SOURCES
from store import ContentStruct, CLIENT
from supporting_widgets import DayLabel, ContextMenu, StaticPreviewTooltip, VideoPreviewTooltip, SearchBox,\
AudioPreviewTooltip
from zeitgeist.datamodel import ResultType, StorageState, TimeRange

#DND support variables
TYPE_TARGET_TEXT = 80
TYPE_TARGET_URI = 81
 
class Draggable():

    def __init__(self, widget):
        targets = [("text/plain", 0, TYPE_TARGET_TEXT),
                   ("text/uri-list", 0, TYPE_TARGET_URI)]
        widget.drag_source_set( gtk.gdk.BUTTON1_MASK, targets,
                gtk.gdk.ACTION_COPY)
        widget.connect("drag_data_get", self.on_drag_data_get)

class Droppable():

    def __init__(self, widget):
        targets = [("text/plain", 0, TYPE_TARGET_TEXT),]
        widget.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
  	                            gtk.DEST_DEFAULT_HIGHLIGHT |
	                            gtk.DEST_DEFAULT_DROP, 
                                    targets, gtk.gdk.ACTION_COPY)
        widget.connect("drag_data_received", self.on_drag_data_received)

    
class _GenericViewWidget(gtk.VBox):
    day = None
    day_signal_id = None
    icon_path = "path to an icon"# get_data_path("relative_path")
    dsc_text = "Description for toolbutton"# _("Switch to MultiView")

    def __init__(self):
        gtk.VBox.__init__(self)
        self.daylabel = DayLabel()
        self.pack_start(self.daylabel, False, False)
        self.connect("style-set", self.change_style)

    def set_day(self, day, store):
        self.store = store
        if self.day:
            self.day.disconnect(self.day_signal_id)
        self.day = day
        self.day_signal_id = self.day.connect("update", self.update_day)
        self.update_day(day)

    def update_day(self, day):
        self.daylabel.set_date(day.date)
        self.view.set_day(self.day)

    def click(self, widget, event):
        if event.button in (1, 3):
            self.emit("unfocus-day")

    def change_style(self, widget, style):
        rc_style = self.style
        color = rc_style.bg[gtk.STATE_NORMAL]
        color = shade_gdk_color(color, 102/100.0)
        self.view.modify_bg(gtk.STATE_NORMAL, color)
        self.view.modify_base(gtk.STATE_NORMAL, color)

class MultiViewContainer(gtk.HBox):

    days = []
    #TODO Add a configuration field where the user 
    #could choose the number of pages
    num_pages = 3
    day_signal_id = [None] * num_pages
    day_page_map = {}
    icon_path = get_data_path("multiview_icon.png")
    dsc_text = _("Switch to MultiView")

    def __init__(self):
        super(MultiViewContainer, self).__init__()
        self.pages = []
        for i in range(self.num_pages):
            group = DayViewContainer()
            self.pages.append(group)
            self.pack_end(group, True, True, 6)

    def set_day(self, day, store):
        t = time.time()
        if self.days:
            for i, _day in enumerate(self.__days(self.days[0], store)):
                signal = self.day_signal_id[i]
                if signal:
                    _day.disconnect(signal)
        self.days = self.__days(day, store)
        for i, day in enumerate(self.days):
            self.day_signal_id[i] = day.connect("update", self.update_day, day)
        self.update_days()

    def __days(self, day, store):
        days = []
        for i in range(self.num_pages):
            days += [day]
            day = day.previous(store)
        return days

    def update_days(self, *args):
        page_days = set([page.day for page in self.pages])
        diff = list(set(self.days).difference(page_days))
        i = 0
        day_page = {}
        for page in self.pages:
            if self.days.count(page.day) > 0:
                self.reorder_child(page, self.days.index(page.day))
        for page in self.pages:
            if not page.day in self.days:
                page.set_day(diff[i])
                day_page[page.day] = page
                i += 1
            self.reorder_child(page, self.days.index(page.day))

    def update_day(self, *args):
        day = args[1]
        for page in self.pages:
            if page.day == day:
                page.set_day(day)


class DayViewContainer(gtk.VBox):
    event_templates = (
        Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri),
        Event.new_for_values(interpretation=Interpretation.CREATE_EVENT.uri),
        Event.new_for_values(interpretation=Interpretation.ACCESS_EVENT.uri),
        Event.new_for_values(interpretation=Interpretation.SEND_EVENT.uri),
        Event.new_for_values(interpretation=Interpretation.RECEIVE_EVENT.uri)
    )
    def __init__(self):
        super(DayViewContainer, self).__init__()
        self.daylabel = DayLabel()
        self.pack_start(self.daylabel, False, False)
        self.dayviews = [DayView(title) for title in DayParts.get_day_parts()]
        self.scrolled_window = gtk.ScrolledWindow()
        self.scrolled_window.set_shadow_type(gtk.SHADOW_NONE)
        self.vp = viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        self.box = gtk.VBox()
        for dayview in self.dayviews:
            self.box.pack_start(dayview, False, False)
        viewport.add(self.box)
        self.scrolled_window.add(viewport)
        self.pack_end(self.scrolled_window, True, True)
        self.scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.show_all()
        self.day = None
        self.connect("style-set", self.change_style)

    def set_day(self, day):
        # TODO: Don't duplicate half of the code for each view, use common
        # base classes and shared interfaces instead!
        
        self.day = day
        if pinbox in self.box.get_children():
            self.box.remove(pinbox)
        if (day.date - datetime.date.today()) == datetime.timedelta(days=0):
            self.box.pack_start(pinbox, False, False)
            self.box.reorder_child(pinbox, 0)
        self.daylabel.set_date(day.date)
        
        parts = [[] for i in DayParts.get_day_parts()]
        uris = [[] for i in parts]
        
        list = day.filter(self.event_templates, result_type=ResultType.MostRecentEvents)
        for item in list:
            if not item.content_object:
                continue
            i = DayParts.get_day_part_for_item(item)
            uri = item.event.subjects[0].uri
            interpretation = item.event.interpretation
            if not uri in uris[i]:
                uris[i].append(uri)
                parts[i].append(item)
        
        for i, part in enumerate(parts):
            self.dayviews[i].set_items(part)

    def change_style(self, this, old_style):
        style = this.style
        color = style.bg[gtk.STATE_NORMAL]
        bgcolor = shade_gdk_color(color, 102/100.0)
        self.vp.modify_bg(gtk.STATE_NORMAL, bgcolor)


class DayView(gtk.VBox):

    def __init__(self, title=None):
        super(DayView, self).__init__()
        # Create the title label
        if title:
            self.label = gtk.Label(title)
            self.label.set_alignment(0.03, 0.5)
            self.pack_start(self.label, False, False, 6)
        # Create the main container
        self.view = None
        # Connect to relevant signals
        self.connect("style-set", self.on_style_change)
        self.show_all()

    def on_style_change(self, widget, style):
        """ Update used colors according to the system theme. """
        color = self.style.bg[gtk.STATE_NORMAL]
        fcolor = self.style.fg[gtk.STATE_NORMAL]
        color = combine_gdk_color(color, fcolor)
        if hasattr(self, "label"):
            self.label.modify_fg(gtk.STATE_NORMAL, color)

    def clear(self):
        if self.view:
            self.remove(self.view)
            self.view.destroy()
        self.view = gtk.VBox()
        self.pack_start(self.view)

    def set_items(self, items):
        self.clear()
        categories = {}
        for struct in items:
            if not struct.content_object: continue
            subject = struct.event.subjects[0]
            interpretation = subject.interpretation
            if INTERPRETATION_PARENTS.has_key(interpretation):
                interpretation = INTERPRETATION_PARENTS[interpretation]
            if struct.event.actor == "application://tomboy.desktop":
                interpretation = "aj://note"
            if not categories.has_key(interpretation):
                categories[interpretation] = []
            categories[interpretation].append(struct)
        if not categories:
            self.hide_all()
        else:
            ungrouped_events = []
            for key in sorted(categories.iterkeys()):
                events = categories[key]
                if len(events) > 3:
                    box = CategoryBox(key, list(reversed(events)))
                    self.view.pack_start(box)
                else:
                    ungrouped_events += events
            box = CategoryBox(None, ungrouped_events)
            self.view.pack_start(box)
            self.show_all()


class CategoryBox(gtk.HBox):
    set_up_done = False
    EXPANDED = {}

    def _set_up_box(self, event_structs):
        if not self.set_up_done:
            self.set_up_done = True
            for struct in event_structs:
                if not struct.content_object:continue
                if self.itemoff > 0:
                    item = Item(struct, self.pinnable, False)
                else:
                    item = Item(struct, self.pinnable, True)
                hbox = gtk.HBox ()
                hbox.pack_start(item, True, True, 0 )
                self.view.pack_start(hbox, False, False, 0)
                hbox.show_all()
                self.pack_end(hbox)

    def __init__(self, category, event_structs, pinnable = False, itemoff = 0):
        super(CategoryBox, self).__init__()
        self.category = category
        self.event_structs = event_structs
        self.pinnable = pinnable
        self.itemoff = itemoff
        self.view = gtk.VBox(True)
        self.vbox = gtk.VBox()
        SearchBox.connect("search", self.__highlight)
        SearchBox.connect("clear", self.__clear)
        if len(event_structs) > 0:
            d = str(datetime.date.fromtimestamp(int(event_structs[0].event.timestamp)/1000)) \
              + " " + str((time.localtime(int(event_structs[0].event.timestamp)/1000).tm_hour)/8) + " " + str(category)
            if not self.EXPANDED.has_key(d):
                self.EXPANDED[d] = False
        # If this isn't a set of ungrouped events, give it a label
        if category or category == "":
            # Place the items into a box and simulate left padding
            self.box = gtk.HBox()
            self.box.pack_start(self.view)
            self.hbox = hbox = gtk.HBox()
            # Add the title button
            if category in SUPPORTED_SOURCES:
                text = SUPPORTED_SOURCES[category].group_label(len(event_structs))
            else:
                text = "Unknown"
            self.label = gtk.Label()
            self.label.set_markup("<span>%s</span>" % text)
            #label.set_ellipsize(pango.ELLIPSIZE_END)
            hbox.pack_start(self.label, False, False, 0)
            self.label_num = gtk.Label()
            self.label_num.set_markup("<span>(%d)</span>" % len(event_structs))
            self.label_num.set_alignment(1.0,0.5)
            self.label_num.set_alignment(1.0,0.5)
            hbox.pack_end(self.label_num, False, False)
            self.al = gtk.gdk.Rectangle(0,0,0,0)
            self.i = self.connect_after("size-allocate", self.set_size)
            hbox.set_border_width(6)
            self.expander = gtk.Expander()
            self.expander.set_expanded(self.EXPANDED[d])
            if self.EXPANDED[d]:
                self._set_up_box(event_structs)
            self.expander.connect_after("activate", self.on_expand, d)
            self.expander.set_label_widget(hbox)
            self.vbox.pack_start(self.expander, True, True)
            self.expander.add(self.box)#
            self.pack_start(self.vbox, True, True, 24)
            self.expander.show_all()
            self.show()
            hbox.show_all()
            self.label_num.show_all()
            self.view.show()
            self.connect("style-set", self.on_style_change, self.label_num)
        else:
            self._set_up_box(event_structs)
            self.box = self.view
            self.vbox.pack_end(self.box)
            self.box.show()
            self.show()
            self.pack_start(self.vbox, True, True, 16 -itemoff)
        self.show_all()

    def on_style_change(self, widget, style, label):
        """ Update used colors according to the system theme. """
        color = self.style.bg[gtk.STATE_NORMAL]
        fcolor = self.style.fg[gtk.STATE_NORMAL]
        color = combine_gdk_color(color, fcolor)
        label.modify_fg(gtk.STATE_NORMAL, color)

    def set_size(self, widget, allocation):
        if self.al != allocation:
            self.al = allocation
            self.hbox.set_size_request(self.al[2]- 72, -1)

    def on_expand(self, widget, d):
        self.EXPANDED[d] = self.expander.get_expanded()
        self._set_up_box(self.event_structs)

    def __highlight(self,*args):
        matches = False
        if self.category:
            for struct in self.event_structs:
                if struct.content_object.matches_search:
                    text = self.label.get_text()
                    self.label.set_markup("<span size='large'><b>" + text + "</b></span>")
                    color = self.style.base[gtk.STATE_SELECTED]
                    self.label.modify_fg(gtk.STATE_NORMAL, color)
                    num = self.label_num.get_text()
                    self.label_num.set_markup("<span size='large'><b>" + num + "</b></span>")
                    self.label_num.modify_fg(gtk.STATE_NORMAL, color)
                    matches = True
                    break
            if not matches: self.__clear()
            

    def __clear(self, *args):
        if self.category:
            self.label.set_markup("<span>" + self.label.get_text() + "</span>")
            color = self.style.text[gtk.STATE_NORMAL]
            self.label.modify_fg(gtk.STATE_NORMAL, color)
            self.label_num.set_markup("<span>" + self.label_num.get_text() + "</span>")
            color = self.style.bg[gtk.STATE_NORMAL]
            fcolor = self.style.fg[gtk.STATE_NORMAL]
            color = combine_gdk_color(color, fcolor)
            self.label_num.modify_fg(gtk.STATE_NORMAL, color)


class Item(gtk.HBox, Draggable):

    def __init__(self, content_struct, allow_pin = False, do_style=True):
        event = content_struct.event
        gtk.HBox.__init__(self)
        self.set_border_width(2)
        self.allow_pin = allow_pin
        self.btn = gtk.Button()
        Draggable.__init__(self, self.btn)
        self.search_results = []
        self.subject = event.subjects[0]
        self.content_obj = content_struct.content_object
        self.time = float(event.timestamp) / 1000
        self.time =  time.strftime("%H:%M", time.localtime(self.time))
        if self.content_obj is not None:
            if self.subject.uri.startswith("http"):
                self.icon = self.content_obj.get_actor_pixbuf(24)
            else:
                self.icon = self.content_obj.get_icon(
                    can_thumb=settings.get('small_thumbnails', False), border=0)          
        else:
            self.icon = None
        self.btn.set_relief(gtk.RELIEF_NONE)
        self.btn.set_focus_on_click(False)
        self.__init_widget()
        self.show_all()
        self.o_style = None
        self.markup = None
        self.__highlight()
        SearchBox.connect("search", self.__highlight)
        SearchBox.connect("clear", self.__clear)
        if do_style:
            self.connect("style-set", self.change_style)

    def change_style(self, widget, style):
        rc_style = self.style
        color = rc_style.bg[gtk.STATE_NORMAL]
        color = shade_gdk_color(color, 102/100.0)
        for w in self:
            w.modify_bg(gtk.STATE_NORMAL, color)

    def __highlight(self, *args):
        if not self.o_style:
            self.o_style = self.style.copy()
        rc_style = self.o_style.copy()
        text = self.content_obj.text.replace("&", "&amp;")
        if text.strip() == "":
            text = self.content_obj.uri.replace("&", "&amp;")
        if self.content_obj.matches_search:
            self.label.set_markup("<span size='large'><b>" + text + "</b></span>")
            color = rc_style.base[gtk.STATE_SELECTED]
            self.label.modify_fg(gtk.STATE_NORMAL, color)
        else:
            self.label.set_markup("<span>" + text + "</span>")
            color = rc_style.text[gtk.STATE_NORMAL]
            self.label.modify_fg(gtk.STATE_NORMAL, color)

    def __clear(self, *args):
        self.content_obj.matches_search = False
        text = self.content_obj.text.replace("&", "&amp;")
        if text.strip() == "":
            text = self.content_obj.uri.replace("&", "&amp;")
        rc_style = self.o_style
        self.label.set_markup("<span>" + text + "</span>")
        color = rc_style.text[gtk.STATE_NORMAL]
        self.label.modify_fg(gtk.STATE_NORMAL, color)

    def __init_widget(self):
        self.label = gtk.Label()
        text = self.content_obj.text.replace("&", "&amp;")
        text.strip()
        if self.content_obj.text.strip() == "":
            text = self.content_obj.uri
        self.label.set_markup(text)
        self.label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self.label.set_alignment(0.0, 0.5)
        if self.icon: img = gtk.image_new_from_pixbuf(self.icon)
        else: img = None
        hbox = gtk.HBox()
        if img: hbox.pack_start(img, False, False, 1)
        hbox.pack_start(self.label, True, True, 4)
        if self.allow_pin:
            # TODO: get the name "pin" from theme when icons are properly installed
            img = gtk.image_new_from_file(get_icon_path("hicolor/24x24/status/pin.png"))
            self.pin = gtk.Button()
            self.pin.add(img)
            self.pin.set_tooltip_text(_("Remove Pin"))
            self.pin.set_focus_on_click(False)
            self.pin.set_relief(gtk.RELIEF_NONE)
            self.pack_end(self.pin, False, False)
            self.pin.connect("clicked", lambda x: self.set_bookmarked(False))
        evbox = gtk.EventBox()
        self.btn.add(hbox)
        evbox.add(self.btn)
        self.pack_start(evbox)
        self.btn.connect("clicked", self.launch)
        self.btn.connect("button_press_event", self._show_item_popup)
        self.btn.connect("realize", self.realize_cb, evbox)
        self.init_multimedia_tooltip()
        

    def on_drag_data_get(self, treeview, context, selection, target_id, etime):
        uri = self.content_obj.uri
        if target_id == TYPE_TARGET_TEXT:
            selection.set_text(uri, -1)
        elif target_id == TYPE_TARGET_URI:
            if uri.startswith("file://"):
                unquoted_uri = urllib.unquote(uri)
                if os.path.exists(unquoted_uri[7:]):
                    selection.set_uris([uri])

    def realize_cb(self, widget, evbox):
        evbox.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))

    def init_multimedia_tooltip(self):
        """add multimedia tooltip to multimedia files
        multimedia tooltip is shown for all images, all videos and pdfs

        TODO: make loading of multimedia thumbs async
        """
        if isinstance(self.content_obj, GioFile) and self.content_obj.has_preview():
            icon_names = self.content_obj.icon_names
            self.set_property("has-tooltip", True)
            self.connect("query-tooltip", self._handle_tooltip)
            if "video-x-generic" in icon_names and gst is not None:
                self.set_tooltip_window(VideoPreviewTooltip)
            elif "audio-x-generic" in icon_names and gst is not None:
                self.set_tooltip_window(AudioPreviewTooltip) 
            else:
                self.set_tooltip_window(StaticPreviewTooltip)

    def _handle_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        tooltip_window = self.get_tooltip_window()
        return tooltip_window.preview(self.content_obj)

    def _show_item_popup(self, widget, ev):
        if ev.button == 3:
            items = [self.content_obj]
            ContextMenu.do_popup(ev.time, items)

    def set_bookmarked(self, bool_):
        uri = unicode(self.subject.uri)
        bookmarker.bookmark(uri) if bool_ else bookmarker.unbookmark(uri)
        if not bool_: self.destroy()

    def launch(self, *discard):
        if self.content_obj is not None:
            self.content_obj.launch()


#####################
## ThumbView code
#####################
class ThumbViewContainer(_GenericViewWidget):
    icon_path = get_data_path("thumbview_icon.png")
    dsc_text = _("Switch to ThumbView")

    def __init__(self):
        _GenericViewWidget.__init__(self)
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.view = ThumbView()
        self.scrolledwindow.add_with_viewport(self.view)
        self.scrolledwindow.get_children()[0].set_shadow_type(gtk.SHADOW_NONE)
        self.pack_end(self.scrolledwindow)
        self.show_all()


class _ThumbViewRenderer(gtk.GenericCellRenderer):
    """
    A IconView renderer to be added to a cellayout. It displays a pixbuf and
    data based on the event property
    """

    __gtype_name__ = "_ThumbViewRenderer"
    __gproperties__ = {
        "content_obj" :
        (gobject.TYPE_PYOBJECT,
         "event to be displayed",
         "event to be displayed",
         gobject.PARAM_READWRITE,
         ),
    }

    width = 96
    height = 72
    properties = {}

    @property
    def content_obj(self):
        return self.get_property("content_obj")

    @property
    def emblems(self):
        return self.content_obj.emblems

    @property
    def pixbuf(self):
        return self.content_obj.thumbview_pixbuf

    @property
    def event(self):
        return self.content_obj.event

    def __init__(self):
        super(_ThumbViewRenderer, self).__init__()
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
        pixbuf_w = self.pixbuf.get_width() if self.pixbuf else 0
        pixbuf_h = self.pixbuf.get_height() if self.pixbuf else 0
        if (pixbuf_w, pixbuf_h) == content_objects.SIZE_THUMBVIEW:
            render_pixbuf(window, x, y, self.pixbuf)
        else:
            self.file_render_pixbuf(window, widget, x, y, w, h)
        render_emblems(window, x, y, w, h, self.emblems)
        path = widget.get_path_at_pos(cell_area.x, cell_area.y)
        if path != None:
            try:
                if widget.active_list[path[0]]:
                    gobject.timeout_add(2, self.render_info_box, window, widget, cell_area, expose_area, self.event)
            except:pass
        return True

    @staticmethod
    def insert_file_markup(text):
        text = text.replace("&", "&amp;")
        text = "<span size='6400'>" + text + "</span>"
        return text

    def file_render_pixbuf(self, window, widget, x, y, w, h):
        """
        Renders a icon and file name for non-thumb objects
        """
        context = window.cairo_create()
        pixbuf = self.pixbuf
        if pixbuf:
            imgw, imgh = pixbuf.get_width(), pixbuf.get_height()
            ix = x + (self.width - imgw)
            iy = y + self.height - imgh
        context.rectangle(x, y, w, h)
        context.set_source_rgb(1, 1, 1)
        context.fill_preserve()
        if pixbuf:
            context.set_source_pixbuf(pixbuf, ix, iy)
            context.fill()
        draw_frame(context, x, y, w, h)
        context = window.cairo_create()
        text = self.insert_file_markup(self.content_obj.thumbview_text)

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
        t1 = event.subjects[0].text
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
        pass


class ThumbIconView(gtk.IconView, Draggable):
    """
    A iconview which uses a custom cellrenderer to render square pixbufs
    based on zeitgeist events
    """
    last_active = -1
    child_width = _ThumbViewRenderer.width
    child_height = _ThumbViewRenderer.height
    def __init__(self):
        gtk.IconView.__init__(self)
        Draggable.__init__(self, self)
        self.active_list = []
        self.popupmenu = ContextMenu
        self.add_events(gtk.gdk.LEAVE_NOTIFY_MASK)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("leave-notify-event", self.on_leave_notify)
        self.set_selection_mode(gtk.SELECTION_SINGLE)
        self.set_column_spacing(6)
        self.set_row_spacing(6)
        pcolumn = gtk.TreeViewColumn("Preview")
        render = _ThumbViewRenderer()
        self.pack_end(render)
        self.add_attribute(render, "content_obj", 0)
        self.set_margin(10)
        SearchBox.connect("search", lambda *args: self.queue_draw())
        SearchBox.connect("clear", lambda *args: self.queue_draw())

    def _set_model_in_thread(self, items):
        """
        A threaded which generates pixbufs and emblems for a list of events.
        It takes those properties and appends them to the view's model
        """
        lock = threading.Lock()
        self.active_list = []
        liststore = gtk.ListStore(gobject.TYPE_PYOBJECT)
        gtk.gdk.threads_enter()
        self.set_model(liststore)
        gtk.gdk.threads_leave()

        for item in items:
            obj = item.content_object
            if not obj: continue
            gtk.gdk.threads_enter()
            lock.acquire()
            self.active_list.append(False)
            liststore.append((obj,))
            lock.release()
            gtk.gdk.threads_leave()

    def set_model_from_list(self, items):
        """
        Sets creates/sets a model from a list of zeitgeist events
        :param events: a list of :class:`Events <zeitgeist.datamodel.Event>`
        """
        self.last_active = -1
        if not items:
            self.set_model(None)
            return
        thread = threading.Thread(target=self._set_model_in_thread, args=(items,))
        thread.start()

    def on_drag_data_get(self, iconview, context, selection, target_id, etime):
        model = iconview.get_model()
        selected = iconview.get_selected_items()
        content_object = model[selected[0]][0]
        uri = content_object.uri
        if target_id == TYPE_TARGET_TEXT:
            selection.set_text(uri, -1)
        elif target_id == TYPE_TARGET_URI:
            if uri.startswith("file://"):
                unquoted_uri = urllib.unquote(uri)
                if os.path.exists(unquoted_uri[7:]):
                    selection.set_uris([uri])     

    def on_button_press(self, widget, event):
        if event.button == 3:
            val = self.get_item_at_pos(int(event.x), int(event.y))
            if val:
                path, cell = val
                model = self.get_model()
                obj = model[path[0]][0]
                self.popupmenu.do_popup(event.time, [obj])
    
    def on_button_release(self, widget, event):
        if event.button == 1:
            val = self.get_item_at_pos(int(event.x), int(event.y))
            if val:
                path, cell = val
                model = self.get_model()
                obj = model[path[0]][0]
                obj.launch()

    def on_leave_notify(self, widget, event):
        try:
            self.active_list[self.last_active] = False
        except IndexError:pass
        self.last_active = -1
        self.queue_draw()

    def on_motion_notify(self, widget, event):
        val = self.get_item_at_pos(int(event.x), int(event.y))
        if val:
            path, cell = val
            if path[0] != self.last_active:
                self.active_list[self.last_active] = False
                self.active_list[path[0]] = True
                self.last_active = path[0]
                self.queue_draw()

    def query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """
        Displays a tooltip based on x, y
        """
        path = self.get_path_at_pos(int(x), int(y))
        if path:
            model = self.get_model()
            uri = model[path[0]][3].uri
            interpretation = model[path[0]][3].subjects[0].interpretation
            tooltip_window = widget.get_tooltip_window()
            if interpretation == Interpretation.VIDEO.uri:
                self.set_tooltip_window(VideoPreviewTooltip)
            else:
                self.set_tooltip_window(StaticPreviewTooltip)
            gio_file = content_objects.GioFile.create(uri)
            return tooltip_window.preview(gio_file)
        return False


class ThumbView(gtk.VBox):
    """
    A container for three image views representing periods in time
    """
    event_templates = (
            Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.CREATE_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.ACCESS_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.RECEIVE_EVENT.uri)
        )
    def __init__(self):
        """Woo"""
        gtk.VBox.__init__(self)
        self.views = []
        self.labels = []
        for text in DayParts.get_day_parts():
            label = gtk.Label()
            label.set_markup("\n  <span size='10336'>%s</span>" % (text))
            label.set_justify(gtk.JUSTIFY_RIGHT)
            label.set_alignment(0, 0)
            self.views.append(ThumbIconView())
            self.labels.append(label)
            self.pack_start(label, False, False)
            self.pack_start(self.views[-1], False, False)
        self.connect("style-set", self.change_style)

    def set_phase_items(self, i, items):
        """
        Set a time phases events

        :param i: a index for the three items in self.views. 0:Morning,1:AfterNoon,2:Evening
        :param events: a list of :class:`Events <zeitgeist.datamodel.Event>`
        """
        view = self.views[i]
        label = self.labels[i]
        if not items or len(items) == 0:
            view.hide_all()
            label.hide_all()
            view.set_model_from_list(None)
            return False
        view.show_all()
        label.show_all()
        view.set_model_from_list(items)


    def set_day(self, day):
        parts = [[] for i in DayParts.get_day_parts()]
        uris = [[] for i in parts]
        
        list = day.filter(self.event_templates, result_type=ResultType.MostRecentEvents)
        for item in list:
            if event_exists(item.event.subjects[0].uri):
                i = DayParts.get_day_part_for_item(item)
                uri = item.event.subjects[0].uri
                interpretation = item.event.interpretation
                if not uri in uris[i]:
                    uris[i].append(uri)
                    parts[i].append(item)

        for i, part in enumerate(parts):
            self.set_phase_items(i, part)

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


class TimelineViewContainer(_GenericViewWidget):
    icon_path = get_data_path("timelineview_icon.png")
    dsc_text = _("Switch to TimelineView")

    def __init__(self):
        _GenericViewWidget.__init__(self)
        self.ruler = _TimelineHeader()
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.view = TimelineView()
        self.scrolledwindow.add(self.view)
        self.pack_end(self.scrolledwindow)
        self.pack_end(self.ruler, False, False)
        self.view.set_events(gtk.gdk.POINTER_MOTION_MASK | gtk.gdk.POINTER_MOTION_HINT_MASK)

    def change_style(self, widget, style):
        _GenericViewWidget.change_style(self, widget, style)
        rc_style = self.style
        color = rc_style.bg[gtk.STATE_NORMAL]
        color = shade_gdk_color(color, 102/100.0)
        self.ruler.modify_bg(gtk.STATE_NORMAL, color)


class _TimelineRenderer(gtk.GenericCellRenderer):
    """
    Renders timeline columns, and text for a for properties
    """

    __gtype_name__ = "TimelineRenderer"
    __gproperties__ = {
        "content_obj" :
        (gobject.TYPE_PYOBJECT,
         "event to be displayed",
         "event to be displayed",
         gobject.PARAM_READWRITE,
         ),
    }

    width = 32
    height = 48
    barsize = 5
    properties = {}

    textcolor = {gtk.STATE_NORMAL : ("#ff", "#ff"),
                 gtk.STATE_SELECTED : ("#ff", "#ff")}

    @property
    def content_obj(self):
        return self.get_property("content_obj")

    @property
    def phases(self):
        return self.content_obj.phases

    @property
    def event(self):
        return self.content_obj.event

    @property
    def colors(self):
        """ A tuple of two colors, the first being the base the outer being the outline"""
        return self.content_obj.type_color_representation

    @property
    def text(self):
        return self.content_obj.timelineview_text

    @property
    def pixbuf(self):
        return self.content_obj.timelineview_pixbuf

    def __init__(self):
        super(_TimelineRenderer, self).__init__()
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
            context.set_source_rgb(*self.colors[0])
            start = int(start * w)
            end = max(int(end * w), 8)
            if start + 8 > w:
                start = w - 8
            context.rectangle(x+ start, y, end, self.barsize)
            context.fill()
            context.set_source_rgb(*self.colors[1])
            context.set_line_width(1)
            context.rectangle(x + start+0.5, y+0.5, end, self.barsize)
            context.stroke()
        x = int(phases[0][0]*w)
        # Pixbuf related junk which is really dirty
        self.render_text_with_pixbuf(window, widget, x, y, w, h, flags)
        return True

    def render_text_with_pixbuf(self, window, widget, x, y, w, h, flags):
        uri = self.content_obj.uri
        imgw, imgh = self.pixbuf.get_width(), self.pixbuf.get_height()
        x = max(x + imgw/2 + 4, 0 + imgw + 4)
        x, y = self.render_text(window, widget, x, y, w, h, flags)
        x -= imgw + 4
        y += self.barsize + 3
        pixbuf_w = self.pixbuf.get_width() if self.pixbuf else 0
        pixbuf_h = self.pixbuf.get_height() if self.pixbuf else 0
        if (pixbuf_w, pixbuf_h) == content_objects.SIZE_TIMELINEVIEW:
            drawframe = True
        else: drawframe = False
        render_pixbuf(window, x, y, self.pixbuf, drawframe=drawframe)

    def render_text(self, window, widget, x, y, w, h, flags):
        w = window.get_geometry()[2]
        y+= 2
        x += 5
        state = gtk.STATE_SELECTED if gtk.CELL_RENDERER_SELECTED & flags else gtk.STATE_NORMAL
        color1, color2 = self.textcolor[state]
        text = self._make_timelineview_text(self.text, color1.to_string(), color2.to_string())
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

    @staticmethod
    def _make_timelineview_text(text, color1, color2):
        """
        :returns: a string of text markup used in timeline widget and elsewhere
        """
        text = text.split("\n")
        if len(text) > 1:
            p1, p2 = text[0], text[1]
        else:
            p1, p2 = text[0], " "
        t1 = "<span color='" + color1 + "'><b>" + p1 + "</b></span>"
        t2 = "<span color='" + color2 + "'>" + p2 + "</span> "
        return (str(t1) + "\n" + str(t2) + "").replace("&", "&amp;")

    def on_start_editing(self, event, widget, path, background_area, cell_area, flags):
        pass

    def on_activate(self, event, widget, path, background_area, cell_area, flags):
        pass


class TimelineView(gtk.TreeView, Draggable):
    child_width = _TimelineRenderer.width
    child_height = _TimelineRenderer.height

    @staticmethod
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

    def __init__(self):
        gtk.TreeView.__init__(self)
        Draggable.__init__(self, self)
        self.popupmenu = ContextMenu
        self.add_events(gtk.gdk.LEAVE_NOTIFY_MASK)
        self.connect("button-press-event", self.on_button_press)
        self.connect("row-activated" , self.on_activate)
        self.connect("style-set", self.change_style)
        pcolumn = gtk.TreeViewColumn("Timeline")
        self.render = render = _TimelineRenderer()
        pcolumn.pack_start(render)
        self.append_column(pcolumn)
        pcolumn.add_attribute(render, "content_obj", 0)
        self.set_headers_visible(False)
        self.set_property("has-tooltip", True)
        self.set_tooltip_window(StaticPreviewTooltip)
        SearchBox.connect("search", lambda *args: self.queue_draw())
        SearchBox.connect("clear", lambda *args: self.queue_draw())

    def set_model_from_list(self, items):
        """
        Sets creates/sets a model from a list of zeitgeist events

        :param events: a list of :class:`Events <zeitgeist.datamodel.Event>`
        """
        if not items:
            self.set_model(None)
            return
        liststore = gtk.ListStore(gobject.TYPE_PYOBJECT)
        for row in items:
            #take the last and more updated content_obj
            item = row[len(row)-1][0]
            obj = item.content_object
            if not obj: continue
            obj.phases = [self.make_area_from_event(item.event.timestamp, stop) for (item, stop) in row]
            obj.phases.sort(key=lambda x: x[0])
            liststore.append((obj,))
        self.set_model(liststore)

    def set_day(self, day):
        items = day.get_time_map()
        self.set_model_from_list(items)

    def on_drag_data_get(self, treeview, context, selection, target_id, etime):
        tree_selection = treeview.get_selection()
        model, iter = tree_selection.get_selected()
        content_object = model.get_value(iter, 0)
        uri = content_object.uri
        if target_id == TYPE_TARGET_TEXT:
            selection.set_text(uri, -1)
        elif target_id == TYPE_TARGET_URI:
            if uri.startswith("file://"):
                unquoted_uri = urllib.unquote(uri)
                if os.path.exists(unquoted_uri[7:]):
                    selection.set_uris([uri])

    def on_button_press(self, widget, event):
        if event.button == 3:
            path = self.get_dest_row_at_pos(int(event.x), int(event.y))
            if path:
                model = self.get_model()
                obj = model[path[0]][0]
                self.popupmenu.do_popup(event.time, [obj])
                return True
        return False

    def on_activate(self, widget, path, column):
        model = self.get_model()
        model[path][0].launch()

    def change_style(self, widget, old_style):
        """
        Sets the widgets style and coloring
        """
        layout = self.create_pango_layout("")
        layout.set_markup("<b>qPqPqP|</b>\nqPqPqP|")
        tw, th = layout.get_pixel_size()
        self.render.height = max(_TimelineRenderer.height, th + 3 + _TimelineRenderer.barsize)
        if self.window:
            width = self.window.get_geometry()[2] - 4
            self.render.width = max(_TimelineRenderer.width, width)
        self.render.set_fixed_size(self.render.width, self.render.height)
        def change_color(color, inc):
            color = shade_gdk_color(color, inc/100.0)
            return color
        normal = (self.style.text[gtk.STATE_NORMAL], change_color(self.style.text[gtk.STATE_INSENSITIVE], 70))
        selected = (self.style.text[gtk.STATE_SELECTED], self.style.text[gtk.STATE_SELECTED])
        self.render.textcolor[gtk.STATE_NORMAL] = normal
        self.render.textcolor[gtk.STATE_SELECTED] = selected


class _TimelineHeader(gtk.DrawingArea):
    time_text = {4:"4:00", 8:"8:00", 12:"12:00", 16:"16:00", 20:"20:00"}
    odd_line_height = 6
    even_line_height = 12

    line_color = (0, 0, 0, 1)

    def __init__(self):
        super(_TimelineHeader, self).__init__()
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


class PinBox(DayView, Droppable):

    def __init__(self):
        self.event_timerange = TimeRange.until_now()
        DayView.__init__(self, title=_("Pinned Items"))#_("Pinned items"))
        self.notebook = gtk.Notebook()
        Droppable.__init__(self, self.notebook)

        bookmarker.connect("reload", self.set_from_templates)
        self.set_from_templates()

    @property
    def event_templates(self):
        if not bookmarker.bookmarks:
            # Abort, or we will query with no templates and get lots of
            # irrelevant events.
            return None
        templates = []
        for bookmark in bookmarker.bookmarks:
            subject = Subject.new_for_values(uri=bookmark)
            templates.append(Event.new_for_values(subjects=[subject]))
        return templates

    def set_from_templates(self, *args, **kwargs):
        if bookmarker.bookmarks:
            CLIENT.find_event_ids_for_templates(
                self.event_templates, self.do_set,
                self.event_timerange,
                StorageState.Any, 10000, ResultType.MostRecentSubjects)
        else:
            self.do_set([])

    def do_set(self, event_ids):
        objs = []
        for id_ in event_ids:
            objs += [ContentStruct(id_)]
        self.set_items(objs)
        # Make the pin icons visible
        self.view.show_all()
        self.show_all()

    def set_items(self, items):
        self.clear()
        box = CategoryBox(None, items, True, itemoff=4)
        self.view.pack_start(box)
        for w in self:
            self.remove(w)
        self.notebook.append_page(self.view, self.label)
        self.label.set_alignment(0.01, 0.5)
        self.notebook.set_tab_label_packing(self.view, True, True, gtk.PACK_START)
        self.set_border_width(4)
        if len(items) > 0: self.pack_start(self.notebook)

    def on_drag_data_received(self, wid, context, x, y, selection, target_type, time):
        uri = unicode(selection.data.strip())
        isbookmarked = bookmarker.is_bookmarked(uri)
        if not isbookmarked:
            bookmarker.bookmark(uri)


## gobject registration
gobject.type_register(_TimelineRenderer)
gobject.type_register(_ThumbViewRenderer)

pinbox = PinBox()

