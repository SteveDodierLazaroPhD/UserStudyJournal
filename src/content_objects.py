# -.- coding: utf-8 -.-
#
# content_objects.py
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
#  Holds content objects which are something like the trackinfo objects used in
#  banshee. All of the display widgets should use these content objects instead
#  of events or uris.
#


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

# Defines some additional icon sizes
SIZE_THUMBVIEW = (92, 72)
SIZE_TIMELINEVIEW = (32, 24)

# Caches desktop files
DESKTOP_FILES = {}


def choose_content_object(event):
    """
    :param event: a zeitgeist.datamodel.Event

    :returns a instance of the best possible ContentObject subclass or None if
    no correct Content Object was found or if that the correct Content object
    rejected the given event
    """
    for obj in CONTENT_OBJECTS:
        instance = obj.use_class(event)
        if instance: return instance

    if event.subjects[0].uri.startswith("file://"):
        return FileContentObject.create(event)
    return GenericContentObject.create(event)




class ContentObject(object):
    """
    Defines the required interface of a Content object. This is a abstract class.
    """
    # Paths where .desktop files are stored.
    desktop_file_paths = ["/usr/share/applications/", "/usr/local/share/applications/"]

    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if False:
            return cls.create(event)
        return False

    def __init__(self, event):
        self._event = event

    @classmethod
    def create(cls, event):
        """
        :param event: a zeitgeist event
        :returns: a ContentObject instance or None
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

    # Thumbnail methods
    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        """:returns: a pixbuf representing the content"""
        thumb = None
        return thumb

    @property
    def thumbview_icon(self):
        """:returns: tuple with containing a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        return None, False

    @property
    def timelineview_icon(self):
        """:returns: tuple with containing a sized pixbuf for the timeline and a ispreview bool describing if it is a preview"""
        return None, False

    @property
    def thumbnail(self):
        return self.get_thumbnail()

    def has_preview(self):
        """
        :returns: True if this content type can show a preview thumbnail instead of a infomation representation else False
        """
        return False

    def thumb_icon_allowed(self):
        """:returns: True if the content type can use a preview instead of a icon else False"""
        return False

    # Icon methods
    def get_icon(self, size=24, can_thumb=False, border=0):
        """
        :Returns: a pixbuf representing this event's icon
        """
        icon = None
        return icon

    @property
    def icon(self):
        return self.get_icon()

    @property
    def emblems(self):
        """
        :returns: a pixbuf array where each element is a emblem with some meaning to this object
        """
        emblem_collection = []
        if not self.has_preview:
            emblem_collection.append(self.icon)
        return emblem_collection

    # utility
    def launch(self):
        """
        Launches a event
        """
        pass

    def get_monitor(self):
        raise NotImplementedError()

    # Used for timeline
    phases = None

    # Thumbview and Timelineview methods
    @property
    def type_color_representation(self):
        """
        Uses the tango color pallet to find a color representing the content type

        :returns: a rgb tuple
        """
        if not hasattr(self, "_type_color_representation"):
            self._type_color_representation = common.get_file_color(self.event.subjects[0].interpretation, self.event.subjects[0].mimetype)
        return self._type_color_representation

    @property
    def text(self):
        if not hasattr(self, "__text"):
            self.__text = str(self.event.subjects[0].text)
        return self.__text

    @property
    def timelineview_text(self):
        """
        :returns: a string of text markup used in timeline widget and elsewhere
        """
        if not hasattr(self, "__timelineview_text"):
            text = common.get_event_text(self.event)
            interpretation = common.get_event_interpretation(self.event)
            t = (common.FILETYPESNAMES[interpretation] if
                 interpretation in common.FILETYPESNAMES.keys() else "Unknown")
            self.__timelineview_text = (t + "\n" + text).replace("%", "%%")
        return self.__timelineview_text


    @property
    def thumbview_text(self):
        """
        :returns: a string of text used in thumb widget and elsewhere
        """
        if not hasattr(self, "_thumbview_text"):
            self._thumbview_text = self.event.subjects[0].text.replace("&", "&amp;")
        return self._thumbview_text

    def _get_desktop_file(self):
        """
        Finds a desktop file for a actor
        """
        if hasattr(self, "_desktop_file"): return self._desktop_file
        if self.event.actor in DESKTOP_FILES:
            self._desktop_file = DESKTOP_FILES[self.event.actor]
            return self._desktop_file

        path = None
        for desktop_path in self.desktop_file_paths:
            if os.path.exists(self.event.actor.replace("application://", desktop_path)):
                path = self.event.actor.replace("application://", desktop_path)
                break
        if not path:
            return None
        self._desktop_file = DesktopEntry.DesktopEntry(path)
        DESKTOP_FILES[self.event.actor] = self._desktop_file
        return self._desktop_file

    def get_actor_pixbuf(self, size):
        """
        Finds a icon for a actor

        :returns: a pixbuf
        """
        if not hasattr(self, "_actor_pixbuf"):
            desktop = self._get_desktop_file()
            if not desktop:
                self._actor_pixbuf = None
            else:
                name = desktop.getIcon()
                self._actor_pixbuf = common.get_icon_for_name(name, size)
        return self._actor_pixbuf

    def get_content(self):
        """
        :returns: a string representing this content objects content
        """
        return ""


