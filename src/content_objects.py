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

from urlparse import urlparse
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation

from gio_file import GioFile, THUMBS, ICONS, SIZE_LARGE, SIZE_NORMAL
import common


SIZE_THUMBVIEW = (92, 72)

def choose_content_object(event):
    return FileContentObject(event)

class GenericContentObject(object):
    """
    Defines the required interface of a Content wrapper that displays all the methods
    a wrapper implements
    """

    def __init__(self, event=None):
        self._uri = event.subjects[0].uri
        self._event = event


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
            return __get_thumbview_icon
        thumb = None
        return thumb

    def __get_thumbview_icon(self):
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

    @property
    def phases(self):
        return []


class FileContentObject(GioFile, GenericContentObject):

    def __init__(self, event):
        GenericContentObject.__init__(self, event)
        uri = event.subjects[0].uri
        return GioFile.__init__(self, uri)


    @property
    def phases(self):
        return []

    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        if size == SIZE_THUMBVIEW:
            return self.__get_thumbview_icon()
        return GioFile.get_thumbnail(self, size, border)

    def __get_thumbview_icon(self):
        if hasattr(self, "__pb"):
            return self.__pb, self.__isthumb
        self.__pb, self.__isthumb = common.PIXBUFCACHE.get_pixbuf_from_uri(self.uri, SIZE_LARGE, iconscale=0.1875, w=SIZE_THUMBVIEW[0], h=SIZE_THUMBVIEW[1])
        return self.__pb, self.__isthumb



