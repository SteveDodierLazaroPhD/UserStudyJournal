#! /usr/bin/env python
# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2009-2010 Siegfried Gevatter <siegfried@gevatter.com>
# Copyright © 2007 Alex Graveley <alex@beatniksoftware.com>
# Copyright © 2010 Markus Korn <thekorn@gmx.de>
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
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

from __future__ import with_statement
import cPickle
import gettext
import gobject
import os
import sys
import urllib
from xdg import BaseDirectory

try:
    from fungtk.quickconf import QuickConf
except:
    from quickconf import QuickConf

from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType


# Installation details
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(BASE_PATH, "data")
VERSION = "0.3.4.1"
GETTEXT_PATH = None

USER_DATA_PATH = BaseDirectory.save_data_path("gnome-activity-journal")
settings = QuickConf("/apps/gnome-activity-journal")

def _get_path(path):
    return os.path.join(BASE_PATH, path)

def get_data_path(path=None):
    return os.path.join(DATA_PATH, path) if path else DATA_PATH

def get_icon_path(path):
    for basepath in (DATA_PATH, "/usr/share/", "/usr/local/share",
        os.path.expanduser("~/.local/share")):
        newpath = os.path.join(basepath, "icons", path)
        if os.path.exists(newpath):
            return newpath
    return None

# When running from Bazaar, give priority to local translations
if os.path.isdir(_get_path("build/mo")):
    GETTEXT_PATH = _get_path("build/mo")


class Bookmarker(gobject.GObject):

    __gsignals__ = {
        "reload" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_PYOBJECT,))
        }

    # PUBLIC!
    bookmarks = []

    @staticmethod
    def event_exists(uri):
        # TODO: Move this into Zeitgeist's datamodel.py
        return not uri.startswith("file://") or os.path.exists(
            urllib.unquote(str(uri[7:])))

    def __init__(self):
        gobject.GObject.__init__(self)
        self.bookmarks_file = os.path.join(USER_DATA_PATH, "bookmarks.pickled")
        self._load()

    def _load(self):
        if os.path.isfile(self.bookmarks_file):
            try:
                with open(self.bookmarks_file) as f:
                    self.bookmarks = cPickle.load(f)
                    removable = []
                    for bookmark in self.bookmarks:
                        if not self.event_exists(bookmark):
                            removable.append(bookmark)
                    for uri in removable:
                        self.bookmarks.remove(uri)
            except:
                print "Pin database is corrupt."

    def _save(self):
        with open(self.bookmarks_file, "w") as f:
            cPickle.dump(self.bookmarks, f)

    def bookmark(self, uri):
        if not uri in self.bookmarks and self.event_exists(uri):
            self.bookmarks.append(uri)
        self._save()
        self.emit("reload", self.bookmarks)

    def unbookmark(self, uri):
        if uri in self.bookmarks:
            self.bookmarks.remove(uri)
        self._save()
        self.emit("reload", self.bookmarks)

    def is_bookmarked(self, uri):
        return uri in self.bookmarks


class Source(object):
    """A source which is used for category creation and verb/description storage for a given interpretation"""
    def __init__(self, interpretation, icon, desc_sing, desc_pl):
        self.name = interpretation.name
        self.icon = icon
        self._desc_sing = desc_sing
        self._desc_pl = desc_pl

    def group_label(self, num):
        return gettext.ngettext(self._desc_sing, self._desc_pl, num)


class PluginManager(object):
    """
    Loads a module and calls the module's main(client, store, window) function

    Where:
    client is a zeitgeist client
    store is a the backing Store which controls journal
    window is the Journal window


    All plugins must have a main function, a __plugin_name__ string, and a
    __description__ string
    """
    standard_plugins = []
    if settings.get("show_status_icon", False):
        standard_plugins.append("status_icon_plugin")

    def __init__(self, client, store, window):
        self.client = client
        self.store = store
        self.window = window
        self.load_plugs(self.standard_plugins, prefix="src.plugins.")
        plug_path = os.path.join(USER_DATA_PATH, "plugins")
        if os.path.exists(plug_path) and os.path.isdir(plug_path):
            sys.path.append(plug_path)
            user_plugs = []
            for module_file in os.listdir(plug_path):
                if module_file.endswith(".py"):
                    user_plugs.append(module_file.replace(".py", "").replace("-", "_"))
            self.load_plugs(user_plugs, level=0)

    def load_plugs(self, plugs, prefix="", level=-1):
        for plugin_name in plugs:
            print "Importing %s" % plugin_name
            try:
                plug_module = __import__(prefix + plugin_name, level=level, fromlist=[plugin_name])
                plug_module.main(self.client, self.store, self.window)
                print  plug_module.__plugin_name__ + " has been loaded"
            except Exception as e:
                print " Importing %s failed." % plugin_name, e


# Singletons and constants
bookmarker = Bookmarker()

SUPPORTED_SOURCES = {
    # TODO: Move this into Zeitgeist's library, implemented properly
    Interpretation.VIDEO.uri: Source(Interpretation.VIDEO, "gnome-mime-video", _("Worked with a Video"), _("Worked with Videos")),
    Interpretation.MUSIC.uri: Source(Interpretation.MUSIC, "gnome-mime-audio", _("Worked with Audio"), _("Worked with Audio")),
    Interpretation.IMAGE.uri: Source(Interpretation.IMAGE, "image", _("Worked with an Image"), _("Worked with Images")),
    Interpretation.DOCUMENT.uri: Source(Interpretation.DOCUMENT, "stock_new-presentation", _("Edited or Read Document"), _("Edited or Read Documents")),
    Interpretation.SOURCECODE.uri: Source(Interpretation.SOURCECODE, "applications-development", _("Edited or Read Code"), _("Edited or Read Code")),
    Interpretation.IM_MESSAGE.uri: Source(Interpretation.IM_MESSAGE, "applications-internet", _("Conversation"), _("Conversations")),
    Interpretation.EMAIL.uri: Source(Interpretation.EMAIL, "applications-internet", _("Email"), _("Emails")),
    Interpretation.UNKNOWN.uri: Source(Interpretation.UNKNOWN, "applications-other", _("Other Activity"), _("Other Activities")),
}
