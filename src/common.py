# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
# Copyright © 2010 Siegfried Gevatter <siegfried@gevatter.com>
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
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Common Functions and classes which are used to create the alternative views,
and handle colors, pixbufs, and text
"""

import cairo
import collections
import gobject
import gettext
import gio
import gnome.ui
import glib
import gtk
import os
import pango
import pangocairo
import time
import math
import operator
import subprocess
import tempfile
import urllib
import zipfile

try:
    import pygments
except ImportError:
    pygments = None
else:
    from pygments.lexers import get_lexer_for_filename, get_lexer_for_mimetype
    from pygments import highlight
    from pygments.formatters import ImageFormatter

try:
    import chardet
except ImportError:
    chardet = None

from config import get_data_path, get_icon_path, INTERPRETATION_UNKNOWN, MANIFESTATION_UNKNOWN

from zeitgeist.datamodel import Interpretation, Event, Subject


THUMBS = collections.defaultdict(dict)
ICONS = collections.defaultdict(dict)
ICON_SIZES = SIZE_NORMAL, SIZE_LARGE = ((128, 128), (256, 256))

# Thumbview and Timelineview sizes
SIZE_THUMBVIEW = [(48, 36), (96, 72), (150, 108), (256, 192)]
SIZE_TIMELINEVIEW = [(16,12), (32, 24), (64, 48), (128, 96)] 
SIZE_TEXT_TIMELINEVIEW = ["small", "medium", "large", "x-large"]
SIZE_TEXT_THUMBVIEW = ["x-small", "small", "large", "xx-large"]

THUMBNAIL_FACTORIES = {
    SIZE_NORMAL: gnome.ui.ThumbnailFactory("normal"),
    SIZE_LARGE: gnome.ui.ThumbnailFactory("large")
}
ICON_THEME = gtk.icon_theme_get_default()

#FIXME i know it's ugly. Btw this is only a temp solution. It will be removed
# when we'll revamp the Multiview view.----sorry----cando
IN_ERASE_MODE = False

# Caches desktop files
DESKTOP_FILES = {}
DESKTOP_FILE_PATHS = []
try:
    desktop_file_paths = os.environ["XDG_DATA_DIRS"].split(":")
    for path in desktop_file_paths:
        if path.endswith("/"):
            DESKTOP_FILE_PATHS.append(path + "applications/")
        else:
            DESKTOP_FILE_PATHS.append(path + "/applications/")
except KeyError:pass

# Placeholder pixbufs for common sizes
PLACEHOLDER_PIXBUFFS = {
    24 : gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path("hicolor/scalable/apps/gnome-activity-journal.svg"), 24, 24),
    16 : gtk.gdk.pixbuf_new_from_file_at_size(get_icon_path("hicolor/scalable/apps/gnome-activity-journal.svg"), 16, 16)
    }

# Color magic
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
    Interpretation.AUDIO.uri : 3,
    Interpretation.DOCUMENT.uri : 12,
    Interpretation.IMAGE.uri : 15,
    Interpretation.SOURCE_CODE.uri : 12,
    INTERPRETATION_UNKNOWN : 21,
    Interpretation.IMMESSAGE.uri : 21,
    Interpretation.EMAIL.uri : 21
}

FILETYPESNAMES = {
    Interpretation.VIDEO.uri : _("Video"),
    Interpretation.AUDIO.uri : _("Music"),
    Interpretation.DOCUMENT.uri : _("Document"),
    Interpretation.IMAGE.uri : _("Image"),
    Interpretation.SOURCE_CODE.uri : _("Source Code"),
    INTERPRETATION_UNKNOWN : _("Unknown"),
    Interpretation.IMMESSAGE.uri : _("IM Message"),
    Interpretation.EMAIL.uri :_("Email"),

}

INTERPRETATION_PARENTS = {
    Interpretation.DOCUMENT.uri : Interpretation.DOCUMENT.uri,
    Interpretation.TEXT_DOCUMENT.uri : Interpretation.DOCUMENT.uri,
    Interpretation.PAGINATED_TEXT_DOCUMENT.uri : Interpretation.DOCUMENT.uri,
    Interpretation.RASTER_IMAGE.uri : Interpretation.IMAGE.uri,
    Interpretation.VECTOR_IMAGE.uri : Interpretation.IMAGE.uri,
    Interpretation.IMAGE.uri : Interpretation.IMAGE.uri,
    Interpretation.AUDIO.uri : Interpretation.AUDIO.uri,
    Interpretation.MUSIC_PIECE.uri : Interpretation.MUSIC_PIECE.uri,
}

MEDIAINTERPRETATIONS = [
    Interpretation.VIDEO.uri,
    Interpretation.IMAGE.uri,
]

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
    
def get_text_or_uri(obj, ellipsize=True, molteplicity=False):
    if molteplicity and obj.molteplicity:
        text = obj.molteplicity_text
    else:
        text = unicode(obj.text.replace("&", "&amp;"))
    if text.strip() == "":
        text = unicode(obj.uri.replace("&", "&amp;"))
        text = urllib.unquote(text)
    if len(text) > 50 and ellipsize: text = text[:50] + "..." #ellipsize--it's ugly!
    return text

##
## Zeitgeist event helper functions

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
    layout.set_ellipsize(pango.ELLIPSIZE_END)
    pcontext.set_source_rgba(*color)
    if maxw:
        layout.set_width(maxw*1024)
    pcontext.move_to(x, y)
    pcontext.show_layout(layout)

def render_pixbuf(window, x, y, pixbuf, w, h, drawframe = True):
    """
    Renders a pixbuf to be displayed on the cell

    Arguments:
    :param window: a gdk window
    :param x: x position
    :param y: y position
    :param drawframe: if true we draw a frame around the pixbuf
    """
    context = window.cairo_create()
    context.save()
    context.rectangle(x, y, w, h)
    if drawframe:
        context.set_source_rgb(1, 1, 1)
        context.fill_preserve()
    context.set_source_pixbuf(pixbuf, x, y)
    context.clip()
    context.paint()
    context.restore();
    if drawframe: # Draw a pretty frame
        draw_frame(context, x, y, w, h)

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
               [x+w-4, y+h-4]]
    context = window.cairo_create()
    for i in xrange(len(emblems)):
        i = i % len(emblems)
        pixbuf = emblems[i]
        if pixbuf:
            pbw, pbh = pixbuf.get_width()/2, pixbuf.get_height()/2
            context.set_source_pixbuf(pixbuf, corners[i][0]-pbw, corners[i][1]-pbh)
            context.rectangle(corners[i][0]-pbw, corners[i][1]-pbh, pbw*2, pbh*2)
            context.fill()
            
def render_molteplicity(window, x, y, w, h, molteplicity):
    """
    Renders the molteplicity number on the top-right corner of the rectangle

    Arguments:
    :param window: a gdk window
    :param x: x position
    :param y: y position
    :param w: the width of the rectangle
    :param y: the height of the rectangle
    :param emblems: the molteplicity number
    """    
    radius = 10
    center = [x + w, y ]           
    context = window.cairo_create()
    context.set_source_rgb(0.9, 0.9, 0.8)
    context.arc(center[0], center[1], radius , 0, 2 * math.pi)
    context.fill_preserve()
    context.set_source_rgb(1, 0.5, 0.2)
    context.stroke()
    
    context.set_source_rgb(0.1, 0.1, 0.1)
    context.select_font_face("Serif", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_BOLD)
    context.set_font_size(radius)
    x_bearing, y_bearing, width, height = context.text_extents(str(molteplicity))[:4]
    context.move_to(center[0] - width / 2 - x_bearing, center[1] - height / 2 - y_bearing)
    context.show_text(str(molteplicity))
        

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

def make_icon_frame(pixbuf, blend=False, border=1, color=0x000000ff):
    """creates a new Pixmap which contains 'pixbuf' with a border at given
    size around it."""
    result = gtk.gdk.Pixbuf(pixbuf.get_colorspace(),
                            True,
                            pixbuf.get_bits_per_sample(),
                            pixbuf.get_width(),
                            pixbuf.get_height())
    result.fill(color)
    if blend:
        pixbuf.composite(result, 0.5, 0.5,
                        pixbuf.get_width(), pixbuf.get_height(),
                        0.5, 0.5,
                        0.5, 0.5,
                        gtk.gdk.INTERP_NEAREST,
                        256)
    pixbuf.copy_area(border, border,
                    pixbuf.get_width() - (border * 2), pixbuf.get_height() - (border * 2),
                    result,
                    border, border)
    return result

def add_background(pixbuf, color=0xffffffff):
    """ adds a background with given color to the pixbuf and returns the result
    as new Pixbuf"""
    result = gtk.gdk.Pixbuf(pixbuf.get_colorspace(),
                            True,
                            pixbuf.get_bits_per_sample(),
                            pixbuf.get_width(),
                            pixbuf.get_height())
    result.fill(color)
    pixbuf.composite(result, 0, 0,
                        pixbuf.get_width(), pixbuf.get_height(),
                        0, 0,
                        1, 1,
                        gtk.gdk.INTERP_NEAREST,
                        255)
    return result

def create_opendocument_thumb(path):
    """ extracts the thumbnail of an Opendocument document as pixbuf """
    thumb = tempfile.NamedTemporaryFile()
    try:
        f = zipfile.ZipFile(path, mode="r")
        try:
            thumb.write(f.read("Thumbnails/thumbnail.png"))
        except KeyError:
            thumb.close()
            return None
        finally:
            f.close()
    except IOError:
        thumb.close()
        return None
    thumb.flush()
    thumb.seek(0)
    pixbuf = gtk.gdk.pixbuf_new_from_file(thumb.name)
    thumb.close()
    return add_background(pixbuf)

def __crop_pixbuf(pixbuf, x, y, size=SIZE_LARGE):
    """ returns a part of the given pixbuf as new one """
    result = gtk.gdk.Pixbuf(pixbuf.get_colorspace(),
                            True,
                            pixbuf.get_bits_per_sample(),
                            size[0], size[1])
    pixbuf.copy_area(x, y, x+size[0], y+size[1], result, 0, 0)
    return result

def create_text_thumb(gio_file, size=None, threshold=2):
    """ tries to use pygments to get a thumbnail of a text file """
    if pygments is None:
        return None
    try:
        lexer = get_lexer_for_mimetype(gio_file.mime_type)
    except pygments.util.ClassNotFound:
        lexer = get_lexer_for_mimetype("text/plain")
    if chardet:
        lexer.encoding = "chardet"
    thumb = tempfile.NamedTemporaryFile()
    formatter = ImageFormatter(font_name="DejaVu Sans Mono", line_numbers=False, font_size=10)
    # to speed things up only highlight the first 20 lines
    content = "\n".join(gio_file.get_content().split("\n")[:20])
    try:
        content = highlight(content, lexer, formatter)
    except (UnicodeDecodeError, TypeError):
        # we can't create the pixbuf
        return None
    thumb.write(content)
    thumb.flush()
    thumb.seek(0)
    try:
        pixbuf = gtk.gdk.pixbuf_new_from_file(thumb.name)
    except glib.GError:
        return None # (LP: #743125)
    thumb.close()
    if size is not None:
        new_height = None
        new_width = None
        height = pixbuf.get_height()
        width = pixbuf.get_width()
        if width > threshold*size[0]:
            new_width = threshold*size[0]
        if height > threshold*size[1]:
            new_height = threshold*size[1]
        if new_height is not None or new_width is not None:
            pixbuf = __crop_pixbuf(pixbuf, 0, 0, (new_width or width, new_height or height))
    return pixbuf


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
    the users filesystem. The naming scheme for thumb files is based on hash()

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

    def get_pixbuf_from_uri(self, uri, size=SIZE_LARGE, iconscale=1):
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
                if pb is None and "audio-x-generic" in gfile.icon_names:
                    pb = gfile.get_icon(size=SIZE_NORMAL[0])
                    thumb = False
            else:
                pb = gfile.get_icon(size=SIZE_NORMAL[0])
                thumb = False
        else: pb = None
        if not pb:
            pb = ICON_THEME.lookup_icon(gtk.STOCK_MISSING_IMAGE, SIZE_NORMAL[0], gtk.ICON_LOOKUP_FORCE_SVG).load_icon()
            thumb = False
        if thumb:
            if "audio-x-generic" in gfile.icon_names: thumb = False
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
    return get_icon_for_uri(location, size)

def get_icon_for_uri(uri, size):
    if uri in ICONS[(size, size)]:
        return ICONS[(size, size)][uri]
    pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(uri, size, size)
    ICONS[(size, size)][uri] = pixbuf
    return pixbuf

def get_icon_from_object_at_uri(uri, size):
    """
    Returns a icon from a event at size

    :param uri: a uri string
    :param size: a int representing the size in pixels of the icon

    :returns: a :class:`Pixbuf <gtk.gdk.Pixbuf>`
    """
    gfile = GioFile.create(uri)
    if gfile:
        pb = gfile.get_icon(size=size)
        if pb:
            return pb
    return False


##
## Other useful methods
##

def get_menu_item_with_stock_id_and_text(stock_id, text):
    item = gtk.ImageMenuItem(stock_id)
    label = item.get_children()[0]
    label.set_text(text)
    return item


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

def launch_string_command(command):
    """
    Launches a program as an independent from a string
    """
    command = command.split(" ")
    null = os.open(os.devnull, os.O_RDWR)
    subprocess.Popen(command, stdout=null, stderr=null,
                     close_fds=True)

##
## GioFile
##

GIO_FILES = {}

class GioFile(object):

    def __new__(classtype, *args, **kwargs):
        # Check to see if a __single exists already for this class
        # Compare class types instead of just looking for None so
        # that subclasses will create their own __single objects
        subj = args[0][1][0][0]
        if not GIO_FILES.has_key(subj):
            GIO_FILES[subj] = object.__new__(classtype)
        return GIO_FILES[subj]

    @classmethod
    def create(cls, path):
        """ save method to create a GioFile object, if a file does not exist
        None is returned"""
        try:
            if not GIO_FILES.has_key(path):
                GIO_FILES[path] = cls(path)
            return GIO_FILES[path]
        except gio.Error:
            return None

    def __init__(self, path):
        self._file_object = gio.File(path)
        self._file_info = self._file_object.query_info(
            "standard::content-type,standard::icon,time::modified")
        self._file_annotation = self._file_object.query_info("metadata::annotation")

    @property
    def mime_type(self):
        return self._file_info.get_attribute_string("standard::content-type")

    @property
    def mtime(self):
        return self._file_info.get_attribute_uint64("time::modified")

    @property
    def basename(self):
        return self._file_object.get_basename()

    @property
    def uri(self):
        return self._file_object.get_uri()
        
    def get_annotation(self):
        self.refresh_annotation()
        return self._file_annotation.get_attribute_as_string("metadata::annotation")
        
    def set_annotation(self, annotation):
        self._file_annotation.set_attribute_string("metadata::annotation", annotation)
        self._file_object.set_attributes_from_info(self._file_annotation)
        
    annotation = property(get_annotation, set_annotation)

    def get_content(self):
        f = open(self._file_object.get_path())
        try:
            content = f.read()
        finally:
            f.close()
        return content

    @property
    def icon_names(self):
        try:
            return self._file_info.get_attribute_object("standard::icon").get_names()
        except AttributeError:
            return list()

    def get_thumbnail(self, size=SIZE_NORMAL, border=0):
        assert size in ICON_SIZES
        try:
            thumb = THUMBS[size][self.uri]
        except KeyError:
            factory = THUMBNAIL_FACTORIES[size]
            location = factory.lookup(self.uri, self.mtime)
            if location:
                thumb, mtime = THUMBS[size][self.uri] = \
                    (gtk.gdk.pixbuf_new_from_file(location), self.mtime)
            else:
                if factory.has_valid_failed_thumbnail(self.uri, self.mtime):
                    thumb = THUMBS[size][self.uri] = None
                else:
                    thumb = factory.generate_thumbnail(self.uri, self.mime_type)
                    if thumb is None:
                        # maybe we are able to use a custom thumbnailer here
                        if filter(lambda name: "application-vnd.oasis.opendocument" in name, self.icon_names):
                            thumb = create_opendocument_thumb(self._file_object.get_path())
                        elif "text-x-generic" in self.icon_names or "text-x-script" in self.icon_names:
                            try:
                                thumb = create_text_thumb(self, size, 1)
                            except Exception:
                                thumb = None
                        elif "audio-x-generic" in self.icon_names:
                            pass
                            #FIXME
                            #thumb = self.get_audio_cover(size)
                    if thumb is None:
                        factory.create_failed_thumbnail(self.uri, self.mtime)
                    else:
                        width, height = thumb.get_width(), thumb.get_height()
                        if width > size[0] or height > size[1]:
                            scale = min(float(size[0])/width, float(size[1])/height)
                            thumb = gnome.ui.thumbnail_scale_down_pixbuf(
                                thumb, int(scale*width), int(scale*height))
                        factory.save_thumbnail(thumb, self.uri, self.mtime)
                        THUMBS[size][self.uri] = (thumb, self.mtime)
        else:
            if thumb is not None:
                if thumb[1] != self.mtime:
                    del THUMBS[size][self.uri]
                    return self.get_thumbnail(size, border)
                thumb = thumb[0]
        if thumb is not None and border:
            thumb = make_icon_frame(thumb, border=border, color=0x00000080)
        return thumb
        
    def get_audio_cover(self, size):
        """
        Try to get a cover art in the folder of the song.
        It's s simple hack, but i think it's a good and quick compromise.
        """
        pix = None
        dirname = os.path.dirname(self.event.subjects[0].uri)
        dirname = urllib.unquote(dirname)[7:]
        if not os.path.exists(dirname): return pix
        for f in os.listdir(dirname):
            if f.endswith(".jpg") or f.endswith(".jpeg"): 
                path = dirname + os.sep + f
                pix = gtk.gdk.pixbuf_new_from_file(path)            
                return pix
                
        return pix

    @property
    def thumbnail(self):
        return self.get_thumbnail()

    def get_monitor(self):
        return self._file_object.monitor_file()

    def refresh(self):
        self._file_info = self._file_object.query_info(
            "standard::content-type,standard::icon,time::modified")
            
    def refresh_annotation(self):
        self._file_annotation = self._file_object.query_info("metadata::annotation")

    def get_icon(self, size=24, can_thumb=False, border=0):
        icon = None
        if can_thumb:
            # let's try to find a thumbnail
            # we only allow thumbnails as icons for a few content types
            if self.thumb_icon_allowed():
                if size < SIZE_NORMAL:
                    thumb_size = SIZE_NORMAL
                else:
                    thumb_size = SIZE_LARGE
                thumb = self.get_thumbnail(size=thumb_size)
                if thumb:
                    s = float(size)
                    width = thumb.get_width()
                    height = thumb.get_height()
                    scale = min(s/width, s/height)
                    icon = thumb.scale_simple(int(width*scale), int(height*scale), gtk.gdk.INTERP_NEAREST)
        if icon is None:
            try:
                return ICONS[size][self.uri]
            except KeyError:
                for name in self.icon_names:
                    info = ICON_THEME.lookup_icon(name, size, gtk.ICON_LOOKUP_USE_BUILTIN)
                    if info is None:
                        continue
                    location = info.get_filename()
                    if not location:
                        continue # (LP: #722227)
                    icon = gtk.gdk.pixbuf_new_from_file_at_size(location, size, size)
                    if icon:
                        break
        ICONS[size][self.uri] = icon
        if icon is not None and border:
            icon = make_icon_frame(icon, border=border, color=0x00000080)
        return icon

    @property
    def icon(self):
        return self.get_icon()

    def launch(self):
        appinfo = gio.app_info_get_default_for_type(self.mime_type, False)
        appinfo.launch([self._file_object,], None)

    def has_preview(self):
        icon_names = self.icon_names
        is_opendocument = filter(lambda name: "application-vnd.oasis.opendocument" in name, icon_names)
        return "video-x-generic" in icon_names \
            or "image-x-generic" in icon_names \
            or "audio-x-generic" in icon_names \
            or "application-pdf" in icon_names \
            or (("text-x-generic" in icon_names or "text-x-script" in icon_names) and pygments is not None) \
            or is_opendocument

    def thumb_icon_allowed(self):
        icon_names = self.icon_names
        is_opendocument = filter(lambda name: "application-vnd.oasis.opendocument" in name, icon_names)
        return "video-x-generic" in icon_names \
            or "image-x-generic" in icon_names \
            or "application-pdf" in icon_names \
            or is_opendocument

    def __eq__(self, other):
        if not isinstance(other, GioFile):
            return False
        return self.uri == other.uri

class DayParts:

    # TODO: In a future, I'd be cool to make the day partitions configurable.
    # This includes redefining what Morning/Afternoon/etc. are, but also
    # changing the categories entirely (eg. "Work", "Lunch time", etc.).
    # For this get_day_parts and other methods should take a timestamp of
    # the relevant day so they can account for weekends not having "Work", etc.

    TIMELABELS = [_("Morning"), _("Afternoon"), _("Evening")]
    CHANGEHOURS = [0, 12, 18]

    @classmethod
    def _local_minimum(cls, hour):
        for i in xrange(1, len(cls.CHANGEHOURS)):
            if hour < cls.CHANGEHOURS[i]:
                return i - 1
        return len(cls.CHANGEHOURS) - 1

    @classmethod
    def get_day_parts(cls):
        return cls.TIMELABELS

    @classmethod
    def get_day_part_for_item(cls, item):
        t = time.localtime(int(item.event.timestamp) / 1000)
        return cls._local_minimum(t.tm_hour)

    @classmethod
    def get_day_part_range_for_item(cls, item):
        start = list(time.localtime(int(item.event.timestamp) / 1000))
        i = cls._local_minimum(start[3])
        start[3] = cls.CHANGEHOURS[i] # Reset hour
        start[4] = start[5] = 0 # Reset minutes and seconds
        end = list(start)
        end[3] = cls.CHANGEHOURS[i+1] if len(cls.CHANGEHOURS) > (i + 1) else 23
        end[4] = end[5] = 59
        return time.mktime(start) * 1000, time.mktime(end) * 1000

def ignore_exceptions(return_value_on_failure=None):
    def wrap(f):
        def safe_method(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception, e:
                from traceback import print_exc
                print '\n --- Error running %s ---' % f.__name__
                print_exc()
                print
                return return_value_on_failure
        return safe_method
    return wrap