class GenericContentObject(ContentObject):
    """
    Used to display Generic content which does not have a better suited content object
    """
    @classmethod
    def use_class(cls, event):
        return False

    empty_timelineview_pb = gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(
            "hicolor/scalable/apps/gnome-activity-journal.svg"), SIZE_TIMELINEVIEW[0], SIZE_TIMELINEVIEW[1])
    empty_24_pb = gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(
            "hicolor/scalable/apps/gnome-activity-journal.svg"), 24, 24)

    empty_16_pb = gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path(
            "hicolor/scalable/apps/gnome-activity-journal.svg"), 16, 16)

    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        return self.get_icon(size[0])

    def get_icon(self, size=24, can_thumb=False, border=0):
        icon = common.get_icon_for_name(self.mime_type.replace("/", "-"), size)
        if icon:
            return icon
        icon = self.get_actor_pixbuf(size)
        if icon:
            return icon
        if size == 24: return self.empty_24_pb
        if size == 16: return self.empty_16_pb
        icon = self.get_actor_pixbuf(size)
        return icon

    @property
    def thumbview_icon(self):
        """Special method which returns a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        return None, False

    @property
    def timelineview_icon(self):
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

    def launch(self):
        pass



class FileContentObject(GioFile, ContentObject):
    """
    Content object used to display events with subjects which are files
    """
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.subjects[0].uri.startswith("file://"):
            return cls.create(event)
        return False

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
        return GioFile.get_thumbnail(self, size, border)

    @property
    def thumbview_icon(self):
        """Special method which returns a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        if not hasattr(self, "__thumbpb"):
            self.__thumbpb, self.__isthumb = common.PIXBUFCACHE.get_pixbuf_from_uri(self.uri, SIZE_LARGE, iconscale=0.1875, w=SIZE_THUMBVIEW[0], h=SIZE_THUMBVIEW[1])
        return self.__thumbpb, self.__isthumb

    @property
    def timelineview_icon(self):
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
    """
    Displays page visits
    """
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.subjects[0].uri.startswith("http://"):
            return cls.create(event)
        return False

    def __init__(self, event):
        super(WebContentObject, self).__init__(event)

    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        return self.get_icon(size[0])

    @property
    def thumbview_icon(self):
        #return self.get_icon(SIZE_LARGE[0]*0.1875), False
        return None, False

    @property
    def timelineview_icon(self):
        return self.get_icon(SIZE_TIMELINEVIEW[0]), False

    def get_icon(self, size=24, can_thumb=False, border=0):
        size = int(size)
        icon = common.get_icon_for_name("text-html", size)
        if not icon:
            icon = self.get_actor_pixbuf(size)
        return icon

    def launch(self):
        pass

    @property
    def timelineview_text(self):
        if not hasattr(self, "__timelineview_text"):
            t1 = self.event.subjects[0].uri
            t2 = self.event.subjects[0].text
            self.__timelineview_text = (t1 + "\n" + t2).replace("%", "%%")
        return self.__timelineview_text

    @property
    def thumbview_text(self):
        if not hasattr(self, "_thumbview_text"):
            interpretation = common.get_event_interpretation(self.event)
            t = (common.FILETYPESNAMES[interpretation] if
                 interpretation in common.FILETYPESNAMES.keys() else "Unknown")
            self._thumbview_text = t + "\n" + self.event.subjects[0].text.replace("&", "&amp;") + \
                "\n<small><small>" + self.event.subjects[0].uri.replace("&", "&amp;") + "</small></small>"
        return self._thumbview_text

    @property
    def emblems(self):
        emblem_collection = []
        emblem_collection.append(self.get_icon(16))
        emblem_collection.append(None)
        emblem_collection.append(None)
        emblem_collection.append(self.get_actor_pixbuf(16))
        return emblem_collection


