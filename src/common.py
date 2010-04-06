# -.- coding: utf-8 -.-
#
# Filename
#
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
# Copyright © 2010 Siegfried Gevatter <siegfried@gevatter.com>
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

"""
Common Functions and classes which are used to create the alternative views,
and handle colors, pixbufs, and text
"""

import cairo
import gobject
import gtk
import os
import pango
import pangocairo
import time
import math
import operator
import subprocess

from gio_file import GioFile, SIZE_LARGE, SIZE_NORMAL, ICONS

from zeitgeist.datamodel import Interpretation, Event


TANGOCOLORS = [
    (252/255.0, 234/255.0,  79/255.0),#0
    (237/255.0, 212/255.0,   0/255.0),
    (196/255.0, 160/255.0,   0/255.0),

    (252/255.0, 175/255.0,  62/255.0),#3
    (245/255.0, 121/255.0,   0/255.0),
    (206/255.0,  92/255.0,   0/255.0),

    (233/255.0, 185/255.0, 110/255.0),#6
    (193/255.0, 125/255.0,  17/255.0),
    (143/255.0,  89/255.0,  02/255.0),

    (138/255.0, 226/255.0,  52/255.0),#9
    (115/255.0, 210/255.0,  22/255.0),
    ( 78/255.0, 154/255.0,  06/255.0),

    (114/255.0, 159/255.0, 207/255.0),#12
    ( 52/255.0, 101/255.0, 164/255.0),
    ( 32/255.0,  74/255.0, 135/255.0),

    (173/255.0, 127/255.0, 168/255.0),#15
    (117/255.0,  80/255.0, 123/255.0),
    ( 92/255.0,  53/255.0, 102/255.0),

    (239/255.0,  41/255.0,  41/255.0),#18
    (204/255.0,   0/255.0,   0/255.0),
    (164/255.0,   0/255.0,   0/255.0),

    (136/255.0, 138/255.0, 133/255.0),#21
    ( 85/255.0,  87/255.0,  83/255.0),
    ( 46/255.0,  52/255.0,  54/255.0),
]

FILETYPES = {
    Interpretation.VIDEO.uri : 0,
    Interpretation.MUSIC.uri : 3,
    Interpretation.DOCUMENT.uri : 12,
    Interpretation.IMAGE.uri : 15,
    Interpretation.SOURCECODE.uri : 12,
    Interpretation.UNKNOWN.uri : 21,
    Interpretation.IM_MESSAGE.uri : 21,
    Interpretation.EMAIL.uri : 21
}

FILETYPESNAMES = {
    Interpretation.VIDEO.uri : _("Video"),
    Interpretation.MUSIC.uri : _("Music"),
    Interpretation.DOCUMENT.uri : _("Document"),
    Interpretation.IMAGE.uri : _("Image"),
    Interpretation.SOURCECODE.uri : _("Source Code"),
    Interpretation.UNKNOWN.uri : _("Unknown"),
    Interpretation.IM_MESSAGE.uri : _("IM Message"),
    Interpretation.EMAIL.uri :_("Email"),

}

MEDIAINTERPRETATIONS = [
    Interpretation.VIDEO.uri,
    Interpretation.IMAGE.uri,
]

TIMELABELS = [_("Morning"), _("Afternoon"), _("Evening")]
ICON_THEME = gtk.icon_theme_get_default()

def get_file_color(ftype, fmime):
    """Uses hashing to choose a shade from a hue in the color tuple above

    :param ftype: a :class:`Event <zeitgeist.datamodel.Interpretation>`
    :param fmime: a mime type string
    """
    if ftype in FILETYPES.keys():
        i = FILETYPES[ftype]
        l = int(math.fabs(hash(fmime))) % 3
        return TANGOCOLORS[min(i+l, len(TANGOCOLORS)-1)]
    return (136/255.0, 138/255.0, 133/255.0)

