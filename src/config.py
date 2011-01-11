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

# Legacy issues
INTERPRETATION_UNKNOWN = "" # "http://zeitgeist-project.com/schema/1.0/core#UnknownInterpretation"
MANIFESTATION_UNKNOWN = "" # "http://zeitgeist-project.com/schema/1.0/core#UnknownManifestation"
INTERPRETATION_NOTE = "aj://note"
INTERPRETATION_VCS = "aj://vcs" #version control system

# Installation details
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(BASE_PATH, "data")
VERSION = "0.5.0.1"
GETTEXT_PATH = None

USER_DATA_PATH = BaseDirectory.save_data_path("gnome-activity-journal")

PLUGIN_PATH = os.path.join(BASE_PATH, "src/plugins")
if not os.path.exists(PLUGIN_PATH) or not os.path.isdir(PLUGIN_PATH):
    PLUGIN_PATH = None
USER_PLUGIN_PATH = os.path.join(USER_DATA_PATH, "plugins")
if not os.path.exists(USER_PLUGIN_PATH) or not os.path.isdir(USER_PLUGIN_PATH):
    USER_PLUGIN_PATH = None

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

def event_exists(uri):
    # TODO: Move this into Zeitgeist's datamodel.py
    return not uri.startswith("file://") or os.path.exists(
        urllib.unquote(str(uri[7:])))

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
                        if not event_exists(bookmark):
                            removable.append(bookmark)
                    for uri in removable:
                        self.bookmarks.remove(uri)
            except:
                print "Pin database is corrupt."

    def _save(self):
        with open(self.bookmarks_file, "w") as f:
            cPickle.dump(self.bookmarks, f)

    def bookmark(self, uri):
        if not uri in self.bookmarks and event_exists(uri):
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
        if not isinstance(interpretation, str):
            self.name = interpretation.name
        else:
            self.name = interpretation
        self.icon = icon
        self._desc_sing = desc_sing
        self._desc_pl = desc_pl

    def group_label(self, num):
        return gettext.ngettext(self._desc_sing, self._desc_pl, num)


class PluginManager(object):
    """
    Loads a module and calls the module's activate(client, store, window) function

    Where:
    client is a zeitgeist client
    store is a the backing Store which controls journal
    window is the Journal window

    All plugins must have:
    func activate(client, store, window): build up when the plugin is enabled
    func deactivate(client, store, window): tear down when the plugin is disabled
    str __plugin_name__: plugin name
    str __description__: description of the plugin
    """
    plugin_settings = QuickConf("/apps/gnome-activity-journal/plugins")

    def __init__(self, client, store, window):
        self.plugins = {}
        self.client = client
        self.store = store
        self.window = window
        # Base plugins
        self.load_path(PLUGIN_PATH)
        self.load_path(USER_PLUGIN_PATH)

    def load_path(self, path):
        if path:
            sys.path.append(path)
            plugs = []
            for module_file in os.listdir(path):
                if module_file.endswith(".py") and module_file != "__init__.py":
                    modname = module_file.replace(".py", "").replace("-", "_")
                    plugs.append(modname)
            self.get_plugins(plugs, level=0)

    def get_plugins(self, plugin_names, prefix="", level=-1):
        plugs = self.import_plugins(plugin_names, prefix=prefix, level=level)
        self.load_plugins(plugs)

    def import_plugins(self, plugs, prefix="", level=-1):
        plugins = []
        for plugin_name in plugs:
            try:
                plugin_module = __import__(prefix + plugin_name, level=level, fromlist=[plugin_name])
                plugins.append((plugin_name, plugin_module))
                self.plugins[plugin_name] = plugin_module
                # print  plugin_module.__plugin_name__ + " has been imported"
            except Exception, e:
                print " Importing %s failed." % plugin_name, e
        return plugins

    def load_plugins(self, plugins):
        for plugin_name, plugin_module in plugins:
            try:
                state = self.plugin_settings.get(plugin_name, False)
                if not state: continue # If the plugin is not True it will not be loaded
                self.activate(plugin_module)
            except Exception, e:
                print "Loading %s failed." % plugin_name, e

    def __get_plugin_from_name(self, plugin=None, name=None):
        if not plugin:
            plugin = self.plugins[name]
        elif not plugin and not name:
            raise TypeError("You must pass either a plugin or a plugin_name")
        return plugin

    def activate(self, plugin=None, name=None):
        plugin = self.__get_plugin_from_name(plugin, name)
        plugin.activate(self.client, self.store, self.window)
        print "Activating %s" % plugin.__plugin_name__

    def deactivate(self, plugin=None, name=None):
        plugin = self.__get_plugin_from_name(plugin, name)
        plugin.deactivate(self.client, self.store, self.window)
        print "Deactivating %s" % plugin.__plugin_name__



# Singletons and constants
bookmarker = Bookmarker()

SUPPORTED_SOURCES = {
    # TODO: Move this into Zeitgeist's library, implemented properly
    Interpretation.VIDEO.uri: Source(Interpretation.VIDEO, "gnome-mime-video", _("Worked with a Video"), _("Worked with Videos")),
    Interpretation.AUDIO.uri: Source(Interpretation.AUDIO, "gnome-mime-audio", _("Worked with Audio"), _("Worked with Audio")),
    Interpretation.IMAGE.uri: Source(Interpretation.IMAGE, "image", _("Worked with an Image"), _("Worked with Images")),
    Interpretation.DOCUMENT.uri: Source(Interpretation.DOCUMENT, "stock_new-presentation", _("Edited or Read Document"), _("Edited or Read Documents")),
    Interpretation.SOURCE_CODE.uri: Source(Interpretation.SOURCE_CODE, "applications-development", _("Edited or Read Code"), _("Edited or Read Code")),
    Interpretation.IMMESSAGE.uri: Source(Interpretation.IMMESSAGE, "applications-internet", _("Conversation"), _("Conversations")),
    Interpretation.WEBSITE.uri: Source(Interpretation.WEBSITE, "gnome-mime-html", _("Visited Website"), _("Visited Websites")),
    Interpretation.EMAIL.uri: Source(Interpretation.EMAIL, "applications-internet", _("Email"), _("Emails")),
    Interpretation.TODO.uri: Source(Interpretation.TODO, "applications-office", _("Todo"), _("Todos")),
    INTERPRETATION_UNKNOWN: Source("Unknown", "applications-other", _("Other Activity"), _("Other Activities")),
    INTERPRETATION_NOTE: Source("aj://note", "tomboy", _("Edited or Read Note"), _("Edited or Read Notes")),
    INTERPRETATION_VCS: Source("aj://vcs", "bzr-icon-64", _("Software Development"), _("Software Developments"))
}
