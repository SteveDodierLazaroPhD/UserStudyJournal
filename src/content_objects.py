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

import gio
import gtk
import os
from xdg import DesktopEntry
import xml.dom.minidom as dom

from urlparse import urlparse
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation

from config import get_icon_path, get_data_path
from gio_file import GioFile, THUMBS, ICONS, SIZE_LARGE, SIZE_NORMAL
import common



SIZE_THUMBVIEW = (92, 72)
SIZE_TIMELINEVIEW = (32, 24)
DESKTOP_FILES = {}

def choose_content_object(event):
    #Payload selection here
    #if event.payload:
    #    print event.payload
    if event.subjects[0].uri.startswith("file://"):
        return FileContentObject.create(event)
    elif event.subjects[0].uri.startswith("http://"):
        return WebContentObject.create(event)
    else:
        return GenericContentObject.create(event)

class ContentObject(object):
    """
    Defines the required interface of a Content wrapper that displays all the methods
    a wrapper implements
    """
    desktop_file_path = "/usr/share/applications/"

    def __init__(self, event):
        self._event = event

    @classmethod
    def create(cls, event):
        """
        Can return None
        """
        return cls(event)

    @property
    def event(self):
        return self._event

    @event.setter
    def event(self, value):
        self._event = value

    @property
    def uri(self):
        return self.event.subjects[0].uri

    @property
    def mime_type(self):
        return self.event.subjects[0].mimetype

    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        """Returns a pixbuf representing the content"""
        if size == SIZE_THUMBVIEW:
            return self.__get_thumbview_icon()
        elif size == SIZE_TIMELINEVIEW:
            return self.__get_timelineview_icon()
        thumb = None
        return thumb

    def __get_thumbview_icon(self):
        """Special method which returns a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        return None, False

    def __get_timelineview_icon(self):
        """Special method which returns a sized pixbuf for the timeline and a ispreview bool describing if it is a preview"""
        return None, False

    @property
    def thumbnail(self):
        return self.get_thumbnail()

    def get_monitor(self):
        raise NotImplementedError

    def get_icon(self, size=24, can_thumb=False, border=0):
        """
        Returns a icon representing this event
        """
        icon = None
        return icon

    @property
    def icon(self):
        return self.get_icon()

    def launch(self):
        """
        Launches a event
        """
        pass

    def has_preview(self):
        """
        Returns true if this content type can show a preview thumbnail instead of a infomation representation
        """
        return False

    def thumb_icon_allowed(self):
        """True if the content type can use a preview instead of a icon"""
        return False

    @property
    def emblems(self):
        """
        Returns emblem pixbufs for the content
        """
        emblem_collection = []
        if not self.has_preview:
            emblem_collection.append(self.icon)
        return emblem_collection

    # Used for timeline
    phases = None

    @property
    def type_color_representation(self):
        """
        Uses the tango color pallet to find a color representing the content type
        """
        if not hasattr(self, "_type_color_representation"):
            self._type_color_representation = common.get_file_color(self.event.subjects[0].interpretation, self.event.subjects[0].mimetype)
        return self._type_color_representation


    def get_pango_subject_text(self):
        """
        Returns the text markup used in timeline widget and elsewhere
        """
        if not hasattr(self, "__pretty_subject_text"):
            text = common.get_event_text(self.event)
            interpretation = common.get_event_interpretation(self.event)
            t = (common.FILETYPESNAMES[interpretation] if
                 interpretation in common.FILETYPESNAMES.keys() else "Unknown")
            text = text.replace("%", "%%")
            t1 = "<span color='!color!'><b>" + t + "</b></span>"
            t2 = "<span color='!color!'>" + text + "</span> "
            self.__pretty_subject_text = (str(t1) + "\n" + str(t2) + "").replace("&", "&amp;").replace("!color!", "%s")
        return self.__pretty_subject_text


    def _get_desktop_file(self):
        """
        Finds a desktop file for a actor
        """
        if hasattr(self, "_desktop_file"): return self._desktop_file
        if self.event.actor in DESKTOP_FILES:
            self._desktop_file = DESKTOP_FILES[self.event.actor]
            return self._desktop_file
        path = self.event.actor.replace("application://", self.desktop_file_path)
        if not os.path.exists(path):
            return None
        self._desktop_file = DesktopEntry.DesktopEntry(path)
        DESKTOP_FILES[self.event.actor] = self._desktop_file
        return self._desktop_file

    def get_actor_pixbuf(self, size):
        """
        Finds a icon for a actor
        """
        if not hasattr(self, "_actor_pixbuf"):
            desktop = self._get_desktop_file()
            if not desktop:
                self._actor_pixbuf = None
            else:
                name = desktop.getIcon()
                self._actor_pixbuf = common.get_icon_for_name(name, size)
        return self._actor_pixbuf

    @property
    def thumbview_text(self):
        if not hasattr(self, "_thumbview_text"):
            self._thumbview_text = self.event.subjects[0].text.replace("&", "&amp;")
        return self._thumbview_text


class GenericContentObject(ContentObject):
    """
    Defines the required interface of a Content wrapper that displays all the methods
    a wrapper implements
    """
    empty_thumbview_pb = gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(
            "hicolor/scalable/apps/gnome-activity-journal.svg"), SIZE_LARGE[0]*0.1875, SIZE_LARGE[1]*0.1875)
    empty_timelineview_pb = gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(
            "hicolor/scalable/apps/gnome-activity-journal.svg"), SIZE_TIMELINEVIEW[0], SIZE_TIMELINEVIEW[1])
    empty_large_pb = gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(
            "hicolor/scalable/apps/gnome-activity-journal.svg"), SIZE_LARGE[0], SIZE_LARGE[1])

    empty_24_pb = gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(
            "hicolor/scalable/apps/gnome-activity-journal.svg"), 24, 24)

    empty_16_pb = gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(
            "hicolor/scalable/apps/gnome-activity-journal.svg"), 16, 16)

    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        if size == SIZE_THUMBVIEW:
            return self.__get_thumbview_icon()
        elif size == SIZE_TIMELINEVIEW:
            return self.__get_timelineview_icon()
        return self.get_icon(size[0])

    def get_monitor(self):
        raise NotImplementedError

    def get_icon(self, size=24, can_thumb=False, border=0):
        if size == 24: return self.empty_24_pb
        if size == 16: return self.empty_16_pb
        icon = self.get_actor_pixbuf(size)
        return icon

    def launch(self):
        pass

    def __get_thumbview_icon(self):
        """Special method which returns a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        #if hasattr(self, "__thumbpb"):
        #    return self.__thumbpb, self.__isthumb
        #icon = self.get_icon(SIZE_LARGE[0]*0.1875)
        #if icon:
        #    self.__thumbpb = icon
        #    self.__isthumb = False
        #    return icon, False
        #return self.empty_thumbview_pb, False
        return None, False

    def __get_timelineview_icon(self):
        """Special method which returns a sized pixbuf for the timeline and a ispreview bool describing if it is a preview"""
        if hasattr(self, "__timelinepb"):
            return self.__timelinepb, self.__timeline_isthumb
        icon = self.get_icon(SIZE_TIMELINEVIEW[0])
        if icon:
            self.__timelinepb = icon
            self.__timeline_isthumb = False
            return self.__timelinepb, self.__timeline_isthumb
        return self.empty_timelineview_pb, False

    @property
    def thumbview_text(self):
        if not hasattr(self, "_thumbview_text"):
            interpretation = common.get_event_interpretation(self.event)
            t = (common.FILETYPESNAMES[interpretation] if
                 interpretation in common.FILETYPESNAMES.keys() else "Unknown")
            self._thumbview_text = t + "\n" + self.event.subjects[0].text.replace("&", "&amp;")
        return self._thumbview_text

    @property
    def emblems(self):
        emblem_collection = []
        emblem_collection.append(self.get_icon(16))
        emblem_collection.append(None)
        emblem_collection.append(None)
        emblem_collection.append(self.get_actor_pixbuf(16))
        return emblem_collection

