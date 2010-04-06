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

import gtk

from urlparse import urlparse
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation

from gio_file import GioFile, THUMBS, ICONS, SIZE_LARGE, SIZE_NORMAL
import common


SIZE_THUMBVIEW = (92, 72)
SIZE_TIMELINEVIEW = (32, 24)


def choose_content_object(event):
    #print event.payload
    # This is where the selection will be done
    return FileContentObject(event)


class GenericContentObject(object):
    """
    Defines the required interface of a Content wrapper that displays all the methods
    a wrapper implements
    """

    def __init__(self, event=None):
        self._uri = event.subjects[0].uri
        self._event = event

    @classmethod
    def create(cls, event):
        """
        Can return None
        """

        return None

    @property
    def event(self):
        return self._event

    @event.setter
    def event(self, value):
        self._event = value

    @property
    def uri(self):
        return self._uri

    def get_content(self):
        return None

    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        if size == SIZE_THUMBVIEW:
            return self.__get_thumbview_icon()
        elif size == SIZE_TIMELINEVIEW:
            return self.__get_timelineview_icon()
        thumb = None
        return thumb

    def __get_thumbview_icon(self):
        return None

    def __get_timelineview_icon(self):
        return None

    @property
    def thumbnail(self):
        return self.get_thumbnail()

    def get_monitor(self):
        raise NotImplementedError

    def refresh(self):
        pass

    def get_icon(self, size=24, can_thumb=False, border=0):
        icon = None
        return icon

    @property
    def icon(self):
        return self.get_icon()

    def launch(self):
        pass

    def has_preview(self):
        return False

    def thumb_icon_allowed(self):
        return False

    @property
    def emblems(self):
        emblem_collection = []
        if not self.has_preview:
            emblem_collection.append(self.icon)
        return emblem_collection

    # Used for timeline
    phases = None

    @property
    def color(self):
        return common.get_file_color(self.event.subjects[0].interpretation, self.event.subjects[0].mimetype)


    def get_pango_subject_text(self):
        if hasattr(self, "__pretty_subject_text"): return self.__pretty_subject_text
        text = common.get_event_text(self.event)
        interpretation = common.get_event_interpretation(self.event)
        t = (common.FILETYPESNAMES[interpretation] if
             interpretation in common.FILETYPESNAMES.keys() else "Unknown")
        text = text.replace("%", "%%")
        t1 = "<span color='!color!'><b>" + t + "</b></span>"
        t2 = "<span color='!color!'>" + text + "</span> "
        self.__pretty_subject_text = (str(t1) + "\n" + str(t2) + "").replace("&", "&amp;").replace("!color!", "%s")
        return self.__pretty_subject_text


class FileContentObject(GioFile, GenericContentObject):

    def __init__(self, event):
        GenericContentObject.__init__(self, event)
        uri = event.subjects[0].uri
        return GioFile.__init__(self, uri)

    @classmethod
    def create(cls, event):
        try:
            return cls(event)
        except gio.Error:
            return None

    #@property
    #def phases(self):
    #    return []

    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        if size == SIZE_THUMBVIEW:
            return self.__get_thumbview_icon()
        elif size == SIZE_TIMELINEVIEW:
            return self.__get_timelineview_icon()
        return GioFile.get_thumbnail(self, size, border)

    def __get_thumbview_icon(self):
        if hasattr(self, "__thumbpb"):
            return self.__thumbpb, self.__isthumb
        self.__thumbpb, self.__isthumb = common.PIXBUFCACHE.get_pixbuf_from_uri(self.uri, SIZE_LARGE, iconscale=0.1875, w=SIZE_THUMBVIEW[0], h=SIZE_THUMBVIEW[1])
        return self.__thumbpb, self.__isthumb

    def __get_timelineview_icon(self):
        #uri = self.uri
        if hasattr(self, "__timelinepb"):
            return self.__timelinepb, self.__timeline_isthumb

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
        self.__timelinepb = pixbuf
        self.__timeline_isthumb = usethumb&thumb
        return pixbuf, usethumb & thumb






