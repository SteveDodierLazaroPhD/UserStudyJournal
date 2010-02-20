#! /usr/bin/env python
# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
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
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from xdg import BaseDirectory

from fungtk.quickconf import QuickConf

# Installation details
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(BASE_PATH, "data")
VERSION = "0.3.3"
GETTEXT_PATH = None

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

# Configuration and user data
USER_DATA_PATH = BaseDirectory.save_data_path("gnome-activity-journal")

# GConf
settings = QuickConf("/apps/gnome-activity-journal")

# GConf keys only updated at startup and globally useful
# (TODO: shouldn't we always connect to changes?)
ACCESSIBILITY = settings.get("accessibility", False)
