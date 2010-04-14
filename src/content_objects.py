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
import glib
import gtk
import os
from xdg import DesktopEntry
import xml.dom.minidom as dom

from urlparse import urlparse
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation

from config import get_icon_path, get_data_path
from gio_file import GioFile, THUMBS, ICONS, SIZE_LARGE, SIZE_NORMAL
import common
import sources

# Defines some additional icon sizes
SIZE_THUMBVIEW = (92, 72)
SIZE_TIMELINEVIEW = (32, 24)

PLACEHOLDER_PIXBUFFS = {
    24 : gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path("hicolor/scalable/apps/gnome-activity-journal.svg"), 24, 24),
    16 : gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path("hicolor/scalable/apps/gnome-activity-journal.svg"), 16, 16)
    }


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
        """ Used by the content object chooser to check if the content object will work for the event

        :param event: The event to test
        :returns: a object instance or False if this Content Object is not correct for this item
        """
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

    #@event.setter
    #def event(self, value):
    #    self._event = value

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
    def get_icon(self, size=24, *args, **kwargs):
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
        if not hasattr(self, "__emblem_collection"):
            self.__emblem_collection = []
            self.__emblem_collection.append(self.get_icon(16))
            self.__emblem_collection.append(None)
            self.__emblem_collection.append(None)
            self.__emblem_collection.append(self.get_actor_pixbuf(16))
        return self.__emblem_collection

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
            if not pixbuf: pixbuf = PLACEHOLDER_PIXBUFFS[24]
            self.__timelinepb = pixbuf
            self.__timeline_isthumb = usethumb&thumb
        return self.__timelinepb, self.__timeline_isthumb


