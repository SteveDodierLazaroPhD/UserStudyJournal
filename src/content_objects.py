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
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
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
import sys
from xdg import DesktopEntry
import xml.dom.minidom as dom

from urlparse import urlparse
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation

from config import get_icon_path, get_data_path
# Fix for merging this and giofile
import common
from common import GioFile, THUMBS, ICONS, SIZE_LARGE, SIZE_NORMAL, SIZE_THUMBVIEW, SIZE_TIMELINEVIEW
#
from config import SUPPORTED_SOURCES
from external import TELEPATHY


class CachedAttribute(object):
    """
    runs the method once, finds the value, and replace the descriptor
    in the instance with the found value
    """
    def __init__(self, method, name=None):
        self.method = method
        self.attr_name = name or method.__name__

    def __get__(self, instance, cls):
        if instance is None:
            return self
        value = self.method(instance)
        setattr(instance, self.attr_name, value)
        return value


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


class Object(object):
    """
    Keeps a list of instances of this class
    """
    matches_search = False
    instances = []
    def __init__(self):
        super(Object, self).__init__()
        Object.instances.append(self)

    def __del__(self):
        Object.instances.remove(self)
        return super(Object, self).__del__()


class ContentObject(Object):
    """
    Defines the required interface of a Content object. This is a abstract class.
    """

    @classmethod
    def find_matching_events(cls, template):
        for obj in cls.instances:
            if obj.event.matches_template(template):
                yield obj

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
        super(ContentObject, self).__init__()
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

    @property
    def uri(self):
        return self.event.subjects[0].uri

    @property
    def mime_type(self):
        return self.event.subjects[0].mimetype

    # View methods
    @property
    def thumbview_pixbuf(self):
        """:returns: tuple with containing a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        return None

    @property
    def timelineview_pixbuf(self):
        """:returns: tuple with containing a sized pixbuf for the timeline and a ispreview bool describing if it is a preview"""
        return None

    # Icon methods
    def get_icon(self, size=24, *args, **kwargs):
        """
        :Returns: a pixbuf representing this event's icon
        """
        return None

    @property
    def icon(self):
        return self.get_icon()

    @CachedAttribute
    def emblems(self):
        emblems = []
        emblems.append(self.get_icon(16))
        emblems.append(None)
        emblems.append(None)
        emblems.append(self.get_actor_pixbuf(16))
        return emblems

    # utility
    def launch(self):
        """
        Launches a event
        """
        pass

    # Used for timeline
    phases = None

    # Thumbview and Timelineview methods
    @CachedAttribute
    def type_color_representation(self):
        """
        Uses the tango color pallet to find a color representing the content type

        :returns: a rgb tuple
        """
        color1 = common.get_file_color(self.event.subjects[0].interpretation,
                                       self.event.subjects[0].mimetype)
        try:
            i = (common.TANGOCOLORS.index(color1)/3)*3
            if i == common.TANGOCOLORS.index(color1): i += 1
            color2 = common.TANGOCOLORS[i]
        except ValueError:
            color2 = common.TANGOCOLORS[-2]
        return (color1, color2)

    @CachedAttribute
    def text(self):
        return str(self.event.subjects[0].text)

    @CachedAttribute
    def timelineview_text(self):
        """
        :returns: a string of text markup used in timeline widget and elsewhere
        """
        text = self.event.subjects[0].text
        interpretation = self.event.subjects[0].interpretation
        t = (common.FILETYPESNAMES[interpretation] if
             interpretation in common.FILETYPESNAMES.keys() else "Unknown")
        timelineview_text = (t + "\n" + text).replace("%", "%%")
        return timelineview_text


    @CachedAttribute
    def thumbview_text(self):
        """
        :returns: a string of text used in thumb widget and elsewhere
        """
        return self.event.subjects[0].text

    def get_actor_desktop_file(self):
        """
        Finds a desktop file for a actor
        """
        desktop_file = None
        if self.event.actor in common.DESKTOP_FILES:
            return common.DESKTOP_FILES[self.event.actor]
        path = None
        for desktop_path in common.DESKTOP_FILE_PATHS:
            if os.path.exists(self.event.actor.replace("application://", desktop_path)):
                path = self.event.actor.replace("application://", desktop_path)
                break
        if path:
            desktop_file = DesktopEntry.DesktopEntry(path)
        common.DESKTOP_FILES[self.event.actor] = desktop_file
        return desktop_file

    def get_actor_pixbuf(self, size):
        """
        Finds a icon for a actor

        :returns: a pixbuf
        """
        desktop = self.get_actor_desktop_file()
        if not desktop:
            pixbuf = None
        else:
            name = desktop.getIcon()
            pixbuf = common.get_icon_for_name(name, size)
        return pixbuf

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

    @CachedAttribute
    def thumbview_pixbuf(self):
        """Special method which returns a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        thumbview_pixbuf, isthumb = common.PIXBUFCACHE.get_pixbuf_from_uri(self.uri, SIZE_LARGE, iconscale=0.1875, w=SIZE_THUMBVIEW[0], h=SIZE_THUMBVIEW[1])
        return thumbview_pixbuf

    @CachedAttribute
    def timelineview_pixbuf(self):
        """Special method which returns a sized pixbuf for the timeline and a ispreview bool describing if it is a preview"""
        usethumb = (True if self.event.subjects[0].interpretation
                    in common.MEDIAINTERPRETATIONS else False)
        thumb = False
        if common.PIXBUFCACHE.has_key(self.uri) and usethumb:
            pixbuf, thumb = common.PIXBUFCACHE[self.uri]
            pixbuf = pixbuf.scale_simple(32, 24, gtk.gdk.INTERP_TILES)
        else:
            pixbuf = common.get_icon_from_object_at_uri(self.uri, 24)
        if common.PIXBUFCACHE.has_key(self.uri) and usethumb and pixbuf != common.PIXBUFCACHE[self.uri][0]:
            pixbuf, thumb = common.PIXBUFCACHE[self.uri]
            pixbuf = pixbuf.scale_simple(32, 24, gtk.gdk.INTERP_TILES)
        if not pixbuf: pixbuf = common.PLACEHOLDER_PIXBUFFS[24]
        is_thumbnail = usethumb&thumb
        return pixbuf


