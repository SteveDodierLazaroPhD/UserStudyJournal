# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
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

import os
import pickle
import gobject

class Bookmarker(gobject.GObject):
    __gsignals__ = {
        "reload" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_PYOBJECT,))
        }
    def __init__(self):
        gobject.GObject.__init__(self)
        path = os.path.expanduser('~/.local/share/gaj/')
        self.bookmarks_file = path + "bookmarks"
        self._mkdir(path)
        self.bookmarks = None
        
    def _mkdir(self, newdir):
        """works the way a good mkdir should :)
            - already exists, silently complete
            - regular file in the way, raise an exception
            - parent directory(ies) does not exist, make them as well
        """
        if os.path.isdir(newdir):
            pass
        elif os.path.isfile(newdir):
            raise OSError("a file with the same name as the desired " \
                          "dir, '%s', already exists." % newdir)
        else:
            head, tail = os.path.split(newdir)
            if head and not os.path.isdir(head):
                self._mkdir(head)
            #print "_mkdir %s" % repr(newdir)
            if tail:
                os.mkdir(newdir)
            
    def bookmark(self, uri):
        if not self.bookmarks:
            try:
                filehandler = open(self.bookmarks_file, 'r') 
                self.bookmarks = pickle.load(filehandler)
                filehandler.close()
            except:
                self.bookmarks = []
                
        if not uri in self.bookmarks:
            self.bookmarks.append(uri)
        
        filehandler = open(self.bookmarks_file, 'w') 
        pickle.dump(self.bookmarks, filehandler)
        filehandler.close()
        self.emit("reload", self.bookmarks)

    def unbookmark(self, uri):
        if not self.bookmarks:
            try:
                filehandler = open(self.bookmarks_file, 'r') 
                self.bookmarks = pickle.load(filehandler)
                filehandler.close()
            except:
                self.bookmarks = []
                
        if uri in self.bookmarks:
            self.bookmarks.remove(uri)
        
        filehandler = open(self.bookmarks_file, 'w') 
        pickle.dump(self.bookmarks, filehandler)
        filehandler.close()
        self.emit("reload", self.bookmarks)
        
bookmarker = Bookmarker()
bookmarker.bookmark("bla")