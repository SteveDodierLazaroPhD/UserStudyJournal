# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
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
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gio
import os
import collections
import zipfile
import gtk
import gnome.ui
import tempfile

try:
    import pygments
except ImportError:
    pygments = None
else:
    from pygments.lexers import get_lexer_for_filename, get_lexer_for_mimetype
    from pygments import highlight
    from pygments.formatters import ImageFormatter

THUMBS = collections.defaultdict(dict)
ICONS = collections.defaultdict(dict)
ICON_SIZES = SIZE_NORMAL, SIZE_LARGE = ((128, 128), (256, 256))
THUMBNAIL_FACTORIES = {
    SIZE_NORMAL: gnome.ui.ThumbnailFactory("normal"),
    SIZE_LARGE: gnome.ui.ThumbnailFactory("large")
}
ICON_THEME = gtk.icon_theme_get_default()

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
    
def crop_pixbuf(pixbuf, x, y, size=SIZE_LARGE):
    """ returns a part of the given pixbuf as new one """
    result = gtk.gdk.Pixbuf(pixbuf.get_colorspace(),
                            True,
                            pixbuf.get_bits_per_sample(),
                            size[0], size[1])
    pixbuf.copy_area(x, y, x+size[0], y+size[1], result, 0, 0)
    return result

def create_opendocument_thumb(path):
    """ extracts the thumbnail of an Opendocument document as pixbuf """
    thumb = tempfile.NamedTemporaryFile()
    try:
        f = zipfile.ZipFile(path, mode="r")
        try:
            thumb.write(f.read("Thumbnails/thumbnail.png"))
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
    
def create_text_thumb(gio_file, size=None, threshold=2):
    """ tries to use pygments to get a thumbnail of a text file """
    if pygments is None:
        return None
    try:
        lexer = get_lexer_for_mimetype(gio_file.mime_type)
    except pygments.util.ClassNotFound:
        lexer = get_lexer_for_mimetype("text/plain")
    thumb = tempfile.NamedTemporaryFile()
    formatter = ImageFormatter(font_name="DejaVu Sans Mono", line_numbers=False, font_size=10)
    # to speed things up only highlight the first 20 lines
    content = "\n".join(gio_file.get_content().split("\n")[:20])
    content = highlight(content, lexer, formatter)
    thumb.write(content)
    thumb.flush()
    thumb.seek(0)
    pixbuf = gtk.gdk.pixbuf_new_from_file(thumb.name)
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
            pixbuf = crop_pixbuf(pixbuf, 0, 0, (new_width or width, new_height or height))
    return pixbuf


class GioFile(object):
    
    @classmethod
    def create(cls, path):
        """ save method to create a GioFile object, if a file does not exist
        None is returned"""
        try:
            return cls(path)
        except gio.Error:
            return None
    
    def __init__(self, path):
        self._file_object = gio.File(path)
        self._file_info = self._file_object.query_info(
            "standard::content-type,standard::icon,time::modified")
            
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
                            thumb = create_text_thumb(self, size, 1)
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
            
    @property
    def thumbnail(self):
        return self.get_thumbnail()
        
    def get_monitor(self):
        return self._file_object.monitor_file()
        
    def refresh(self):
        self._file_info = self._file_object.query_info(
            "standard::content-type,standard::icon,time::modified")
        
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
                for icon in self.icon_names:
                    info = ICON_THEME.lookup_icon(icon, size, gtk.ICON_LOOKUP_USE_BUILTIN)
                    if info is None:
                        continue
                    location = info.get_filename()
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
