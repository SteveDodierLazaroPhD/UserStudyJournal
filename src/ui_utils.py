# -.- coding: utf-8 -.-

# Zeitgeist
#
# Copyright © 2009 Seif Lotfy <seif@lotfy.com>
# Copyright © 2009 Siegfried Gevatter <siegfried@gevatter.com>
# Copyright © 2007 Alex Graveley <alex@beatniksoftware.com>
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

import os.path
import gobject
import urllib
import os
import gtk
import gnome.ui
import gettext
from fungtk.quickconf import QuickConf
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation

class Settings(gobject.GObject):
    
    __gsignals__ = {
        "change-view" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
        "change-insertions" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
        "toggle-time" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_BOOLEAN,)),
        "toggle-grouping" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }
    
    def __init__(self):
        
        gobject.GObject.__init__(self)
        
        self._conf = QuickConf('/apps/gnome-activity-journal')
        self.view = self._conf.get("view", "Journal")
        self.show_timestamps = self._conf.get("show_timestamps", False)
        self.compress_categories = {
            Interpretation.VIDEO.uri:  False,
            Interpretation.MUSIC.uri: False,
            Interpretation.IMAGE.uri: False,
            Interpretation.DOCUMENT.uri: False,
            Interpretation.SOURCECODE.uri: False,
            Interpretation.UNKNOWN.uri: False
        }
        
        # Connect to changes in gconf
        self._conf.connect("view",
            lambda key, value: self.set_view(value))
        self._conf.connect("show_timestamps",
            lambda key, value: self.toggle_time(value))
    
    def set_view(self, view):
        if view == self.view:
            return
        self.view = view
        self.emit("change-view", self.view)
        if not from_gconf:
            self._conf['view'] = view
    
    def set_insertions(self, insertions):
        self.insertions = insertions
        self.emit("change-insertions", self.view)
    
    def toggle_time(self, bool):
        if bool == self.show_timestamps:
            return
        self.show_timestamps = bool
        self.emit("toggle-time", self.show_timestamps)
        self._conf['show_timestamps'] = bool
    
    def toggle_compression(self, cat, bool):
        self.compress_categories[cat] = bool
        self.emit("toggle-grouping")



class LaunchManager:
    """
    A program lauching utility which handles opening a URI or executing a
    program or .desktop launcher, handling variable expansion in the Exec
    string.

    Adds the launched URI or launcher to the ~/.recently-used log. Sets a
    DESKTOP_STARTUP_ID environment variable containing useful information such
    as the URI which caused the program execution and a timestamp.

    See the startup notification spec for more information on
    DESKTOP_STARTUP_IDs.
    """
    
    def __init__(self):
        self.recent_model = None

    def _get_recent_model(self):
        # FIXME: This avoids import cycles
        if not self.recent_model:
            import zeitgeist_recent
            self.recent_model = zeitgeist_recent.recent_model
        return self.recent_model
    
    def launch_uri(self, uri, mimetype = None):
        assert uri, "Must specify URI to launch"
    
        child = os.fork()
        if not child:
            # Inside forked child
            os.setsid()
            os.environ['zeitgeist_LAUNCHER'] = uri
            os.environ['DESKTOP_STARTUP_ID'] = self.make_startup_id(uri)
            os.spawnlp(os.P_NOWAIT, "gnome-open", "gnome-open", uri)
            os._exit(0)
        else:
            os.wait()
            if not mimetype:
                mimetype = "application/octet-stream"
            try:
                # Use XDG to lookup mime type based on file name.
                # gtk_recent_manager_add_full requires it.
                import xdg.Mime
                mimetype = xdg.Mime.get_type_by_name(uri)
                if mimetype:
                    mimetype = str(mimetype)
                return mimetype
            except (ImportError, NameError):
                # No mimetype found for URI: %s
                pass
        return child
    
    def get_local_path(self, uri):
        scheme, path = urllib.splittype(uri)
        if scheme == None:
            return uri
        elif scheme == "file":
            path = urllib.url2pathname(path)
            if path[:3] == "///":
                path = path[2:]
            return path
        return None
    
    def launch_command_with_uris(self, command, uri_list, launcher_uri = None):
        if command.rfind("%U") > -1:
            uri_str = ""
            for uri in uri_list:
                uri_str = uri_str + " " + uri
                return self.launch_command(command.replace("%U", uri_str), launcher_uri)
        elif command.rfind("%F") > -1:
            file_str = ""
            for uri in uri_list:
                uri = self.get_local_path(self, uri)
                if uri:
                    file_str = file_str + " " + uri
                else:
                    # Command does not support non-file URLs
                    pass
            return self.launch_command(command.replace("%F", file_str), launcher_uri)
        elif command.rfind("%u") > -1:
            startup_ids = []
            for uri in uri_list:
                startup_ids.append(self.launch_command(command.replace("%u", uri), launcher_uri))
            else:
                return self.launch_command(command.replace("%u", ""), launcher_uri)
            return startup_ids
        elif command.rfind("%f") > -1:
            startup_ids = []
            for uri in uri_list:
                uri = self.get_local_path(self, uri)
                if uri:
                    startup_ids.append(self.launch_command(command.replace("%f", uri),
                                                           launcher_uri))
                else:
                    #print " !!! Command does not support non-file URLs: ", command
                    pass
            else:
                return self.launch_command(command.replace("%f", ""), launcher_uri)
            return startup_ids
        else:
            return self.launch_command(command, launcher_uri)
    
    def make_startup_id(self, key, ev_time = None):
        if not ev_time:
            ev_time = gtk.get_current_event_time()
        if not key:
            return "zeitgeist_TIME%d" % ev_time
        else:
            return "zeitgeist:%s_TIME%d" % (key, ev_time)

    def parse_startup_id(self, id):
        if id and id.startswith("zeitgeist:"):
            try:
                uri = id[len("zeitgeist:"):id.rfind("_TIME")]
                timestamp = id[id.rfind("_TIME") + len("_TIME"):]
                return (uri, timestamp)
            except IndexError:
                pass
        return (None, None)

    def launch_command(self, command, launcher_uri = None):
        startup_id = self.make_startup_id(launcher_uri)
        child = os.fork()
        if not child:
            # Inside forked child
            os.setsid()
            os.environ['DESKTOP_STARTUP_ID'] = startup_id
            if launcher_uri:
                os.environ['zeitgeist_LAUNCHER'] = launcher_uri
            os.system(command)
            os._exit(0)
        else:
            os.wait()
           
            return (child, startup_id)