##
## Zeitgeist event helper functions because Randal really hates doing
## event.subject[0].uri, it makes him cry

def launch_event(event):
    """
    Launches a uri from a event

    :param event: a :class:`Event <zeitgeist.datamodel.Event>`
    """
    gfile = GioFile(get_event_uri(event))
    gfile.launch()

def get_event_interpretation(event):
    """
    :param event: a :class:`Event <zeitgeist.datamodel.Event>`

    :returns: a interpretation uri from a event
    """
    return event.subjects[0].interpretation

def get_event_typename(event):
    """
    :param event: a :class:`Event <zeitgeist.datamodel.Event>`

    :returns: a plain text version of a interpretation
    """
    try:
        return Interpretation[event.subjects[0].interpretation].display_name
    except KeyError:
        pass
    return FILETYPESNAMES[event.subjects[0].interpretation]

def get_event_mimetype(event):
    """
    :param event: a :class:`Event <zeitgeist.datamodel.Event>`

    :returns: a plain text version of a mimetype
    """
    return event.subjects[0].mimetype

def get_event_text(event):
    """
    :param event: a :class:`Event <zeitgeist.datamodel.Event>`

    :returns: the file name text of a event
    """
    return event.subjects[0].text

def get_event_uri(event):
    """
    :param event: a :class:`Event <zeitgeist.datamodel.Event>`

    :returns: a uri from a event's first subject
    """
    return event.subjects[0].uri

def get_timestamp(event):
    """
    :param event: a :class:`Event <zeitgeist.datamodel.Event>`

    :returns: a float event timestamp in miliseconds
    """
    return float(event.timestamp)

def get_event_icon(event, size):
    """
    Returns a icon from a event at size

    :param event: a :class:`Event <zeitgeist.datamodel.Event>`
    :param size: a int representing the size in pixels of the icon

    :returns: a :class:`Pixbuf <gtk.gdk.Pixbuf>`
    """
    gfile = GioFile.create(get_event_uri(event))
    if gfile:
        pb = gfile.get_icon(size=size)
        if pb:
            return pb
    return False

##
# Cairo drawing functions

def draw_frame(context, x, y, w, h):
    """
    Draws a 2 pixel frame around a area defined by x, y, w, h using a cairo context

    :param context: a cairo context
    :param x: x position of the frame
    :param y: y position of the frame
    :param w: width of the frame
    :param h: height of the frame
    """
    x, y = int(x)+0.5, int(y)+0.5
    w, h = int(w), int(h)
    context.set_line_width(1)
    context.rectangle(x-1, y-1, w+2, h+2)
    context.set_source_rgba(0.5, 0.5, 0.5)#0.3, 0.3, 0.3)
    context.stroke()
    context.set_source_rgba(0.7, 0.7, 0.7)
    context.rectangle(x, y, w, h)
    context.stroke()
    context.set_source_rgba(0.4, 0.4, 0.4)
    context.rectangle(x+1, y+1, w-2, h-2)
    context.stroke()

def draw_rounded_rectangle(context, x, y, w, h, r=5):
    """Draws a rounded rectangle

    :param context: a cairo context
    :param x: x position of the rectangle
    :param y: y position of the rectangle
    :param w: width of the rectangle
    :param h: height of the rectangle
    :param r: radius of the rectangle
    """
    context.new_sub_path()
    context.arc(r+x, r+y, r, math.pi, 3 * math.pi /2)
    context.arc(w-r+x, r+y, r, 3 * math.pi / 2, 0)
    context.arc(w-r+x, h-r+y, r, 0, math.pi/2)
    context.arc(r+x, h-r+y, r, math.pi/2, math.pi)
    context.close_path()
    return context