class BaseContentType(ContentObject):
    """

    A Base content type which has 6 fields which define the automated content
    type creation. The string fields are ran into string format where formatting
    is done. The keywords are as follows:

    event is the event
    content_obj is self
    interpretation is the event interpretation
    subject_interpretation is the first subjects interpretation
    source = the SUPPORTED_SOURCES source for the interpretation

    if icon_name is equal to $ACTOR then the actor icon is used
    if icon_name is equal to $MIME then the MIME icon is used
    """
    # default fields which subclasses can modify
    icon_name = ""
    icon_uri = ""
    thumbnail_uri = ""

    text = ""
    timelineview_text = ""
    thumbview_text = ""

    # Attributes of this class which will be ran into string format as described
    # in this class's doctstring
    fields_to_format = ("text", "timelineview_text", "thumbview_text")

    def __init__(self, event):
        super(BaseContentType, self).__init__(event)
        # String formatting
        self.wrds = wrds = {
            "content_obj" : self,
            "event" : event
        }
        try: wrds["interpretation"] = Interpretation[event.interpretation]
        except KeyError: wrds["interpretation"] = Interpretation.OPEN_EVENT
        try: wrds["subject_interpretation"] = Interpretation[event.subjects[0].interpretation]
        except KeyError: wrds["subject_interpretation"] = Interpretation.UNKNOWN
        try:
            wrds["source"] = SUPPORTED_SOURCES[self.event.subjects[0].interpretation]
        except:
            wrds["source"] = SUPPORTED_SOURCES[Interpretation.UNKNOWN.uri]
        for name in self.fields_to_format:
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
            if common.PLACEHOLDER_PIXBUFFS.has_key(size): return common.PLACEHOLDER_PIXBUFFS[size]
        return icon

    @CachedAttribute
    def thumbview_pixbuf(self):
        """Special method which returns a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        if self.thumbnail_uri:
            thumbview_pixbuf, isthumb = common.PIXBUFCACHE.get_pixbuf_from_uri(
                self.thumbnail_uri, SIZE_LARGE, iconscale=0.1875, w=SIZE_THUMBVIEW[0], h=SIZE_THUMBVIEW[1])
        else:
           thumbview_pixbuf = None
        return thumbview_pixbuf

    @CachedAttribute
    def timelineview_pixbuf(self):
        """Special method which returns a sized pixbuf for the timeline and a ispreview bool describing if it is a preview"""
        icon = self.get_icon(SIZE_TIMELINEVIEW[1])
        if not icon:
            icon = common.PLACEHOLDER_PIXBUFFS[24]
        return icon

    @CachedAttribute
    def emblems(self):
        emblems = []
        if (not self.thumbnail_uri) and self.icon_name != "$ACTOR":
            emblems.append(self.get_icon(16))
        else:
            emblems.append(None)
        emblems.append(None)
        emblems.append(None)
        emblems.append(self.get_actor_pixbuf(16))
        return emblems

    def launch(self):
        desktop = self.get_actor_desktop_file()
        if desktop:
            command = desktop.getExec()
            try:
                if "%u" in command:
                    command = command.replace("%u", self.uri)
                elif "%U" in command:
                    command = command.replace("%U", self.uri)
                common.launch_string_command(command)
            except OSError: return


class GenericContentObject(BaseContentType):
    """
    Used when no other content type would fit
    """

    if sys.version_info >= (2,6):
        icon_name = "$MIME $ACTOR"
        text = "{event.subjects[0].text}"
        timelineview_text = "{subject_interpretation.display_name}\n{event.subjects[0].uri}"
        thumbview_text = "{subject_interpretation.display_name}\n{event.subjects[0].text}"
    else:
        def __init__(self, event):
            super(BaseContentType, self).__init__(event)
            # String formatting
            self.wrds = wrds = {
            }
            try: wrds["interpretation"] = Interpretation[event.interpretation]
            except KeyError: wrds["interpretation"] = Interpretation.OPEN_EVENT
            try: wrds["subject_interpretation"] = Interpretation[event.subjects[0].interpretation]
            except KeyError: wrds["subject_interpretation"] = Interpretation.UNKNOWN
            try:
                wrds["source"] = SUPPORTED_SOURCES[self.event.subjects[0].interpretation]
            except:
                wrds["source"] = SUPPORTED_SOURCES[Interpretation.UNKNOWN.uri]

        @CachedAttribute
        def text(self):
            return self.event.subjects[0].text

        @CachedAttribute
        def timelineview_text(self):
            return self.wrds["subject_interpretation"].display_name + "\n" + self.event.subjects[0].uri

        @CachedAttribute
        def thumbview_text(self):
            return self.wrds["subject_interpretation"].display_name + "\n" + self.event.subjects[0].text

    def get_icon(self, size=24, *args, **kwargs):
        icon = common.get_icon_for_name(self.mime_type.replace("/", "-"), size)
        if icon:
            return icon
        icon = self.get_actor_pixbuf(size)
        if icon:
            return icon
        if common.PLACEHOLDER_PIXBUFFS.has_key(size): return common.PLACEHOLDER_PIXBUFFS[size]
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

    text = "{event.subjects[0].text}"
    timelineview_text = "Bazaar\n{event.subjects[0].text}"
    thumbview_text = "Bazaar\n{event.subjects[0].text}"

    type_color_representation = common.TANGOCOLORS[1], common.TANGOCOLORS[2]

    def launch(self):
        if common.is_command_available("xdg-open"):
            common.launch_command("xdg-open", [self.uri])


class IMContentObject(BaseContentType):
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.subjects[0].interpretation == Interpretation.IM_MESSAGE.uri:
            return cls.create(event)
        return False

    type_color_representation = common.TANGOCOLORS[13], common.TANGOCOLORS[14]


    icon_name = "empathy"
    if not TELEPATHY:
        text = _("{source._desc_sing} with {event.subjects[0].text}")
        timelineview_text = _("{source._desc_sing} with {event.subjects[0].text}\n{event.subjects[0].uri}")
        thumbview_text = _("{source._desc_sing} with {event.subjects[0].text}")

        def launch(self):
            if common.is_command_available("empathy"):
                common.launch_command("empathy", [self.uri])


    else:
        fields_to_format = ()#"text", "thumbview_text")
        status_symbols = {
            "available" : u" <span color='#4E9A06' weight='bold' rise='2000' size='6000'>" + _("Available") + "</span>",
            "offline" : u" <span color='#A40000' weight='bold' rise='2000' size='6000'>" + _("Offline") + "</span>",
            "away" : u" <span color='#C4A000' weight='bold' rise='2000' size='6000'>" + _("Away") + "</span>",
            "busy" : u" <span color='#C4A000' weight='bold' rise='2000' size='6000'>" + _("Busy") + "</span>",
        }
        status_icon_funcs = {
            "available" : lambda s: common.get_icon_for_name("empathy-available", s),
            "offline" : lambda s: common.get_icon_for_name("empathy-offline", s),
            "away" : lambda s: common.get_icon_for_name("empathy-away", s),
            "busy" : lambda s: common.get_icon_for_name("empathy-busy", s),
        }

        def get_subject_status(self):
            return "offline"

        def get_subject_status_string(self):
            """
            :returns: the status string from status_symbols according to the subjects
            status in telepathy

            !!to be implemented!!
            """
            return self.status_symbols[self.get_subject_status()]

        def get_icon(self, size=24, *args, **kwargs):
            status = self.get_subject_status()
            if size in (24, 48):
                try:
                    return self.status_icon_funcs[status](size)
                except:pass
            return BaseContentType.get_icon(self, size, *args, **kwargs)

        @property
        def text(self):
            status = self.get_subject_status_string()
            return self.wrds["source"]._desc_sing + " " + _("with") + " " + self.event.subjects[0].text

        @property
        def timelineview_text(self):
            status = self.get_subject_status_string()
            return self.wrds["source"]._desc_sing + " " + _("with") + " " + self.event.subjects[0].text + "\n" + self.uri + status

        @property
        def thumbview_text(self):
            status = self.get_subject_status_string()
            return self.wrds["source"]._desc_sing + " " + _("with") + " " + self.event.subjects[0].text + "\n" + status

        def launch(self):
            if common.is_command_available("empathy"):
                common.launch_command("empathy", [self.uri])


class WebContentObject(BaseContentType):
    """
    Displays page visits

    We can write dataproviders which generate pixbufs and the thumbnail_uri
    property request will find it for the thumbview
    """
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.subjects[0].uri.startswith("http://"):
            return cls.create(event)
        return False

    icon_name = "$MIME $ACTOR"
    # thumbnail_uri = "/some/users/cache/hash(uri).png"
    text = "{interpretation.display_name} {event.subjects[0].text}"
    timelineview_text = "{interpretation.display_name}\n{event.subjects[0].uri}"
    thumbview_text = "{interpretation.display_name}\n{event.subjects[0].text}"
    #type_color_representation = (207/255.0, 77/255.0, 16/255.0), (207/255.0, 77/255.0, 16/255.0)


class EmailContentObject(BaseContentType):
    """
    An Email Content Object where any additional subjects are considered attachments
    """
    @classmethod
    def use_class(cls, event):
        if event.subjects[0].interpretation == Interpretation.EMAIL:
            return cls.create(event)
        return False
    icon_name = "$MIME $ACTOR"

    fields_to_format = ("_text", "_timelineview_text", "_thumbview_text")

    _text = _("{source._desc_sing} from {event.subjects[0].text}")
    _timelineview_text = _("{source._desc_sing} from {event.subjects[0].text}\n{event.subjects[0].uri}")
    _thumbview_text = _("{source._desc_sing} from {event.subjects[0].text}")

    @CachedAttribute
    def _attachment_string(self): return (_(" (%s Attachments)") % str(len(self.event.subjects)))

    @CachedAttribute
    def text(self):
        return self._text + self._attachment_string

    @CachedAttribute
    def timelineview_text(self):
        return self._timelineview_text + self._attachment_string

    @CachedAttribute
    def thumbview_text(self):
        return self._thumbview_text + self._attachment_string


class TomboyContentObject(BaseContentType):
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.actor == "application://tomboy.desktop":
            return cls.create(event)
        return False

    icon_name = "$ACTOR"
    text = _("{source._desc_sing} {event.subjects[0].text}")
    timelineview_text = _("Tomboy\n{source._desc_sing} {event.subjects[0].text}")
    thumbview_text = _("Tomboy\n{source._desc_sing} {event.subjects[0].text}")

    type_color_representation = common.TANGOCOLORS[0], common.TANGOCOLORS[2]

    def launch(self):
        if common.is_command_available("tomboy"):
            common.launch_command("tomboy", ["--open-note", self.uri])


class MusicPlayerContentObject(BaseContentType):
    """Used by music players when the backing subject is not a file"""

    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.actor in ("application://banshee.desktop", "application://rhythmbox.desktop") \
           and not event.subjects[0].uri.startswith("file://"):
            return cls.create(event)
        return False

    icon_name = "$MIME $ACTOR"
    text = "{event.subjects[0].text}"
    timelineview_text = "{event.subjects[0].text}"
    thumbview_text = "{event.subjects[0].text}"

    @CachedAttribute
    def mime_type(self):
        event_mime = self.event.subjects[0].mimetype or ""
        if "audio" not in event_mime or "video" not in event_mime:
            interpretation = self.event.subjects[0].interpretation
            if Interpretation.VIDEO.uri == interpretation:
                event_mime = "video/mpeg"
            elif Interpretation.MUSIC.uri == interpretation:
                event_mime = "audio/x-mpeg"
            else: event_mime = "audio/x-mpeg"
        return event_mime


# Content object list used by the section function. Should use Subclasses but I like to have some order in which these should be used
if sys.version_info >= (2,6):
    CONTENT_OBJECTS = (MusicPlayerContentObject, BzrContentObject, WebContentObject, IMContentObject, TomboyContentObject, EmailContentObject)
else:
    CONTENT_OBJECTS = tuple()