class IconFactory():
    """
    Icon lookup swiss-army knife (from menutreemodel.py)
    """
    
    def __init__(self):
        self.icon_dict={}
    
    def load_icon_from_path(self, icon_path, icon_size=None):
        try:
            if icon_size:
                icon = gtk.gdk.pixbuf_new_from_file_at_size(icon_path,
                    int(icon_size), int(icon_size))
                return icon
            else:
                return gtk.gdk.pixbuf_new_from_file(icon_path)
        except Exception:
            pass
        return None
    
    def load_icon_from_data_dirs(self, icon_value, icon_size=None):
        data_dirs = None
        if os.environ.has_key("XDG_DATA_DIRS"):
            data_dirs = os.environ["XDG_DATA_DIRS"]
        if not data_dirs:
            data_dirs = "/usr/local/share/:/usr/share/"

        for data_dir in data_dirs.split(":"):
            retval = self.load_icon_from_path(os.path.join(data_dir, "pixmaps", icon_value),
                                              icon_size)
            if retval:
                return retval
            
            retval = self.load_icon_from_path(os.path.join(data_dir, "icons", icon_value),
                                              icon_size)
            if retval:
                return retval
        return None
    
    def transparentize(self, pixbuf, percent):
        pixbuf = pixbuf.add_alpha(False, '0', '0', '0')
        for row in pixbuf.get_pixels_array():
            for pix in row:
                pix[3] = min(int(pix[3]), 255 - (percent * 0.01 * 255))
        return pixbuf
    
    def greyscale(self, pixbuf):
        pixbuf = pixbuf.copy()
        for row in pixbuf.get_pixels_array():
            for pix in row:
                pix[0] = pix[1] = pix[2] = (int(pix[0]) + int(pix[1]) + int(pix[2])) / 3
        return pixbuf
    
    def load_icon(self, icon_value, icon_size, force_size=True, cache=True):
        if not self.icon_dict.has_key(str(icon_value)+str(icon_size)) or not cache:
            try:
                if isinstance(icon_value, gtk.gdk.Pixbuf):
                    return icon_value
                elif os.path.isabs(icon_value):
                    icon = self.load_icon_from_path(icon_value, icon_size)
                    if icon:
                        return icon
                    icon_name = os.path.basename(icon_value)
                else:
                    icon_name = icon_value
                
                if icon_name.endswith(".png"):
                    icon_name = icon_name[:-len(".png")]
                elif icon_name.endswith(".xpm"):
                    icon_name = icon_name[:-len(".xpm")]
                elif icon_name.endswith(".svg"):
                    icon_name = icon_name[:-len(".svg")]
                
                icon = None
                info = icon_theme.lookup_icon(icon_name, icon_size, gtk.ICON_LOOKUP_USE_BUILTIN)
                if info:
                    if icon_name.startswith("gtk-"):
                        icon = info.load_icon()
                    elif info.get_filename():
                        icon = self.load_icon_from_path(info.get_filename(), icon_size)
                else:
                    icon = self.load_icon_from_data_dirs(icon_value, icon_size) 
                
                if cache:
                    self.icon_dict[str(icon_value)+str(icon_size)] = icon
                return icon
            except Exception:
                self.icon_dict[str(icon_value)+str(icon_size)] = None
                return None
        else:
            return self.icon_dict[str(icon_value)+str(icon_size)]
    
    def load_image(self, icon_value, icon_size, force_size=True):
        pixbuf = self.load_icon(icon_value, icon_size, force_size)
        img = gtk.Image()
        img.set_from_pixbuf(pixbuf)
        img.show()
        return img

    def make_icon_frame(self, thumb, icon_size = None, blend = False):
        border = 1

        mythumb = gtk.gdk.Pixbuf(thumb.get_colorspace(),
                                 True,
                                 thumb.get_bits_per_sample(),
                                 thumb.get_width(),
                                 thumb.get_height())
        mythumb.fill(0x00000080) # black, 50% transparent
        if blend:
            thumb.composite(mythumb, 0.5, 0.5,
                            thumb.get_width(), thumb.get_height(),
                            0.5, 0.5,
                            0.5, 0.5,
                            gtk.gdk.INTERP_NEAREST,
                            256)
        thumb.copy_area(border, border,
                        thumb.get_width() - (border * 2), thumb.get_height() - (border * 2),
                        mythumb,
                        border, border)
        return mythumb
    