def draw_speech_bubble(context, layout, x, y, w, h):
    """
    Draw a speech bubble at a position

    Arguments:
    :param context: a cairo context
    :param layout: a pango layout
    :param x: x position of the bubble
    :param y: y position of the bubble
    :param w: width of the bubble
    :param h: height of the bubble
    """
    layout.set_width((w-10)*1024)
    layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
    textw, texth = layout.get_pixel_size()
    context.new_path()
    context.move_to(x + 0.45*w, y+h*0.1 + 2)
    context.line_to(x + 0.5*w, y)
    context.line_to(x + 0.55*w, y+h*0.1 + 2)
    h = max(texth + 5, h)
    draw_rounded_rectangle(context, x, y+h*0.1, w, h, r = 5)
    context.close_path()
    context.set_line_width(2)
    context.set_source_rgb(168/255.0, 165/255.0, 134/255.0)
    context.stroke_preserve()
    context.set_source_rgb(253/255.0, 248/255.0, 202/255.0)
    context.fill()
    pcontext = pangocairo.CairoContext(context)
    pcontext.set_source_rgb(0, 0, 0)
    pcontext.move_to(x+5, y+5)
    pcontext.show_layout(layout)

def draw_text(context, layout, markup, x, y, maxw = 0, color = (0.3, 0.3, 0.3)):
    """
    Draw text using a cairo context and a pango layout

    Arguments:
    :param context: a cairo context
    :param layout: a pango layout
    :param x: x position of the bubble
    :param y: y position of the bubble
    :param maxw: the max text width in pixels
    :param color: a rgb tuple
    """
    pcontext = pangocairo.CairoContext(context)
    layout.set_markup(markup)
    layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
    pcontext.set_source_rgba(*color)
    if maxw:
        layout.set_width(maxw*1024)
    pcontext.move_to(x, y)
    pcontext.show_layout(layout)

def render_pixbuf(window, x, y, pixbuf, drawframe = True):
    """
    Renders a pixbuf to be displayed on the cell

    Arguments:
    :param window: a gdk window
    :param x: x position
    :param y: y position
    :param drawframe: if true we draw a frame around the pixbuf
    """
    imgw, imgh = pixbuf.get_width(), pixbuf.get_height()
    context = window.cairo_create()
    context.rectangle(x, y, imgw, imgh)
    if drawframe:
        context.set_source_rgb(1, 1, 1)
        context.fill_preserve()
    context.set_source_pixbuf(pixbuf, x, y)
    context.fill()
    if drawframe: # Draw a pretty frame
        draw_frame(context, x, y, imgw, imgh)

def render_emblems(window, x, y, w, h, emblems):
    """
    Renders emblems on the four corners of the rectangle

    Arguments:
    :param window: a gdk window
    :param x: x position
    :param y: y position
    :param w: the width of the rectangle
    :param y: the height of the rectangle
    :param emblems: a list of pixbufs
    """
    # w = max(self.width, w)
    corners = [[x, y],
               [x+w, y],
               [x, y+h],
               [x+w, y+h]]
    context = window.cairo_create()
    for i in xrange(len(emblems)):
        i = i % len(emblems)
        pixbuf = emblems[i]
        if pixbuf:
            pbw, pbh = pixbuf.get_width()/2, pixbuf.get_height()/2
            context.set_source_pixbuf(pixbuf, corners[i][0]-pbw, corners[i][1]-pbh)
            context.rectangle(corners[i][0]-pbw, corners[i][1]-pbh, pbw*2, pbh*2)
            context.fill()

##
## Color functions

def shade_gdk_color(color, shade):
    """
    Shades a color by a fraction

    Arguments:
    :param color: a gdk color
    :param shade: fraction by which to shade the color

    :returns: a :class:`Color <gtk.gdk.Color>`
    """
    f = lambda num: min((num * shade, 65535.0))
    if gtk.pygtk_version >= (2, 16, 0):
        color.red = f(color.red)
        color.green = f(color.green)
        color.blue = f(color.blue)
    else:
        red = int(f(color.red))
        green = int(f(color.green))
        blue = int(f(color.blue))
        color = gtk.gdk.Color(red=red, green=green, blue=blue)
    return color