class BaseContentType(ContentObject):
    """
    Formatting is done where

    event is the event
    content_obj is self
    interpretation is the event interpretation
    subject_interpretation is the first subjects interpretation
    """
    icon_name = ""
    icon_uri = ""
    icon_is_thumbnail = False

    text = ""
    timelineview_text = ""
    thumbview_text = ""

    def __init__(self, event):
        super(BaseContentType, self).__init__(event)
        # String formatting
        for name in ("text", "timelineview_text", "thumbview_text"):
            val = getattr(self, name)
            setattr(self, name, val.format(event=self.event, content_obj=self, interpretation=Interpretation[self.event.interpretation],
                                           subject_interpretation=Interpretation[self.event.subjects[0].interpretation]))

    def get_icon(self, size = 24, can_thumb = False, border = 0):
        if self.icon_uri:
            return common.get_icon_for_uri(self.icon_uri, size)
        if self.icon_name:
            return common.get_icon_for_name(self.icon_name, size)

    @property
    def thumbview_icon(self):
        """Special method which returns a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        if not hasattr(self, "__thumbpb"):
            if self.icon_is_thumbnail and self.icon_uri:
                self.__thumbpb, self.__isthumb = common.PIXBUFCACHE.get_pixbuf_from_uri(
                    self.icon_uri, SIZE_LARGE, iconscale=0.1875, w=SIZE_THUMBVIEW[0], h=SIZE_THUMBVIEW[1])
            else:
                self.__thumbpb = self.get_icon(SIZE_THUMBVIEW[0]*0.1875)
                self.__isthumb = False
        return self.__thumbpb, self.icon_is_thumbnail

    @property
    def timelineview_icon(self):
        """Special method which returns a sized pixbuf for the timeline and a ispreview bool describing if it is a preview"""
        if not hasattr(self, "__timelinepb"):
            icon = self.get_icon(SIZE_TIMELINEVIEW[0])
            if not icon:
                icon = GenericContentObject.empty_timelineview_pb
            self.__timelinepb = icon
        return self.__timelinepb, False

    @property
    def emblems(self):
        emblem_collection = []
        #emblem_collection.append(self.get_icon(16))
        emblem_collection.append(None)
        emblem_collection.append(None)
        emblem_collection.append(self.get_actor_pixbuf(16))
        return emblem_collection

    def launch(self):
        pass


class BzrContentObject(BaseContentType):
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.actor == "application://bzr.desktop":
            return cls.create(event)
        return False

    icon_uri = "/usr/share/pixmaps/bzr-icon-64.png"
    icon_is_thumbnail = False

    text = "{event.subjects[0].text}"
    timelineview_text = "BZR\n{event.subjects[0].text}"
    thumbview_text = "BZR\n{event.subjects[0].text}"


class TelepathyContentObject(BaseContentType):
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.actor == "application://telepathy.desktop":
            print "Found"
            return cls.create(event)
        return False

    icon_is_thumbnail = False

    text = "{event.subjects[0].text}"
    timelineview_text = "{subject_interpretation.display_name}\n{event.subjects[0].text}"
    thumbview_text = "{subject_interpretation.display_name}\n{event.subjects[0].text}"

# Content object list used by the section function
CONTENT_OBJECTS = (BzrContentObject, WebContentObject)
