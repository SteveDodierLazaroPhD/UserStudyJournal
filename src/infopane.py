# -.- coding: utf-8 -.-
#
# Filename
#
# Copyright © 2010 Randal Barlow
# Copyright © 2010 Markus Korn <thekorn@gmx.de>
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

# Purpose:

import gobject
import gtk
import mimetypes
import os
import pango
try: import gst
except ImportError:
    gst = None
try: import gtksourceview2
except ImportError: gtksourceview2 = None
import threading

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
     ResultType, TimeRange

import content_objects
from common import *
from gio_file import GioFile
import supporting_widgets
from store import STORE

try:
    from tracker_wrapper import TRACKER
except ImportError: TRACKER = None


GENERIC_DISPLAY_NAME = "other"
MIMETYPEMAP = {
    GENERIC_DISPLAY_NAME : ("image", None),
    #"multimedia" : ("video", "audio"),
    #"text" : ("text",),
}
CLIENT = ZeitgeistClient()


def get_related_events_for_uri(uri, callback):
    """
    :param uri: A uri for which to request related uris using zetigeist
    :param callback: this callback is called once the events are retrieved for
    the uris. It is called with a list of events.
    """
    def _event_request_handler(uris):
        """
        :param uris: a list of uris which are related to the windows current uri
        Seif look here
        """
        templates = []
        if len(uris) > 0:
            for i, uri in enumerate(uris):
                templates += [
                        Event.new_for_values(interpretation=Interpretation.VISIT_EVENT.uri, subject_uri=uri),
                        Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri, subject_uri=uri),
                        Event.new_for_values(interpretation=Interpretation.CREATE_EVENT.uri, subject_uri=uri),
                        Event.new_for_values(interpretation=Interpretation.OPEN_EVENT.uri, subject_uri=uri)
                    ]
            CLIENT.find_events_for_templates(templates, callback,
                                             [0, time.time()*1000], num_events=50000,
                                             result_type=ResultType.MostRecentSubjects)

    end = time.time() * 1000
    start = end - (86400*30*1000)
    CLIENT.find_related_uris_for_uris([uri], _event_request_handler)


def get_media_type(gfile):
    uri = gfile.uri
    if not uri.startswith("file://") or not gfile:
        return GENERIC_DISPLAY_NAME
    majortype = gfile.mime_type.split("/")[0]
    for key, mimes in MIMETYPEMAP.iteritems():
        if majortype in mimes:
            return key
    #if isinstance(gfile, GioFile):
    #    if "text-x-generic" in gfile.icon_names or "text-x-script" in gfile.icon_names:
    #        return "text"
    return GENERIC_DISPLAY_NAME


class ContentDisplay(object):
    """
    The abstract base class for content displays
    """
    def set_content_object(self, obj):
        """
        :param obj a content object which the Content Display displays
        """
        pass

    def set_inactive(self):
        """
        This method performs clean when the displays are swapped
        """
        pass


class ScrolledDisplay(gtk.ScrolledWindow):
    """
    A scrolled window container that acts as a proxy for a child
    use type to make wrapers for your type
    """
    child_type = gtk.Widget
    def __init__(self):
        super(ScrolledDisplay, self).__init__()
        self._child_obj = self.child_type()
        self.add(self._child_obj)
        self.set_shadow_type(gtk.SHADOW_IN)
        self.set_size_request(-1, 200)

    def set_content_object(self, obj): self._child_obj.set_content_object(obj)
    def set_inactive(self): self._child_obj.set_inactive()


class TextDisplay(gtksourceview2.View if gtksourceview2
                  else gtk.TextView, ContentDisplay):
    """
    A text preview display which uses a sourceview or a textview if sourceview
    modules are not found
    """
    def __init__(self):
        """"""
        super(TextDisplay, self).__init__()
        self.textbuffer = (gtksourceview2.Buffer() if gtksourceview2
                           else gtk.TextBuffer())
        self.set_buffer(self.textbuffer)
        self.set_editable(False)
        font  = pango.FontDescription()
        font.set_family("Monospace")
        self.modify_font(font)
        if gtksourceview2:
            self.manager = gtksourceview2.LanguageManager()
            self.textbuffer.set_highlight_syntax(True)

    def get_language_from_mime_type(self, mime):
        for id_ in self.manager.get_language_ids():
            temp_language = self.manager.get_language(id_)
            if mime in temp_language.get_mime_types():
                return temp_language
        return None

    def set_content_object(self, obj):
        if obj:
            content = obj.get_content()
            self.textbuffer.set_text(content)
            if gtksourceview2:
                lang = self.get_language_from_mime_type(obj.mime_type)
                self.textbuffer.set_language(lang)


