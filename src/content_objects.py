# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Randal Barlow
# Copyright © 2011 Stefano Candori <stefano.candori@gmail.com>
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
import glob
import sys
import datetime
from urlparse import urlparse
from xdg import DesktopEntry
import xml.dom.minidom as dom

from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation

from config import get_icon_path, get_data_path, SUPPORTED_SOURCES, UCL_INTERPRETATIONS
from external import TELEPATHY
# Fix for merging this and giofile
import common
from common import GioFile, THUMBS, ICONS, SIZE_LARGE, SIZE_NORMAL, SIZE_THUMBVIEW, SIZE_TIMELINEVIEW, INTERPRETATION_PARENTS


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


class AbstractContentObject(object):
    """
    Keeps a list of instances of this class
    """
    instances = []

    content_object_types = []

    _connections = {"add":[], "remove":[]}

    @classmethod
    def connect_to_manager(cls, signal, func):
        cls._connections[signal].append(func)
        return signal, cls._connections[signal].index(func)

    @classmethod
    def remove_manager_connection(cls, identity):
        del cls._connections[identity[0]][identity[1]]

    @classmethod
    def register_new_content_object_type(cls, content_object_type, index=None):
        if index != None:
            cls.content_object_types.insert(index, content_object_type)
        else:
            cls.content_object_types.append(content_object_type)
        for func in cls._connections["add"]:
            func(content_object_type)

    @classmethod
    def remove_content_object_type(cls, content_object_type):
        cls.content_object_types.remove(content_object_type)
        for func in cls._connections["remove"]:
            func(content_object_type)

    @classmethod
    def new_from_event(cls, event):
        """
        :param event: a zeitgeist.datamodel.Event

        :returns a instance of the best possible ContentObject subclass or None if
        no correct Content Object was found or if that the correct Content object
        rejected the given event
        """
        for obj in cls.content_object_types:
            instance = obj.use_class(event)
            if instance:
                return instance.create(event)
        if event.subjects[0].uri.startswith("file://"):
            return FileContentObject.create(event)
        return GenericContentObject.create(event)

    @classmethod
    def find_best_type_from_event(cls, event):
        """
        :param event: a zeitgeist.datamodel.Event

        :returns a instance of the best possible ContentObject subclass or None if
        no correct Content Object was found or if that the correct Content object
        rejected the given event
        """
        for obj in cls.content_object_types:
            instance = obj.use_class(event)
            if instance:
                return instance
        if event.subjects[0].uri.startswith("file://"):
            return FileContentObject
        return GenericContentObject

    def __init__(self):
        super(AbstractContentObject, self).__init__()
        self.instances.append(self)

    def __del__(self):
        self.instances.remove(self)
        return super(AbstractContentObject, self).__del__()


