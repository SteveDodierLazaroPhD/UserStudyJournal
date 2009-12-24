#!/usr/bin/env python

# example drawingarea.py

import pygtk
pygtk.require('2.0')
import gtk
import operator
import time
import string
from ui_utils import *
 
class WindowView(gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self)
        self.connect("destroy", self.quit)
        self.set_size_request(400,400)
        self.vbox = gtk.VBox()
        self.add(self.vbox)
        
        self._init_toppanel()
        
        self.show_all()
    
    def quit(self, widget):
        self.destroy()    
    
    def _init_iconview(self):
        self.view = IconView()
    
    def _init_toppanel(self):
        hbox= gtk.HBox()
        self.vbox.pack_start(hbox, False, False)
        
        toolbar1 = gtk.Toolbar()
        toolbar2 = gtk.Toolbar()
        
        hbox.pack_start(toolbar1)
        hbox.pack_end(toolbar2, False, False)
        
        self.delbtn = gtk.ToolButton("gtk-remove")
        toolbar1.add(self.delbtn)
        

class IconView(gtk.IconView):
    def __init__(self):
        gtk.IconView(self)
        pass
        
class DrawingAreaExample:
    def __init__(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title("Drawing Area Example")
        window.connect("destroy", lambda w: gtk.main_quit())
        self.area = gtk.DrawingArea()
        self.area.set_size_request(400, 300)
        self.pangolayout = self.area.create_pango_layout("")
        self.sw = gtk.ScrolledWindow()
        self.sw.add_with_viewport(self.area)
        self.table = gtk.Table(2,2)
        self.table.attach(self.sw, 1, 2, 1, 2)
        window.add(self.table)
        
        self.area.set_events(gtk.gdk.POINTER_MOTION_MASK |
                             gtk.gdk.POINTER_MOTION_HINT_MASK )
        self.area.connect("expose-event", self.area_expose_cb)
        
        self.area.show()
        self.sw.show()
        self.table.show()
        window.show()

    def area_expose_cb(self, area, event):
        self.style = self.area.get_style()
        self.gc = self.style.fg_gc[gtk.STATE_NORMAL]
        self.draw_pixmap(10,10)
        return True

    def draw_pixmap(self, x, y):
        key = Interpretation.VIDEO.uri
        pixbuf = get_category_icon(SUPPORTED_SOURCES[key]["icon"])
        self.area.window.draw_pixbuf(self.gc, pixbuf, 0, 0, x+15, y+25,
                                       -1, -1)
        self.pangolayout.set_text("Pixmap")
        self.area.window.draw_layout(self.gc, x+5, y+80, self.pangolayout)
        return

def main():
    gtk.main()
    return 0

if __name__ == "__main__":
    DrawingAreaExample()
    main()