class ImageDisplay(gtk.Image, ContentDisplay):
    """
    A display based on GtkImage to display a uri's thumb or icon using GioFile
    """
    def set_content_object(self, obj):
        if obj:
            if isinstance(obj, GioFile) and obj.has_preview():
                pixbuf = obj.get_thumbnail(size=SIZE_NORMAL, border=3)
            else:
                pixbuf = obj.get_icon(size=128)
            self.set_from_pixbuf(pixbuf)


class MultimediaDisplay(gtk.VBox, ContentDisplay):
    """
    a display which words for video and audio using gstreamer
    """
    def __init__(self):
        super(MultimediaDisplay, self).__init__()
        self.playing = False
        self.mediascreen = gtk.DrawingArea()
        self.player = gst.element_factory_make("playbin", "player")
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)
        buttonbox = gtk.HBox()
        self.playbutton = gtk.Button()
        buttonbox.pack_start(self.playbutton, True, False)
        self.playbutton.gtkimage = gtk.Image()
        self.playbutton.add(self.playbutton.gtkimage)
        self.playbutton.gtkimage.set_from_stock(gtk.STOCK_MEDIA_PAUSE, 2)
        self.pack_start(self.mediascreen, True, True, 10)
        self.pack_end(buttonbox, False, False)
        self.playbutton.connect("clicked", self.on_play_click)
        self.playbutton.set_relief(gtk.RELIEF_NONE)
        self.connect("hide", self._handle_hide)

    def _handle_hide(self, widget):
        self.player.set_state(gst.STATE_NULL)

    def set_playing(self):
        """
        Set MultimediaDisplay.player's state to playing
        """
        self.player.set_state(gst.STATE_PLAYING)
        self.playbutton.gtkimage.set_from_stock(gtk.STOCK_MEDIA_PAUSE, 2)
        self.playing = True

    def set_paused(self):
        """
        Set MultimediaDisplay.player's state to paused
        """
        self.player.set_state(gst.STATE_PAUSED)
        self.playbutton.gtkimage.set_from_stock(gtk.STOCK_MEDIA_PLAY, 2)
        self.playing = False


    def set_content_object(self, obj):
        if isinstance(obj, GioFile):
            self.player.set_state(gst.STATE_NULL)
            self.player.set_property("uri", obj.uri)
            self.set_playing()

    def set_inactive(self):
        self.player.set_state(gst.STATE_NULL)
        self.playing = False

    def on_play_click(self, widget):
        if self.playing:
            return self.set_paused()
        return self.set_playing()

    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            gtk.gdk.threads_enter()
            try:
                self.show_all()
                imagesink.set_xwindow_id(self.mediascreen.window.xid)
            finally:
                gtk.gdk.threads_leave()

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
        elif t == gst.MESSAGE_ERROR:
            self.player.set_state(gst.STATE_NULL)
            err, debug = message.parse_error()
            print "Error: %s" % err, debug


class EventDataPane(gtk.Table):
    x = 2
    y = 8

    column_names = (
        _("Actor"), # 0
        _("Time"), # 1
        _(""), # 2
        _("Interpretation"), # 3
        _("Subject Interpretation"), # 4
        _("Manifestation"),
    )


    def __init__(self):
        super(EventDataPane, self).__init__(self.x, self.y)
        self.set_col_spacings(4)
        self.set_row_spacings(4)
        self.labels = []
        for i, name in enumerate(self.column_names):
            #for i in xrange(len(self.column_names)):
            namelabel = gtk.Label()
            if name:
                namelabel.set_markup("<b>" + name + ":</b>")
            namelabel.set_alignment(0, 0)
            self.attach(namelabel, 0, 1, i, i+1)
            label = gtk.Label()
            label.set_alignment(0, 0)
            self.attach(label, 1, 2, i, i+1)
            self.labels.append(label)

    def set_content_object(self, obj):
        event = obj.event
        # Actor
        desktop_file = obj.get_actor_desktop_file()
        if desktop_file:
            actor = desktop_file.getName()
        else: actor = event.actor
        self.labels[0].set_text(actor)
        # Time
        local_t = time.localtime(int(event.timestamp)/1000)
        time_str = time.strftime("%b %d %Y %H:%M:%S", local_t)
        self.labels[1].set_text(time_str)
        #self.labels[2].set_text(event.subjects[0].uri)
        # Interpetation
        try: interpretation_name = Interpretation[event.interpretation].display_name
        except KeyError: interpretation_name = ""
        self.labels[3].set_text(interpretation_name)
        # Subject Interpetation
        try: subject_interpretation_name = Interpretation[event.subjects[0].interpretation].display_name
        except KeyError: subject_interpretation_name = ""
        self.labels[4].set_text(subject_interpretation_name)
        # Manifestation
        try: manifestation_name = Manifestation[event.manifestation].display_name
        except KeyError: manifestation_name = ""
        self.labels[5].set_text(manifestation_name)