def combine_gdk_color(color, fcolor):
    """
    Combines a color with another color

    Arguments:
    :param color: a gdk color
    :param fcolor: a gdk color to combine with color

    :returns: a :class:`Color <gtk.gdk.Color>`
    """
    if gtk.pygtk_version >= (2, 16, 0):
        color.red = (2*color.red + fcolor.red)/3
        color.green = (2*color.green + fcolor.green)/3
        color.blue = (2*color.blue + fcolor.blue)/3
    else:
        red = int(((2*color.red + fcolor.red)/3))
        green = int(((2*color.green + fcolor.green)/3))
        blue = int(((2*color.blue + fcolor.blue)/3))
        color = gtk.gdk.Color(red=red, green=green, blue=blue)
    return color

def get_gtk_rgba(style, palette, i, shade = 1, alpha = 1):
    """Takes a gtk style and returns a RGB tuple

    Arguments:
    :param style: a gtk_style object
    :param palette: a string representing the palette you want to pull a color from
        Example: "bg", "fg"
    :param shade: how much you want to shade the color

    :returns: a rgba tuple
    """
    f = lambda num: (num/65535.0) * shade
    color = getattr(style, palette)[i]
    if isinstance(color, gtk.gdk.Color):
        red = f(color.red)
        green = f(color.green)
        blue = f(color.blue)
        return (min(red, 1), min(green, 1), min(blue, 1), alpha)
    else: raise TypeError("Not a valid gtk.gdk.Color")


##
## Pixbuff work
##

def new_grayscale_pixbuf(pixbuf):
    """
    Makes a pixbuf grayscale

    :param pixbuf: a :class:`Pixbuf <gtk.gdk.Pixbuf>`

    :returns: a :class:`Pixbuf <gtk.gdk.Pixbuf>`

    """
    pixbuf2 = pixbuf.copy()
    pixbuf.saturate_and_pixelate(pixbuf2, 0.0, False)
    return pixbuf2

def crop_pixbuf(pixbuf, x, y, width, height):
    """
    Crop a pixbuf

    Arguments:
    :param pixbuf: a :class:`Pixbuf <gtk.gdk.Pixbuf>`
    :param x: the x position to crop from in the source
    :param y: the y position to crop from in the source
    :param width: crop width
    :param height: crop height

    :returns: a :class:`Pixbuf <gtk.gdk.Pixbuf>`
    """
    dest_pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, width, height)
    pixbuf.copy_area(x, y, width, height, dest_pixbuf, 0, 0)
    return dest_pixbuf

def scale_to_fill(pixbuf, neww, newh):
    """
    Scales/crops a new pixbuf to a width and height at best fit and returns it

    Arguments:
    :param pixbuf: a :class:`Pixbuf <gtk.gdk.Pixbuf>`
    :param neww: new width of the new pixbuf
    :param newh: a new height of the new pixbuf

    :returns: a :class:`Pixbuf <gtk.gdk.Pixbuf>`
    """
    imagew, imageh = pixbuf.get_width(), pixbuf.get_height()
    if (imagew, imageh) != (neww, newh):
        imageratio = float(imagew) / float(imageh)
        newratio = float(neww) / float(newh)
        if imageratio > newratio:
            transformw = int(round(newh * imageratio))
            pixbuf = pixbuf.scale_simple(transformw, newh, gtk.gdk.INTERP_BILINEAR)
            pixbuf = crop_pixbuf(pixbuf, 0, 0, neww, newh)
        elif imageratio < newratio:
            transformh = int(round(neww / imageratio))
            pixbuf = pixbuf.scale_simple(neww, transformh, gtk.gdk.INTERP_BILINEAR)
            pixbuf = crop_pixbuf(pixbuf, 0, 0, neww, newh)
        else:
            pixbuf = pixbuf.scale_simple(neww, newh, gtk.gdk.INTERP_BILINEAR)
    return pixbuf