class FileContentObject(GioFile, ContentObject):

    def __init__(self, event):
        ContentObject.__init__(self, event)
        uri = event.subjects[0].uri
        return GioFile.__init__(self, uri)

    @classmethod
    def create(cls, event):
        try:
            return cls(event)
        except gio.Error:
            return None

    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        if size == SIZE_THUMBVIEW:
            return self.__get_thumbview_icon()
        elif size == SIZE_TIMELINEVIEW:
            return self.__get_timelineview_icon()
        return GioFile.get_thumbnail(self, size, border)

    def __get_thumbview_icon(self):
        """Special method which returns a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        if not hasattr(self, "__thumbpb"):
            self.__thumbpb, self.__isthumb = common.PIXBUFCACHE.get_pixbuf_from_uri(self.uri, SIZE_LARGE, iconscale=0.1875, w=SIZE_THUMBVIEW[0], h=SIZE_THUMBVIEW[1])
        return self.__thumbpb, self.__isthumb

    def __get_timelineview_icon(self):
        """Special method which returns a sized pixbuf for the timeline and a ispreview bool describing if it is a preview"""
        if not hasattr(self, "__timelinepb"):
            usethumb = (True if common.get_event_interpretation(self.event)
                        in common.MEDIAINTERPRETATIONS else False)
            thumb = False
            if common.PIXBUFCACHE.has_key(self.uri) and usethumb:
                pixbuf, thumb = common.PIXBUFCACHE[self.uri]
                pixbuf = pixbuf.scale_simple(32, 24, gtk.gdk.INTERP_TILES)
            else:
                pixbuf = common.get_event_icon(self.event, 24)
            if common.PIXBUFCACHE.has_key(self.uri) and usethumb and pixbuf != common.PIXBUFCACHE[self.uri][0]:
                pixbuf, thumb = common.PIXBUFCACHE[self.uri]
                pixbuf = pixbuf.scale_simple(32, 24, gtk.gdk.INTERP_TILES)
            if not pixbuf: pixbuf = GenericContentObject.empty_timelineview_pb
            self.__timelinepb = pixbuf
            self.__timeline_isthumb = usethumb&thumb
        return self.__timelinepb, self.__timeline_isthumb

    @property
    def emblems(self):
        emblem_collection = []
        emblem_collection.append(self.get_icon(16))
        emblem_collection.append(None)
        emblem_collection.append(None)
        emblem_collection.append(self.get_actor_pixbuf(16))
        return emblem_collection


class WebContentObject(ContentObject):


    def __init__(self, event):
        super(WebContentObject, self).__init__(event)

    @classmethod
    def create(cls, event):
        """
        Can return None
        """
        return cls(event)

    @property
    def mime_type(self):
        return self.event.subjects[0].mimetype

    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        if size == SIZE_THUMBVIEW:
            return self.__get_thumbview_icon()
        elif size == SIZE_TIMELINEVIEW:
            return self.__get_timelineview_icon()
        return self.get_icon(size[0])

    def __get_thumbview_icon(self):
        return self.get_icon(SIZE_THUMBVIEW[0]), False

    def __get_timelineview_icon(self):
        return self.get_icon(SIZE_LARGE[0]*0.1875), False

    def get_monitor(self):
        raise NotImplementedError()

    def get_icon(self, size=24, can_thumb=False, border=0):
        size = int(size)
        icon = common.get_icon_for_name(self.mime_type, size)
        if not icon:
            icon = self.get_actor_pixbuf(size)
        return icon

    def launch(self):
        pass

    def get_pango_subject_text(self):
        if not hasattr(self, "__pretty_subject_text"):
            t1 = self.event.subjects[0].uri
            t2 = self.event.subjects[0].text
            t1 = t1.replace("%", "%%")
            t2 = t2.replace("%", "%%")
            interpretation = common.get_event_interpretation(self.event)
            t1 = "<span color='!color!'><b>" + t1 + "</b></span>"
            t2 = "<span color='!color!'>" + t2 + "</span> "
            self.__pretty_subject_text = (str(t1) + "\n" + str(t2) + "").replace("&", "&amp;").replace("!color!", "%s")
        return self.__pretty_subject_text


class EventGeneratedContentType(ContentObject):
    """
    Takes markup in a events payload and builds a event around it

    <Content name="Web history">
    <thumbnail uri="file:///home/tehk/.cache/somethumb.png"/>
    <!-- ${application} and ${subject_uri} are replaced by gaj with values from the event -->
    <launcher command="${application} ${subject_uri}"/>
    </Content>

    Disabled until we write a specification for the payload markup
    """
    def __init__(self, event):
        super(self, EventGeneratedContentType).__init__(event)

        self._header = common.get_event_interpretation(self.event)
        self._body = self.event.subjects[0].text
        self._thumb_uri = ""
        self._icon_uri = ""
        self._command = ""

    def __process_launcher(self, node):
        self._command = node.getAttribute("command")

    def __process_thumb(self, node):
        node = dom.Element()
        self._thumb_uri = node.getAttribute("uri")
        if not self._icon_uri:
            self._icon_uri = node.getAttribute("uri")

    def __process_header(self, node):
        text_node = node.childNodes[0]
        self._header = text_node.nodeValue()

    def __process_body(self, node):
        text_node = node.childNodes[0]
        self._body = text_node.nodeValue()

    def __process_icon(self, node):
        self._icon_uri = node.getAttribute("uri")

    def __process_node(node):
        node_func_map = {"thumbnail" : self.__process_thumb,
                         "header" : self.__process_header,
                         "body" : self.__process_body,
                         "icon" : self.__process_icon,
                         "launcher" : self.__process_launcher,
                         }
        if not node.localName:
            if node_func_map.has_key(node.localName):
                node_func_map[node.localName](node)

    def __process_payload(self, payload):
        payload_string = payload

        document = dom.parseString(payload_string)
        content = document.childNodes[0]
        for node in content.childNodes:
            self.__process_node(node)


    def get_pango_subject_text(self):
        if not hasattr(self, "__pretty_subject_text"):
            t1 = self._header
            t2 = self._body
            t1 = t1.replace("%", "%%")
            t2 = t2.replace("%", "%%")
            interpretation = common.get_event_interpretation(self.event)
            t1 = "<span color='!color!'><b>" + t1 + "</b></span>"
            t2 = "<span color='!color!'>" + t2 + "</span> "
            self.__pretty_subject_text = (str(t1) + "\n" + str(t2) + "").replace("&", "&amp;").replace("!color!", "%s")
        return self.__pretty_subject_text

    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        if size == SIZE_THUMBVIEW:
            return self.__get_thumbview_icon()
        elif size == SIZE_TIMELINEVIEW:
            return self.__get_timelineview_icon()
        return self.get_icon(size[0])

    def __get_thumbview_icon(self):
        return self.get_icon(SIZE_THUMBVIEW[0]), False

    def __get_timelineview_icon(self):
        return self.get_icon(SIZE_LARGE[0]*0.1875), False

    def get_monitor(self):
        raise NotImplementedError

    def get_icon(self, size=24, can_thumb=False, border=0):
        if ICONS[(size, size)].has_key(self.uri):
            return ICONS[(size, size)][self.uri]
        size = int(size)
        #icon = ICONS[(size, size)][self.uri] = gtk.gdk.pixbuf_new_from_file_at_size
        icon = self.get_actor_pixbuf(size)
        return icon