class InformationPane(gtk.VBox):
    """
    . . . . . . . .
    .             .
    .    Info     .
    .             .
    .             .
    . . . . . . . .

    Holds widgets which display information about a uri
    """
    displays = {
        GENERIC_DISPLAY_NAME : ImageDisplay,
        "multimedia" : MultimediaDisplay if gst else ImageDisplay,
        "text" : type("TextScrolledWindow", (ScrolledDisplay,),
                      {"child_type" : TextDisplay}),
    }

    obj = None

    def __init__(self):
        super(InformationPane, self).__init__()
        vbox = gtk.VBox()
        self.box = gtk.Frame()
        self.label = gtk.Label()
        self.pathlabel = gtk.Label()
        labelvbox = gtk.VBox()
        labelvbox.pack_start(self.label)
        labelvbox.pack_end(self.pathlabel)
        self.displays = self.displays.copy()
        #self.set_shadow_type(gtk.SHADOW_NONE)
        #self.set_label_widget(labelvbox)
        self.pack_start(labelvbox)
        self.box.set_shadow_type(gtk.SHADOW_NONE)
        vbox.pack_start(self.box, True, True)
        #self.set_label_align(0.5, 0.5)
        #self.label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        #self.pathlabel.set_size_request(100, -1)
        #self.pathlabel.set_size_request(300, -1)
        self.pathlabel.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        #self.datapane = EventDataPane()
        #vbox.pack_end(self.datapane, False, False)
        self.add(vbox)
        self.show_all()

    def set_displaytype(self, obj):
        """
        Determines the ContentDisplay to use for a given uri
        """
        media_type = get_media_type(obj)
        display_widget = self.displays[media_type]
        if isinstance(display_widget, type):
            display_widget = self.displays[media_type] = display_widget()
        if display_widget.parent != self.box:
            child = self.box.get_child()
            if child:
                self.box.remove(child)
                child.set_inactive()
            self.box.add(display_widget)
        display_widget.set_content_object(obj)
        self.show_all()

    def set_content_object(self, obj):
        self.obj = obj
        self.set_displaytype(obj)
        self.label.set_markup("<span size='12336'>" + obj.text.replace("&", "&amp;") + "</span>")
        self.pathlabel.set_markup("<span color='#979797'>" + obj.uri + "</span>")
        #self.datapane.set_content_object(obj)

    def set_inactive(self):
        display = self.box.get_child()
        if display: display.set_inactive()


class RelatedPane(gtk.TreeView):
    """
                     . . .
                     .   .
                     .   . <--- Related files
                     .   .
                     .   .
                     . . .

    Displays related events using a widget based on gtk.TreeView
    """
    def __init__(self):
        super(RelatedPane, self).__init__()
        self.popupmenu = supporting_widgets.ContextMenu
        self.connect("button-press-event", self.on_button_press)
        self.connect("row-activated", self.row_activated)
        pcolumn = gtk.TreeViewColumn(_("Related Items"))
        pixbuf_render = gtk.CellRendererPixbuf()
        pcolumn.pack_start(pixbuf_render, False)
        pcolumn.set_cell_data_func(pixbuf_render, self.celldatamethod, "pixbuf")
        text_render = gtk.CellRendererText()
        text_render.set_property("ellipsize", pango.ELLIPSIZE_MIDDLE)
        pcolumn.pack_end(text_render, True)
        pcolumn.set_cell_data_func(text_render, self.celldatamethod, "text")
        self.append_column(pcolumn)
        #self.set_headers_visible(False)

    def celldatamethod(self, column, cell, model, iter_, user_data):
        if model:
            obj = model.get_value(iter_, 0)
            if user_data == "text":
                cell.set_property("text", obj.text.replace("&", "&amp;"))
            elif user_data == "pixbuf":
                cell.set_property("pixbuf", obj.icon)

    def _set_model_in_thread(self, events):
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
        for event in events:
            obj = content_objects.choose_content_object(event)
            if not obj: continue
            gtk.gdk.threads_enter()
            lock.acquire()
            self.active_list.append(False)
            liststore.append((obj,))
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


class NewTagToolEntry(supporting_widgets.SearchEntry):
    default_text = _("Type to add a tag")
    def __init__(self):
        super(NewTagToolEntry, self).__init__()


