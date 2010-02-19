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
import time
import threading

from zeitgeist.datamodel import Event, Subject, Interpretation
from gio_file import GioFile, SIZE_LARGE, SIZE_NORMAL

import drawing

ICON_THEME = gtk.icon_theme_get_default()


FILETYPESNAMES = {
    Interpretation.VIDEO.uri : "Video",
    Interpretation.MUSIC.uri : "Music",
    Interpretation.DOCUMENT.uri : "Document",
    Interpretation.IMAGE.uri : "Image",
    Interpretation.SOURCECODE.uri : "Source Code",
    Interpretation.UNKNOWN.uri : "Unknown",
    }

def launch_event(event):
    gfile = GioFile(get_uri(event))
    gfile.launch()

def get_interpretation(event):
    return event.subjects[0].interpretation

def get_typename(event):
    return FILETYPESNAMES[event.subjects[0].interpretation]

def get_mimetype(event):
    return event.subjects[0].mimetype

def get_text(event):
    return event.subjects[0].text

def get_uri(event):
    return event.subjects[0].uri#[7:].replace("%20", " ")

def get_timestamp(event):
    if hasattr(self, "_event"):
        return float(event.timestamp)

def get_timetext(event):
    t = time.localtime(get_timestamp(event)/1000)
    return time.strftime("%H:%M, %d %B", t)


def get_pixbuf_from_uri(uri, size=SIZE_LARGE, iconscale=1):
    """
    Return a pixbuf and True if a thumbnail was found, else False

    Arguments:
    -- size: a size tuple from thumbfactory
    -- iconscale: a factor to reduce other icons by
    """
    gfile = GioFile(uri)
    thumb = True
    if gfile:
        if gfile.has_preview():
            pb = gfile.get_thumbnail(size=size)
        else:
            iconsize = int(size[0]*iconscale)
            pb = gfile.get_icon(size=iconsize)
            thumb = False
    else: pb = None
    if not pb:
        pb = ICON_THEME.lookup_icon(gtk.STOCK_MISSING_IMAGE, 64, gtk.ICON_LOOKUP_FORCE_SVG).load_icon()
        thumb = False
    return pb, thumb

def get_event_icon(event, size):
    gfile = GioFile(get_uri(event))
    if gfile:
        pb = gfile.get_icon(size=size)
        if pb:
            return pb
    return False

def get_event_markup(event):
    """
    Returns a typename and event formatted to be displayed in a info bubble
    """
    t0 = get_typename(event)
    t1 = get_text(event)
    return ("<span size='10240'>%s</span>\n<span size='8192'>%s</span>" % (t0, t1)).replace("&", "&amp;")

def get_pixbuf(event, w, h):
    uri = get_uri(event)
    pb, isthumb = get_pixbuf_from_uri(uri, SIZE_LARGE, iconscale=2/9.0)
    if isthumb:
        rendering_functions = {}
        pb = drawing.scale_to_fill(pb, w, h)
        # Hack to make file previews display as non thumbs
        #if get_interpretation(event) in (Interpretation.DOCUMENT.uri, Interpretation.SOURCECODE.uri):
        #    pb = drawing.new_grayscale_pixbuf(pb)
        #    isthumb = False
    return pb, isthumb