class ContentObject(AbstractContentObject):
    """
    Defines the required interface of a Content object. This is a abstract class.
    """

    matches_search = False

    @classmethod
    def clear_search_matches(cls):
        map(lambda o: setattr(o, "matches_search", False), cls.instances)

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
            return cls
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

    @property
    def category(self):
        return self.event.subjects[0].interpretation

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
        try:
            interpretation = INTERPRETATION_PARENTS[self.event.subjects[0].interpretation]
        except Exception:
            interpretation = self.event.subjects[0].interpretation
        t = (common.FILETYPESNAMES[interpretation] if
             interpretation in common.FILETYPESNAMES.keys() else "Unknown")
        timelineview_text = (self.text+ "\n" + t).replace("%", "%%")
        return timelineview_text

    @CachedAttribute
    def thumbview_text(self):
        """
        :returns: a string of text used in thumb widget and elsewhere
        """
        return self.text

    def get_actor_desktop_file(self, actor=None):
        """
        Finds a desktop file for a actor
        """
        
        if actor is None:
            actor = self.event.actor
        
        desktop_file = None
        if actor in common.DESKTOP_FILES:
            return common.DESKTOP_FILES[actor]
        path = None
        for desktop_path in common.DESKTOP_FILE_PATHS:
            if os.path.exists(actor.replace("application://", desktop_path)):
                path = actor.replace("application://", desktop_path)
                break
        if path:
            desktop_file = DesktopEntry.DesktopEntry(path)
        else:
            actor_name = actor.replace("application://", "").replace(".desktop", "")
            for desktop_path in common.DESKTOP_FILE_PATHS:
                for file in glob.glob(desktop_path+'*.desktop'):
                    try:
                        with open(file) as f:
                            contents = f.read()
                        if 'TryExec='+actor_name in contents or 'Exec='+actor_name in contents:
                            desktop_file = DesktopEntry.DesktopEntry(file)
                            common.DESKTOP_FILES[actor] = desktop_file
                            return desktop_file
                    except IOError:
                        pass

        common.DESKTOP_FILES[actor] = desktop_file
        return desktop_file

    def get_actor_pixbuf(self, size, target=None):
        """
        Finds a icon for a actor

        :returns: a pixbuf
        """
        desktop = self.get_actor_desktop_file(target)
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
            return cls
        return False
    
    thumbnail_uri = ""
    molteplicity = False

    def __init__(self, event):
        ContentObject.__init__(self, event)
        uri = event.subjects[0].uri
        GioFile.__init__(self, uri)

    @classmethod
    def create(cls, event):
        try:
            return cls(event)
        except gio.Error:
            return None

    @CachedAttribute
    def text(self):
        return self._file_object.get_basename()

    @CachedAttribute
    def thumbview_pixbuf(self):
        """
        Special method which returns a pixbuf for the thumbview 
        and a ispreview bool describing if it is a preview
        """
        thumbview_pixbuf, isthumb = common.PIXBUFCACHE.get_pixbuf_from_uri(self.uri, SIZE_LARGE)
        return thumbview_pixbuf, isthumb

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
        
    def get_thumbview_pixbuf_for_size(self, w, h):
        pix, isthumb = self.thumbview_pixbuf
        if pix is not None:
            if isthumb:
                pix = common.scale_to_fill(pix, w, h)
            else:
                pix = pix.scale_simple(w // 2, w // 2, gtk.gdk.INTERP_BILINEAR)
        return pix,isthumb


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
    
    #Field used to group particular type of event like 
    #website or irc chats in thumb and timeline view
    molteplicity = False

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
        except KeyError: wrds["interpretation"] = Interpretation.ACCESS_EVENT
        try: wrds["subject_interpretation"] = Interpretation[event.subjects[0].interpretation]
        except KeyError: wrds["subject_interpretation"] = Interpretation
        try:
            wrds["source"] = SUPPORTED_SOURCES[self.event.subjects[0].interpretation]
        except Exception:
            wrds["source"] = SUPPORTED_SOURCES[""]
        try:
            wrds["manifestation"] = Manifestation[event.manifestation]
        except Exception:
            wrds["manifestation"] = Manifestation
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
                if "$ACTINGSUBJECT" in self.icon_name:
                    icon = self.get_actor_pixbuf(size, self.event.subjects[0].uri)
                if self.icon_uri:
                    icon = common.get_icon_for_uri(self.icon_uri, size)
                elif self.icon_name and self.icon_name not in ("$MIME", "$ACTOR", "$ACTINGSUBJECT"):
                    icon = common.get_icon_for_name(self.icon_name, size)
                break
        except glib.GError:
            if common.PLACEHOLDER_PIXBUFFS.has_key(size): return common.PLACEHOLDER_PIXBUFFS[size]
        #if i can't find any icon for this event i use the default one
        if not icon:
            if common.PLACEHOLDER_PIXBUFFS.has_key(size): return common.PLACEHOLDER_PIXBUFFS[size]  
        return icon

    @CachedAttribute
    def thumbview_pixbuf(self):
        """Special method which returns a pixbuf for the thumbview and a ispreview bool describing if it is a preview"""
        isthumb = False
        if self.thumbnail_uri:
            thumbview_pixbuf, isthumb = common.PIXBUFCACHE.get_pixbuf_from_uri(
                self.uri, SIZE_LARGE)
        else:
            thumbview_pixbuf = self.get_icon(SIZE_NORMAL[0])
        return thumbview_pixbuf, isthumb
        
    def get_thumbview_pixbuf_for_size(self, w, h):
       pix, isthumb = self.thumbview_pixbuf
       if pix is not None:
           if isthumb:
               pix = common.scale_to_fill(pix, w, h)
           else:
               pix = pix.scale_simple(w // 2, w // 2, gtk.gdk.INTERP_BILINEAR)
       return pix,isthumb

    @CachedAttribute
    def timelineview_pixbuf(self):
        """Special method which returns a sized pixbuf for the timeline and a ispreview bool describing if it is a preview"""
        icon = self.get_icon(SIZE_TIMELINEVIEW[1][1])
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
            except KeyError: wrds["interpretation"] = Interpretation.ACCESS_EVENT
            try: wrds["subject_interpretation"] = INTERPRETATION_PARENTS[Interpretation[event.subjects[0].interpretation]]
            except KeyError: wrds["subject_interpretation"] = Interpretation
            try:
                wrds["source"] = SUPPORTED_SOURCES[self.event.subjects[0].interpretation]
            except Exception:
                wrds["source"] = SUPPORTED_SOURCES[""]

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
            return cls
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

class UCLContentType(BaseContentType):
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        for inter in cls.class_interpretation():
            if event.interpretation == UCL_INTERPRETATIONS[inter]:
                return cls
        return False

    @classmethod
    def class_interpretation(cls):
        return ()

    @property
    def category(self):
        return UCL_INTERPRETATIONS[self.__class__.class_interpretation()[-1]]
#        return self.event.interpretation
#        return self.event.subjects[self._meta_subject].interpretation

    icon_name = ""

    _text = "UCL event"
    _thumbview_text = "UCL event"
    _timelineview_text = "UCL event"
    _molteplicity_text = "Multiple UCL events"

    _meta_subject = -1
    _use_time = False

    molteplicity = True

    @property
    def uri(self):
        return self.event.subjects[0].uri
    @property
    def mime_type(self):
        return self.event.subjects[0].mimetype
    
    @CachedAttribute
    def actor_name(self):
        return self._actor_name()
    
    def _actor_name(self, target=None):
        desktop = self.get_actor_desktop_file(target);
        if desktop:
            actor = desktop.getName()
        else:
            actor = "{event.actor}"
        return actor

    def actor_pid(self):
        try:
            uri = self.event.subjects[self._meta_subject].uri
            return uri.split("///")[1].split("//")[1]
        except IndexError:
            return 0

    @CachedAttribute 
    def molteplicity_text(self):
        return _(self._molteplicity_text)

    @CachedAttribute
    def time(self):
        if self._use_time:
            return ", at " + (datetime.datetime.fromtimestamp(int(int(self.event.timestamp) / 1000)).strftime('%H:%M:%S'))
        else:
            return ""

    @CachedAttribute
    def text(self):
        pid = self.actor_pid()
        if pid != 0:
            return self._text + "\n" + self.actor_name + ", pid " + pid + self.time
        else:
            return self._text + "\n" + self.actor_name + self.time;

    @CachedAttribute
    def timelineview_text(self):
        pid = self.actor_pid()
        if pid != 0:
            return self._timelineview_text + "\n" + self.actor_name + ", pid " + pid + self.time
        else:
            return self._timelineview_text + "\n" + self.actor_name + self.time;

    @CachedAttribute
    def thumbview_text(self):
        return self._thumbview_text + "\n" + self.actor_name + self.time;

    type_color_representation = common.TANGOCOLORS[1], common.TANGOCOLORS[2]

    def launch(self):
        pass

class ClipboardCopyObject(UCLContentType):
    @classmethod
    def class_interpretation(cls):
        return ('copy2', 'copy3', 'copy')

    icon_name = "edit-copy"
    _text = "Copy event"
    _thumbview_text = "Copy event"
    _timelineview_text = "Copy event"
    _molteplicity_text = "Copied data"
    _use_time = True

    type_color_representation = common.TANGOCOLORS[1], common.TANGOCOLORS[2]

class ClipboardPasteObject(UCLContentType):
    @classmethod
    def class_interpretation(cls):
        return ('paste2', 'paste3')

    icon_name = "edit-paste"
    _text = "Paste event"
    _thumbview_text = "Paste event"
    _timelineview_text = "Paste event"
    _molteplicity_text = "Pasted data"
    _use_time = True

    type_color_representation = common.TANGOCOLORS[1], common.TANGOCOLORS[2]

class UCLFSContentType(UCLContentType):
    
    icon_name = "$MIME $ACTOR"
    _action = "Accessed"

    @CachedAttribute
    def text(self):
        pid = self.actor_pid()
        if pid != 0:
            return self.event.subjects[0].text + "\n" + self._action + " in " + self.actor_name + " (" + pid + ")"
        else:
            return self.event.subjects[0].text + "\n" + self._action + " in " + self.actor_name

    @CachedAttribute
    def timelineview_text(self):
        return self.text

    @CachedAttribute
    def thumbview_text(self):
        return self.text

    type_color_representation = common.TANGOCOLORS[2], common.TANGOCOLORS[5]

class FileAccessObject(UCLFSContentType):
    @classmethod
    def class_interpretation(cls):
        return ('file-access2', 'file-set2', 'file-set3', 'file-access3')

    #icon_name = "document-open"
    _action = "Opened"
    _text = "Opened File"
    _thumbview_text = "Opened File"
    _timelineview_text = "Opened File"
    _molteplicity_text = "Opened File"

class FileCopyObject(UCLFSContentType):
    @classmethod
    def class_interpretation(cls):
        return ('file-copy', 'file-link')

    #icon_name = "document-open"
    _action = "Copied"
    _text = "Copied File"
    _thumbview_text = "Copied File"
    _timelineview_text = "Copied File"
    _molteplicity_text = "Copied File"
    
    @CachedAttribute
    def text(self):
        return self.event.subjects[0].text + "\n" + "Copied to " + self.event.subjects[1].text

class FileCreateObject(UCLFSContentType):
    @classmethod
    def class_interpretation(cls):
        return ('file-create2', 'file-create3', 'file-modify2', 'file-modify3')

    #icon_name = "document-save"
    _action = "Edited"
    _text = "Saved or Created File"
    _thumbview_text = "Saved or Created File"
    _timelineview_text = "Saved or Created File"
    _molteplicity_text = "Saved File"

class FileRecentObject(UCLFSContentType):
    @classmethod
    def class_interpretation(cls):
        return ('recent-file-access2', 'recent-file-access3')

    #icon_name = "document-open-recent"
    _action = "Reopened"
    _text = "Reopened Recent File"
    _thumbview_text = "Reopened Recent File"
    _timelineview_text = "Reopened Recent File"
    _molteplicity_text = "Recent File"
    
    def thumbview_text(self):
        print "Recently opened: " + self.uri
        return self._text

class AppLaunchObject(UCLContentType):
    @classmethod
    def class_interpretation(cls):
        return ('app-launch-n','app-launch')

    #icon_name = "document-open-recent"
    _action = "Launched"
    _text = "Launched App"
    _thumbview_text = "Launched App"
    _timelineview_text = "Launched App"
    _molteplicity_text = "App Launches"
    icon_name = "$ACTINGSUBJECT"

    @CachedAttribute
    def text(self):
        pid = self.actor_pid()
        if pid != 0:
            return self._actor_name(self.event.subjects[0].uri) + "\n" + self._action + " by " + self.actor_name + " (" + pid + ")"
        else:
            return self._actor_name(self.event.subjects[0].uri) + "\n" + self._action + " by " + self.actor_name

    @CachedAttribute
    def timelineview_text(self):
        return self.text

    @CachedAttribute
    def thumbview_text(self):
        return self.text
        
    def launch(self):
        actor_name = self.event.subjects[0].uri.replace("application://", "").replace(".desktop", "")
        if common.is_command_available(actor_name):
            common.launch_command(actor_name)

    type_color_representation = common.TANGOCOLORS[20], common.TANGOCOLORS[17]

class WebAccessObject(UCLContentType):
    @classmethod
    def class_interpretation(cls):
        return ('web-access',)

    icon_name = "browser"
    _action = "Visited"
    _text = "Visited a Website"
    _thumbview_text = "Visited a Website"
    _timelineview_text = "Visited a Website"
    _molteplicity_text = "Visited Websites"

    @CachedAttribute
    def text(self):
        return self._text + "\n" + self.event.subjects[0].uri

    @CachedAttribute
    def timelineview_text(self):
        return self.text

    @CachedAttribute
    def thumbview_text(self):
        return self.text
        
    def launch(self):
        actor_name = self.event.actor.replace("application://", "").replace(".desktop", "")
        if common.is_command_available(actor_name):
            common.launch_command(actor_name, [self.uri])
        elif common.is_command_available('xdg-open'):
            common.launch_command('xdg-open', [self.uri])

    type_color_representation = common.TANGOCOLORS[9], common.TANGOCOLORS[1]

class WebLeaveObject(WebAccessObject):
    @classmethod
    def class_interpretation(cls):
        return ('web-leave',)

    _action = "Left"
    _text = "Left a Website / Closed a Tab"
    _thumbview_text = "Left a Website / Closed a Tab"
    _timelineview_text = "Left a Website / Closed a Tab"
    _molteplicity_text = "Left Websites / Closed Tabs"

class WebDLObject(WebAccessObject):
    @classmethod
    def class_interpretation(cls):
        return ('web-dl',)

    _action = "Downloaded"
    _text = "Downloaded a File"
    _thumbview_text = "Downloaded a File"
    _timelineview_text = "Downloaded a File"
    _molteplicity_text = "Downloaded Files"

class WebActiveObject(WebAccessObject):
    @classmethod
    def class_interpretation(cls):
        return ('web-tabs',)

    #icon_name = "browser"
    _use_time = True
    icon_name = "browser"
    _action = "Opened in"
    _text = "Open Web Tabs"
    _thumbview_text = "Open Web Tabs"
    _timelineview_text = "Open Web Tabs"
    _molteplicity_text = "Open Web Tabs"

    @CachedAttribute
    def text(self):
        tabcount = len(self.event.subjects) - 1
        return self._text + "\n" + str(tabcount) + " tabs open" + self.time

class WindowOpenObject(UCLContentType):
    @classmethod
    def class_interpretation(cls):
        return ('unity-open',)

    icon_name = "window-new"
    _text = "Window Opened"
    _thumbview_text = "Window Opened"
    _timelineview_text = "Window Opened"
    _molteplicity_text = "Windows Opened"
    
    type_color_representation = common.TANGOCOLORS[5], common.TANGOCOLORS[4]

class WindowCloseObject(UCLContentType):
    @classmethod
    def class_interpretation(cls):
        return ('unity-closed',)

    icon_name = "window-close"
    _text = "Window Closed"
    _thumbview_text = "Window Closed"
    _timelineview_text = "Window Closed"
    _molteplicity_text = "Windows Closed"
    
    type_color_representation = common.TANGOCOLORS[5], common.TANGOCOLORS[4]

class WindowCrashObject(UCLContentType):
    @classmethod
    def class_interpretation(cls):
        return ('unity-crash',)

    icon_name = "apport"
    _text = "App Crashed"
    _thumbview_text = "App Crashed"
    _timelineview_text = "App Crashed"
    _molteplicity_text = "Apps Crashed"
    
    type_color_representation = common.TANGOCOLORS[5], common.TANGOCOLORS[4]

class WindowTitleObject(UCLContentType):
    @classmethod
    def class_interpretation(cls):
        return ('unity-title',)

    icon_name = "preferences-system-windows"
    _text = "Window Title Changed"
    _thumbview_text = "Window Title Changed"
    _timelineview_text = "Window Title Changed"
    _molteplicity_text = "Window Titles Changed"
    
    type_color_representation = common.TANGOCOLORS[5], common.TANGOCOLORS[4]

class WindowActiveObject(UCLContentType):
    @classmethod
    def class_interpretation(cls):
        return ('unity-active',)

    icon_name = "preferences-system-windows"
    _text = "Active Windows"
    _thumbview_text = "Active Windows"
    _timelineview_text = "Active Windows"
    _molteplicity_text = "Active Windows"

    @CachedAttribute
    def text(self):
        tabcount = len(self.event.subjects) - 1
        return self._text + "\n" + str(tabcount) + " windows open" + self.time
    
    type_color_representation = common.TANGOCOLORS[5], common.TANGOCOLORS[4]

class IMContentObject(BaseContentType):
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.subjects[0].interpretation == Interpretation.IMMESSAGE.uri \
           and event.actor != "application://xchat.desktop":
            return cls
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
                except Exception:
                    pass
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


#class WebContentObject(BaseContentType):
#    """
#    Displays page visits
#
#    We can write dataproviders which generate pixbufs and the thumbnail_uri
#    property request will find it for the thumbview
#    """
#    @classmethod
#    def use_class(cls, event):
#        """ Used by the content object chooser to check if the content object will work for the event"""
#        if event.subjects[0].uri.startswith(("http://", "https://")):
#            return cls
#        return False
    
#    molteplicity = True
    
#    @CachedAttribute 
#    def molteplicity_text(self): 
#        return _("Surfed in ") + urlparse(self.uri).netloc

#    icon_name = "$MIME $ACTOR"
    # thumbnail_uri = "/some/users/cache/hash(uri).png"
#    text = "{event.subjects[0].text}"
#    timelineview_text = "{event.subjects[0].uri}"
#    thumbview_text = "{event.subjects[0].text}"
    #type_color_representation = (207/255.0, 77/255.0, 16/255.0), (207/255.0, 77/255.0, 16/255.0)


class HamsterContentObject(BaseContentType):
    """
    Used for Hamster(time tracker)
    """
    @classmethod
    def use_class(cls, event):
        if event.actor == "application://hamster-standalone.desktop":
            return cls
        return False

    _prefix = _("Time Tracker")

    icon_name = "hamster-applet"
    text = _prefix + ": {event.subjects[0].text}"
    timelineview_text = _prefix + "\n{event.subjects[0].text}"
    thumbview_text = _prefix + "\n{event.subjects[0].text}"
    
class XChatContentObject(BaseContentType):
    """
    Used for Xchat(irc client)
    """
    @classmethod
    def use_class(cls, event):
        if event.actor == "application://xchat.desktop":
            return cls
        return False
        
    molteplicity = True
    
    @CachedAttribute 
    def molteplicity_text(self): 
        return _("Chatted in ") + urlparse(self.uri).netloc

    icon_name = "$ACTOR"
    _text = "{event.subjects[0].text}"
    _timelineview_text = "{event.subjects[0].text}"
    _thumbview_text = "{event.subjects[0].text}"
     
    @CachedAttribute 
    def is_channel(self): return self.uri.split("/")[-1].startswith("#")
      
    @CachedAttribute
    def buddy_or_channel(self): return self.uri.split("/")[-1]
     
    @CachedAttribute
    def text(self):                                    
        if self.is_channel:
            if self.event.interpretation in \
              [Interpretation.SEND_EVENT.uri, Interpretation.RECEIVE_EVENT.uri]:
                return "{source._desc_sing} in " + self.buddy_or_channel    
            else: return self._text 
        else: return "{source._desc_sing} with " + self.buddy_or_channel

    @CachedAttribute
    def timelineview_text(self):
        if self.is_channel:
            if self.event.interpretation in \
              [Interpretation.SEND_EVENT.uri, Interpretation.RECEIVE_EVENT.uri]:
                return "{source._desc_sing} in " + self.buddy_or_channel
            else: return self._timelineview_text
        else: return "{source._desc_sing} with " + self.buddy_or_channel

    @CachedAttribute
    def thumbview_text(self):
        if self.is_channel:
            if self.event.interpretation in \
              [Interpretation.SEND_EVENT.uri, Interpretation.RECEIVE_EVENT.uri]:
                return "{source._desc_sing} in " + self.buddy_or_channel
            else: return self._thumbview_text 
        else: return "{source._desc_sing} with " + self.buddy_or_channel
    
    def launch(self):
        if common.is_command_available("xchat"):
            if self.is_channel:
                common.launch_command("xchat", ["-e", "--url=" + self.uri])


class EmailContentObject(BaseContentType):
    """
    An Email Content Object where any additional subjects are considered attachments
    """
    @classmethod
    def use_class(cls, event):
        if event.subjects[0].interpretation == Interpretation.EMAIL:
            return cls
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
            return cls
        return False

    icon_name = "$ACTOR"
    text = _("{event.subjects[0].text}")
    timelineview_text = _("Note\n{event.subjects[0].text}")
    thumbview_text = _("Note\n{event.subjects[0].text}")

    type_color_representation = common.TANGOCOLORS[0], common.TANGOCOLORS[2]

    def launch(self):
        if common.is_command_available("tomboy"):
            common.launch_command("tomboy", ["--open-note", self.uri])


class GTGContentObject(BaseContentType):
    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.actor == "application://gtg.desktop":
            return cls
        return False

    icon_name = "$ACTOR"
    text = _("{source._desc_sing} {event.subjects[0].text}")
    timelineview_text = _("GTG\n{source._desc_sing} {event.subjects[0].text}")
    thumbview_text = _("GTG\n{source._desc_sing} {event.subjects[0].text}")

    type_color_representation = common.TANGOCOLORS[0], common.TANGOCOLORS[2]

    def launch(self):
        if common.is_command_available("gtg"):
            common.launch_command("gtg", [self.uri])


class MusicPlayerContentObject(BaseContentType):
    """Used by music players when the backing subject is not a file"""

    @classmethod
    def use_class(cls, event):
        """ Used by the content object chooser to check if the content object will work for the event"""
        if event.actor in ("application://banshee.desktop", "application://rhythmbox.desktop") \
           and not event.subjects[0].uri.startswith("file://"):
            return cls
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
            elif Interpretation.AUDIO.uri == interpretation:
                event_mime = "audio/x-mpeg"
            else: event_mime = "audio/x-mpeg"
        return event_mime


# Content object list used by the section function. Should use Subclasses but I like to have some order in which these should be used
if sys.version_info >= (2,6):
    map(AbstractContentObject.content_object_types.append,
        (MusicPlayerContentObject, BzrContentObject, ClipboardCopyObject, ClipboardPasteObject, XChatContentObject, #WebContentObject,
         FileAccessObject, FileCopyObject, FileCreateObject, FileRecentObject, AppLaunchObject,
         WebAccessObject, WebLeaveObject, WebDLObject, WebActiveObject,
         WindowOpenObject, WindowCloseObject, WindowTitleObject, WindowCrashObject, WindowActiveObject,
         IMContentObject, TomboyContentObject, GTGContentObject, EmailContentObject, HamsterContentObject))