class NewTagTool(gtk.ToolItem):
    __gsignals__ = {
        "finished":  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,(gobject.TYPE_STRING,)),
    }
    def __init__(self):
        super(NewTagTool, self).__init__()
        self.hbox = gtk.HBox()
        self.button = supporting_widgets.StockIconButton(gtk.STOCK_OK)
        self.entry = NewTagToolEntry()
        self.entry.set_size_request(100,-1)
        self.hbox.pack_start(self.entry, True, True)
        self.hbox.pack_end(self.button, True, True)
        self.add(self.hbox)
        self.button.connect("clicked", self.emit_finished)

    def emit_finished(self, *args):
        if self.entry.get_text() != self.entry.default_text:
            self.emit("finished", self.entry.get_text())
            self.entry.set_text(self.entry.default_text)
        self.hide()


class InformationToolbar(gtk.Toolbar):
    def __init__(self):
        super(InformationToolbar, self).__init__()
        self.set_icon_size(gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.open_button = ob = gtk.ToolButton(gtk.STOCK_OPEN)
        ob.set_label(_("Launch this subject"))
        self.delete_button = del_ = gtk.ToolButton(gtk.STOCK_DELETE)
        del_.set_label(_("Delete this subject"))
        self.add_tag_button = add = gtk.ToolButton(gtk.STOCK_ADD)
        add.set_label(_("Add a tag"))
        self.new_tag_entry = new = NewTagTool()
        #self.pin_button = pin = supporting_widgets.Toolbar.get_toolbutton(
        #    get_icon_path("hicolor/24x24/status/pin.png"),
        #    _("Add Pin"))
        sep = gtk.SeparatorToolItem()
        for item in (del_, sep, new, add, ob):
            self.insert(item, 0)
        new.hide_all()


class InformationContainer(supporting_widgets.Pane):
    """
    . . . . . . . .  . . .
    .             .  .   .
    .    Info     .  .   . <--- Related files
    .             .  .   .
    .             .  .   .
    . . . . . . . .  . . .

    A window which holds the information pane and related pane
    """
    def __init__(self):
        super(InformationContainer, self).__init__()
        box1 = gtk.VBox()
        box2 = gtk.VBox()
        vbox = gtk.VBox()
        self.toolbar = InformationToolbar()
        self.infopane = InformationPane()
        self.tag_cloud = supporting_widgets.TagCloud()
        self.relatedpane = RelatedPane()
        scrolledwindow = gtk.ScrolledWindow()
        box2.set_border_width(10)
        box1.pack_start(self.toolbar, False, False)
        box2.pack_start(self.infopane, False, False, 4)
        box2.pack_start(self.tag_cloud, False, False, 2)
        scrolledwindow.set_shadow_type(gtk.SHADOW_IN)
        #self.relatedpane.set_size_request(230, -1)
        scrolledwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolledwindow.add(self.relatedpane)
        vbox.pack_end(scrolledwindow, True, True)
        box2.pack_end(vbox, True, True, 10)
        box1.add(box2)
        self.add(box1)
        def _launch(w):
            self.obj.launch()
        self.toolbar.open_button.connect("clicked", _launch)
        self.toolbar.delete_button.connect("clicked", self.do_delete_events_with_shared_uri)
        self.toolbar.add_tag_button.connect("clicked", self.on_add_tag_press)
        self.toolbar.new_tag_entry.connect("finished", self.do_add_tag)

    def on_add_tag_press(self, *args):
        if self.toolbar.new_tag_entry.get_property("visible"):
            self.toolbar.new_tag_entry.hide()
            self.toolbar.add_tag_button.set_stock_id(gtk.STOCK_ADD)
        else:
            self.toolbar.new_tag_entry.show()
            self.toolbar.add_tag_button.set_stock_id(gtk.STOCK_CANCEL)

    def do_add_tag(self, w, text):
        self.toolbar.add_tag_button.set_stock_id(gtk.STOCK_ADD)
        if TRACKER:
            TRACKER.add_tag_to_uri(text, self.obj.uri)
        self.set_tags(self.obj)

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
        self.set_tags(obj)
        self.show()
        self.toolbar.new_tag_entry.hide()
        self.toolbar.add_tag_button.set_stock_id(gtk.STOCK_ADD)

    def set_tags(self, obj):
        if TRACKER:
            tag_dict = {}
            tags = TRACKER.get_tag_dict_for_uri(obj.uri)
            self.tag_cloud.set_tags(tags)
        else:
            self.tag_cloud.set_text("")

    def hide_on_delete(self, widget, *args):
        super(InformationContainer, self).hide_on_delete(widget)
        self.infopane.set_inactive()
        return True

