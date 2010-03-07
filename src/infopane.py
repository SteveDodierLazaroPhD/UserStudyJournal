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
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
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
try: import gtksourceview
except ImportError: gtksourceview = None

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
     ResultType, TimeRange

from common import *
from eventgatherer import get_related_events_for_uri
from thumb import ImageView
from gio_file import GioFile


GENERIC_DISPLAY_NAME = "other"

MIMETYPEMAP = {
    GENERIC_DISPLAY_NAME : ("image", None),
    "multimedia" : ("video", "audio"),
    "text" : ("text",),
}


def get_media_type(uri):
    gfile = GioFile.create(uri)
    if not gfile:
        return GENERIC_DISPLAY_NAME
    majortype = gfile.mime_type.split("/")[0]
    for key, mimes in MIMETYPEMAP.iteritems():
        if majortype in mimes:
            return key
    if "text-x-generic" in gfile.icon_names or "text-x-script" in gfile.icon_names:
        return "text"
    return GENERIC_DISPLAY_NAME


class ContentDisplay(object):
    def set_uri(self, uri):
        pass

    def set_inactive(self):
        pass


class ScrolledDisplay(gtk.ScrolledWindow):
    """
    A scrolled window container that acts as a proxy for a child
    use type to make wrapers for your type
    """
    child_type = gtk.Widget
    def __init__(self):
        """"""
        super(ScrolledDisplay, self).__init__()
        self._child_obj = self.child_type()
        self.add(self._child_obj)
        self.set_shadow_type(gtk.SHADOW_IN)

    def set_uri(self, uri): self._child_obj.set_uri(uri)
    def set_inactive(self): self._child_obj.set_inactive()


class TextDisplay(gtksourceview.SourceView if gtksourceview
                  else gtk.TextView, ContentDisplay):
    """
    A text preview display which uses a sourceview or a textview if sourceview
    modules are not found
    """
    def __init__(self):
        """"""
        super(TextDisplay, self).__init__()
        self.textbuffer = (gtksourceview.SourceBuffer() if gtksourceview
                           else gtk.TextBuffer())
        self.set_buffer(self.textbuffer)
        self.set_editable(False)
        font  = pango.FontDescription()
        font.set_family("Monospace")
        self.modify_font(font)
        if gtksourceview:
            self.manager = gtksourceview.SourceLanguagesManager()
            self.textbuffer.set_highlight(True)

    def set_uri(self, uri):
        gfile = GioFile.create(uri)
        if gfile:
            content = gfile.get_content()
            self.textbuffer.set_text(content)
            if gtksourceview:
                lang = self.manager.get_language_from_mime_type(gfile.mime_type)
                self.textbuffer.set_language(lang)


class ImageDisplay(gtk.Image, ContentDisplay):
    """Displays an image or a icon representing the uri
    """
    def set_uri(self, uri):
        gfile = GioFile.create(uri)
        if gfile:
            if gfile.has_preview():
                pixbuf = gfile.get_thumbnail(size=SIZE_LARGE, border=3)
            else:
                pixbuf = gfile.get_icon(size=256)
            self.set_from_pixbuf(pixbuf)


