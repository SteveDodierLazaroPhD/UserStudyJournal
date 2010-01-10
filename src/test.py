'''
Created on Jan 9, 2010

@author: seif
'''
import gtk
from widgets import SearchEntry

class SearchBox(gtk.HBox):
    def __init__(self):
        gtk.HBox.__init__(self)
        self.search = SearchEntry()
        self.pack_start(self.search)
        

if __name__ == "__main__":
    window = gtk.Window()
    window.add(SearchBox())
    window.show_all()
    gtk.main()