class Thumbnailer:
    
    def __init__(self):
        self.icon_dict={}

    def get_icon(self, subject, icon_size, timestamp = 0):
        
        uri = subject.uri
        if not self.icon_dict.get(uri+str(icon_size)):
            cached_icon = self._lookup_or_make_thumb(uri, subject.mimetype,
                icon_size, timestamp)
            self.icon_dict[uri+str(icon_size)] = cached_icon
        
        return self.icon_dict[uri+str(icon_size)]

    def _lookup_or_make_thumb(self, uri, mimetype, icon_size, timestamp):
        icon_name, icon_type = \
                   gnome.ui.icon_lookup(icon_theme, thumb_factory, uri, mimetype, 0)
        try:
            if icon_type == gnome.ui.ICON_LOOKUP_RESULT_FLAGS_THUMBNAIL or \
                   thumb_factory.has_valid_failed_thumbnail(uri,int(timestamp)):
                # Use existing thumbnail
                thumb = icon_factory.load_icon(icon_name, icon_size)
            elif self._is_local_uri(uri):
                # Generate a thumbnail for local files only
                thumb = thumb_factory.generate_thumbnail(uri, mimetype)
                thumb_factory.save_thumbnail(thumb, uri, timestamp)

            if thumb:
                thumb = icon_factory.make_icon_frame(thumb, icon_size)
                return thumb
            
        except Exception:
            pass

        return icon_factory.load_icon(icon_name, icon_size)

    def _is_local_uri(self, uri):
        # NOTE: gnomevfs.URI.is_local seems to hang for some URIs (e.g. ssh
        #        or http).  So look in a list of local schemes which comes
        #        directly from gnome_vfs_uri_is_local_scheme.
        scheme, path = urllib.splittype(self.get_uri() or "")
        return not scheme or scheme in ("file", "help", "ghelp", "gnome-help", "trash",
                                        "man", "info", "hardware", "search", "pipe",
                                        "gnome-trash")

class CellRendererPixbuf(gtk.CellRendererPixbuf):
    
    __gsignals__ = {
        'toggled': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
        (gobject.TYPE_STRING,))
    }
    def __init__(self):
        gtk.CellRendererPixbuf.__init__(self)
        self.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
    
    def do_activate(self, event, widget, path, background_area, cell_area, flags):
        model = widget.get_model()
        self.emit("toggled",path)

def get_category_icon(icon, size=24):
    try:
        return icon_theme.load_icon (icon, size, 0)
    except:
        return None
    

icon_theme = gtk.icon_theme_get_default()
icon_factory = IconFactory()
thumbnailer = Thumbnailer()
thumb_factory = gnome.ui.ThumbnailFactory("normal")
launcher = LaunchManager()
settings = Settings()

class Source:
    
    def __init__(self, interpretation, icon, desc_sing, desc_pl):
        self.name = interpretation.name
        self.icon = icon
        self._desc_sing = desc_sing
        self._desc_pl = desc_pl
    
    def group_label(self, num):
        return gettext.ngettext(self._desc_sing, self._desc_pl, num)

SUPPORTED_SOURCES = {
    # TODO: Please change this description stuff. To give a single reason,
    # saying "videos watched" is a lie because you may have edited them, or
    # it may just be a "bookmark event".
    #
    # Also, how this is implemented now won't work fine with i18n.
    Interpretation.VIDEO.uri: Source(Interpretation.VIDEO, "gnome-mime-video", "video watched", "videos watched"),
    Interpretation.MUSIC.uri: Source(Interpretation.MUSIC, "gnome-mime-audio", "audio heard", "audios heard"),
    Interpretation.IMAGE.uri: Source(Interpretation.IMAGE, "image", "image viewed", "images viewed"),
    Interpretation.DOCUMENT.uri: Source(Interpretation.DOCUMENT, "stock_new-presentation", "document edited or read", "documents edited or read"),
    Interpretation.SOURCECODE.uri: Source(Interpretation.SOURCECODE, "applications-development", "source file edited or read", "source files edited or read"),
    Interpretation.UNKNOWN.uri: Source(Interpretation.UNKNOWN, "applications-other", "other activity", "other activites"),
}