class MultimediaDisplay(gtk.VBox, ContentDisplay):
    """Displays a video or audio object using gstreamer
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
        self.player.set_state(gst.STATE_PLAYING)
        self.playbutton.gtkimage.set_from_stock(gtk.STOCK_MEDIA_PAUSE, 2)
        self.playing = True

    def set_paused(self):
        self.player.set_state(gst.STATE_PAUSED)
        self.playbutton.gtkimage.set_from_stock(gtk.STOCK_MEDIA_PLAY, 2)
        self.playing = False

    def set_uri(self, uri):
        self.player.set_state(gst.STATE_NULL)
        self.player.set_property("uri", uri)
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


class InformationPane(gtk.Frame):
    """
    . . . . . . . .
    .             .
    .    Info     .
    .             .
    .             .
    . . . . . . . .
    """
    displays = {
        GENERIC_DISPLAY_NAME : ImageDisplay,
        "multimedia" : MultimediaDisplay if gst else ImageDisplay,
        "text" : type("TextScrolledWindow", (ScrolledDisplay,),
                      {"child_type" : TextDisplay}),
    }
    uri = None
    def __init__(self):
        """"""
        super(InformationPane, self).__init__()
        vbox = gtk.VBox()
        buttonhbox = gtk.HBox()
        self.box = gtk.Frame()
        self.label = gtk.Label()
        self.pathlabel = gtk.Label()
        labelvbox = gtk.VBox()
        labelvbox.pack_start(self.label)
        labelvbox.pack_end(self.pathlabel)
        self.openbutton = gtk.Button(stock=gtk.STOCK_OPEN)
        self.displays = self.displays.copy()
        self.set_shadow_type(gtk.SHADOW_NONE)
        self.set_label_widget(labelvbox)
        self.box.set_shadow_type(gtk.SHADOW_NONE)
        buttonhbox.pack_end(self.openbutton, False, False, 5)
        buttonhbox.set_border_width(5)
        vbox.pack_start(self.box, True, True)
        vbox.pack_end(buttonhbox, False, False)
        self.add(vbox)
        self.set_label_align(0.5, 0.5)
        self.label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self.pathlabel.set_size_request(300, -1)
        self.pathlabel.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        def _launch_uri(w):
            gfile = GioFile.create(self.uri)
            if gfile: gfile.launch()
        self.openbutton.connect("clicked", _launch_uri)

    def set_displaytype(self, uri):
        media_type = get_media_type(uri)
        display_widget = self.displays[media_type]
        if isinstance(display_widget, type):
            display_widget = self.displays[media_type] = display_widget()
        if display_widget.parent != self.box:
            child = self.box.get_child()
            if child:
                self.box.remove(child)
                child.set_inactive()
            self.box.add(display_widget)
        display_widget.set_uri(uri)
        self.show_all()

    def set_uri(self, uri):
        """
        :param uri:
        """
        self.uri = uri
        self.set_displaytype(uri)
        filename = os.path.basename(uri).replace("&", "&amp;").replace("%20", " ")
        if not filename:
            filename = uri.replace("&", "&amp;").replace("%20", " ")
        self.label.set_markup("<span size='13336'>" + filename + "</span>")
        self.pathlabel.set_markup("<span color='#979797'>" + uri + "</span>")

    def set_inactive(self):
        display = self.box.get_child()
        if display: display.set_inactive()


class RelatedPane(ImageView):
    """
    ...............
    .             . <--- Related files
    ...............
    """
    def __init__(self):
        super(RelatedPane, self).__init__()
        self.set_orientation(gtk.ORIENTATION_HORIZONTAL)


class InformationWindow(gtk.Window):
    """
    . . . . . . . .
    .             .
    .    Info     .
    .             .
    .             .
    . . . . . . . .
    ...............
    .             . <--- Related files
    ...............
    """
    def __init__(self):
        super(InformationWindow, self).__init__()
        box = gtk.HBox()
        vbox = gtk.VBox()
        relatedlabel = gtk.Label(_("Related Items"))
        self.infopane = InformationPane()
        self.relatedpane = RelatedPane()
        scrolledwindow = gtk.ScrolledWindow()
        box.set_border_width(10)
        box.pack_start(self.infopane, True, True, 10)
        scrolledwindow.set_shadow_type(gtk.SHADOW_IN)
        self.relatedpane.set_size_request(130, -1)
        scrolledwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        scrolledwindow.add(self.relatedpane)
        vbox.pack_start(relatedlabel, False, False)
        vbox.pack_end(scrolledwindow, True, True)
        box.pack_end(vbox, False, False, 10)
        self.add(box)
        self.set_size_request(600, 400)
        self.connect("delete-event", self._hide_on_delete)

    def _hide_on_delete(self, widget, event):
        widget.hide()
        self.infopane.set_inactive()
        return True

    def set_uri(self, uri):
        """
        :param uri: a uri which is set as the window's current focus
        """
        def _callback(events):
            self.relatedpane.set_model_from_list(events)
        get_related_events_for_uri(uri, _callback)
        self.infopane.set_uri(uri)
        self.show_all()


InformationWindow = InformationWindow()