class BaseContentType(ContentObject):
    """

    A Base content type which has 6 fields which define the automated content
    type creation. The string fields are ran into string format where formatting
    is done. The keywords are as follows:

    event is the event
    content_obj is self
    interpretation is the event interpretation
    subject_interpretation is the first subjects interpretation
    source = the sources.SUPPORTED_SOURCES source for the interpretation

    if icon_name is equal to $ACTOR then the actor icon is used
    if icon_name is equal to $MIME then the MIME icon is used
    """

    # fields which subclasses can modify
    icon_name = ""
    icon_uri = ""
    icon_is_thumbnail = False

    text = ""
    timelineview_text = ""
    thumbview_text = ""

    def __init__(self, event):
        super(BaseContentType, self).__init__(event)
        # String formatting
        wrds = {
            "content_obj" : self,
            "event" : event
        }
        try: wrds["interpretation"] = Interpretation[event.interpretation]
        except KeyError: wrds["interpretation"] = Interpretation.OPEN_EVENT
        try: wrds["subject_interpretation"] = Interpretation[event.subjects[0].interpretation]
        except KeyError: wrds["subject_interpretation"] = Interpretation.UNKNOWN
        try:
            wrds["source"] = sources.SUPPORTED_SOURCES[self.event.subjects[0].interpretation]
        except:
            wrds["source"] = sources.SUPPORTED_SOURCES[Interpretation.UNKNOWN.uri]
        for name in ("text", "timelineview_text", "thumbview_text"):
            val = getattr(self, name)
            setattr(self, name, val.format(**wrds))

    def get_icon(self, size=24, *args, **kwargs):
        icon = False
        try:
            while not icon:
                if "$MIME" in self.icon_name:
                    icon = common.get_icon_for_name(self.mime_type.replace("/", "-"), size)
                    if icon != None: return icon
                if "$ACTOR" in self.icon_name:
                    icon = self.get_actor_pixbuf(size)
                if self.icon_uri:
                    icon = common.get_icon_for_uri(self.icon_uri, size)
                elif self.icon_name and self.icon_name not in ("$MIME", "$ACTOR"):
                    icon = common.get_icon_for_name(self.icon_name, size)
                break
        except glib.GError:
            if PLACEHOLDER_PIXBUFFS.has_key(size): return PLACEHOLDER_PIXBUFFS[size]
        return icon

    @property
    def thumbview_icon(self):
        """Special method which returns a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        if not hasattr(self, "__thumbpb"):
            if self.icon_is_thumbnail and self.icon_uri:
                self.__thumbpb, self.__isthumb = common.PIXBUFCACHE.get_pixbuf_from_uri(
                    self.icon_uri, SIZE_LARGE, iconscale=0.1875, w=SIZE_THUMBVIEW[0], h=SIZE_THUMBVIEW[1])
            else:
                self.__thumbpb = None
                self.__isthumb = False
        return self.__thumbpb, self.icon_is_thumbnail

    @property
    def timelineview_icon(self):
        """Special method which returns a sized pixbuf for the timeline and a ispreview bool describing if it is a preview"""
        if not hasattr(self, "__timelinepb"):
            icon = self.get_icon(SIZE_TIMELINEVIEW[1])
            if not icon:
                icon = PLACEHOLDER_PIXBUFFS[24]
            self.__timelinepb = icon
        return self.__timelinepb, False

    @property
    def emblems(self):
        if not hasattr(self, "__emblem_collection"):
            self.__emblem_collection = []
            if (not self.icon_is_thumbnail) and self.icon_name != "$ACTOR":
                self.__emblem_collection.append(self.get_icon(16))
            else:
                self.__emblem_collection.append(None)
            self.__emblem_collection.append(None)
            self.__emblem_collection.append(None)
            self.__emblem_collection.append(self.get_actor_pixbuf(16))
        return self.__emblem_collection

    def launch(self):
        pass


class GenericContentObject(BaseContentType):
    """
    Used when no other content type would fit
    """

    icon_is_thumbnail = False
    icon_name = "$MIME $ACTOR"
    text = "{event.subjects[0].text}"
    timelineview_text = "{subject_interpretation.display_name}\n{event.subjects[0].uri}"
    thumbview_text = "{subject_interpretation.display_name}\n{event.subjects[0].text}"

    def get_icon(self, size=24, *args, **kwargs):
        icon = common.get_icon_for_name(self.mime_type.replace("/", "-"), size)
        if icon:
            return icon
        icon = self.get_actor_pixbuf(size)
        if icon:
            return icon
        if PLACEHOLDER_PIXBUFFS.has_key(size): return PLACEHOLDER_PIXBUFFS[size]
        icon = self.get_actor_pixbuf(size)
        return icon


class BzrContentObject(BaseContentType):
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.actor == "application://bzr.desktop":
            return cls.create(event)
        return False

    #icon_uri = "/usr/share/pixmaps/bzr-icon-64.png"
    icon_name = "bzr-icon-64"
    icon_is_thumbnail = False

    text = "{event.subjects[0].text}"
    timelineview_text = "BZR\n{event.subjects[0].text}"
    thumbview_text = "BZR\n{event.subjects[0].text}"


class IMContentObject(BaseContentType):
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.subjects[0].interpretation == Interpretation.IM_MESSAGE.uri:
            return cls.create(event)
        return False

    icon_name = "empathy"
    icon_is_thumbnail = False
    text = _("{source._desc_sing} with {event.subjects[0].text}")
    timelineview_text = _("{source._desc_sing} with {event.subjects[0].text}\n{event.subjects[0].uri}")
    thumbview_text = _("{source._desc_sing} with {event.subjects[0].text}")


class WebContentObject(BaseContentType):
    """
    Displays page visits
    """
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.subjects[0].uri.startswith("http://"):
            return cls.create(event)
        return False

    icon_name = "$ACTOR"
    text = "{interpretation.display_name} {event.subjects[0].text}"
    timelineview_text = "{interpretation.display_name}\n{event.subjects[0].uri}"
    thumbview_text = "{interpretation.display_name}\n{event.subjects[0].text}"


# Content object list used by the section function
CONTENT_OBJECTS = (BzrContentObject, WebContentObject, IMContentObject)