class PixbufCache(dict):
    """
    A pixbuf cache dict which stores, loads, and saves pixbufs to a cache and to
    the users filesystem. The naming scheme for thumb files are use hash

    There are huge flaws with this object. It does not have a ceiling, and it
    does not remove thumbnails from the file system. Essentially meaning the
    cache directory can grow forever.
    """
    def __init__(self, *args, **kwargs):
        super(PixbufCache, self).__init__()

    def check_cache(self, uri):
        return self[uri]

    def get_buff(self, key):
        thumbpath = os.path.expanduser("~/.cache/GAJ/1_" + str(hash(key)))
        if os.path.exists(thumbpath):
            self[key] = (gtk.gdk.pixbuf_new_from_file(thumbpath), True)
            return self[key]
        return None

    def __getitem__(self, key):
        if self.has_key(key):
            return super(PixbufCache, self).__getitem__(key)
        return self.get_buff(key)

    def __setitem__(self, key, (pb, isthumb)):
        dir_ = os.path.expanduser("~/.cache/GAJ/")
        if not os.path.exists(os.path.expanduser("~/.cache/GAJ/")):
            os.makedirs(dir_)
        path = dir_ + str(hash(isthumb)) + "_" + str(hash(key))
        if not os.path.exists(path):
            open(path, 'w').close()
            pb.save(path, "png")
        return super(PixbufCache, self).__setitem__(key, (pb, isthumb))

    def get_pixbuf_from_uri(self, uri, size=SIZE_LARGE, iconscale=1, w=0, h=0):
        """
        Returns a pixbuf and True if a thumbnail was found, else False. Uses the
        Pixbuf Cache for thumbnail compatible files. If the pixbuf is a thumb
        it is cached.

        Arguments:
        :param uri: a uri on the disk
        :param size: a size tuple from thumbfactory
        :param iconscale: a factor to reduce icons by (not thumbs)
        :param w: resulting width
        :param h: resulting height

        Warning! This function is in need of a serious clean up.

        :returns: a tuple containing a :class:`Pixbuf <gtk.gdk.Pixbuf>` and bool
        which is True if a thumbnail was found
        """
        try:
            cached = self.check_cache(uri)
        except gobject.GError:
            cached = None
        if cached:
            return cached
        gfile = GioFile.create(uri)
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
            pb = ICON_THEME.lookup_icon(gtk.STOCK_MISSING_IMAGE, int(size[0]*iconscale), gtk.ICON_LOOKUP_FORCE_SVG).load_icon()
            thumb = False
        if thumb:
            pb = scale_to_fill(pb, w, h)
            self[uri] = (pb, thumb)
        return pb, thumb

PIXBUFCACHE = PixbufCache()

def get_icon_for_name(name, size):
    """
    return a icon for a name
    """
    size = int(size)
    ICONS[(size, size)]
    if ICONS[(size, size)].has_key(name):
        return ICONS[(size, size)][name]
    info = ICON_THEME.lookup_icon(name, size, gtk.ICON_LOOKUP_USE_BUILTIN)
    if not info:
        return None
    location = info.get_filename()
    pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(location, size, size)
    ICONS[(size, size)][name] = pixbuf
    return pixbuf


##
## Other useful methods
##

def is_command_available(command):
    """
    Checks whether the given command is available, by looking for it in
    the PATH.

    This is useful for ensuring that optional dependencies on external
    applications are fulfilled.
    """
    assert len(" a".split()) == 1, "No arguments are accepted in command"
    for directory in os.environ["PATH"].split(os.pathsep):
        if os.path.exists(os.path.join(directory, command)):
            return True
    return False

def launch_command(command, arguments=None):
    """
    Launches a program as an independent process.
    """
    if not arguments:
        arguments = []
    null = os.open(os.devnull, os.O_RDWR)
    subprocess.Popen([command] + arguments, stdout=null, stderr=null,
                     close_fds=True)
