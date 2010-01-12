# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
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

from __future__ import with_statement
import os
import cPickle
import gobject

from config import DATA_PATH

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
        self.bookmarks_file = os.path.join(DATA_PATH, "bookmarks.pickled")
        self._load()
    
    def _load(self):
        if os.path.isfile(self.bookmarks_file):
            try:
                with open(self.bookmarks_file) as f:
                    self.bookmarks = cPickle.load(f)
            except BadPickleGet:
                print "Pin database is corrupt."
    
    def _save(self):
        with open(self.bookmarks_file, "w") as f:
            cPickle.dump(self.bookmarks, f)
    
    def bookmark(self, uri):
        if not uri in self.bookmarks:
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

bookmarker = Bookmarker()
