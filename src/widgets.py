'''
Created on Nov 28, 2009

@author: seif
'''
import gtk
import gobject
import pango
#from teamgeist import TeamgeistInterface


class DayListView(gtk.TreeView):
    def __init__(self):
        gtk.TreeView.__init__(self)
        self.store = gtk.ListStore(
                                gtk.gdk.Pixbuf,
                                str,    #TIME
                                gobject.TYPE_PYOBJECT,
                                gobject.TYPE_BOOLEAN
                                )

        self.filters = {}
        # Icon 
        icon_cell = gtk.CellRendererPixbuf()
        icon_cell.set_property("yalign", 0.5)
        icon_column = gtk.TreeViewColumn("Icon", icon_cell, pixbuf=0)

        text_cell = gtk.CellRendererText()
        #text_cell.set_properties("wrap-width", 100)
        #text_cell.set_properties("wrap-mode", gtk.WRAP_WORD_CHAR)
        text_cell.set_property("ellipsize", pango.ELLIPSIZE_END)
        text_column = gtk.TreeViewColumn("Activity", text_cell, markup=1)
        
        self.append_column(icon_column)
        self.append_column(text_column)
        
        self.set_headers_visible(False)
        
        self.filterstore = self.store.filter_new()
        self.filterstore.set_visible_column(3)
        self.set_model(self.filterstore)

    def set_filters(self, filters):
        self.filters = filters
        for path in self.store:
            subject =  path[2]
            path[3] = self.filters[subject.interpretation]

    def clear(self):
        self.store.clear()
    
    def append_object(self, icon, text, subject):
        #print text
        #text = "<span><b>"+text+"</b></span>"
        bool = self.filters[subject.interpretation]
        
        self.store.append([
                        icon,
                        text,
                        subject,
                        bool
                        ])


class FilterButton(gtk.Button):
    def __init__(self, img, category):
        gtk.Button.__init__(self)
        self.category = category
        self.img = img
        self.active = True
        self.add(self.img)
        self.set_focus_on_click(False)
        
        self.set_relief(gtk.RELIEF_NONE)
        self.connect("clicked", self.toggle)

    def toggle(self, widget):
        self.active = not self.active
        self.img.set_sensitive(self.active)

class Tab(gtk.HBox):
    def __init__(self, text):
        gtk.HBox.__init__(self)
        self.label = gtk.Label(text)
        self.pack_start(self.label)

        self.closebtn= gtk.Button()
        self.closebtn.set_focus_on_click(False)
        self.closebtn.set_relief(gtk.RELIEF_NONE)
        img = gtk.image_new_from_stock("gtk-close", 4)
        self.closebtn.add(img)
        self.pack_end(self.closebtn)
        
        self.show_all()

class SearchEntry(gtk.Entry):

    __gsignals__ = {
        "clear" : (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   ()),
        "search" : (gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_STRING,))
    }

    # TODO: i18n
    default_text = "Search"

    # The font style of the text in the entry.
    font_style = None

    # TODO: What is this?
    search_timeout = 0

    def __init__(self, accel_group = None):
        gtk.Entry.__init__(self)

        self.set_width_chars(30)
        self.set_text(self.default_text)

        self.connect("changed", lambda w: self._queue_search())
        self.connect("focus-in-event", self._entry_focus_in)
        self.connect("focus-out-event", self._entry_focus_out)
        self.connect("icon-press", self._icon_press)

        self.set_property("primary-icon-name", gtk.STOCK_FIND)
        self.set_property("secondary-icon-name", gtk.STOCK_CLEAR)

        self.font_style = self.get_style().font_desc
        self.font_style.set_style(pango.STYLE_ITALIC)
        self.modify_font(self.font_style)

        self.show_all()

    def _icon_press(self, widget, pos, event):
        # Note: GTK_ENTRY_ICON_SECONDARY does not seem to be bound in PyGTK.
        if int(pos) == 1 and not self.get_text() == self.default_text:
            self._entry_clear_no_change_handler()

    def _entry_focus_in(self, widget, x):
        if self.get_text() == self.default_text:
            self.set_text("")
            self.font_style.set_style(pango.STYLE_NORMAL)
            self.modify_font(self.font_style)

    def _entry_focus_out(self, widget, x):
        if self.get_text() == "":
            self.set_text(self.default_text)
            self.font_style.set_style(pango.STYLE_ITALIC)
            self.modify_font(self.font_style)

    def _entry_clear_no_change_handler(self):
        if not self.get_text() == self.default_text:
            self.set_text("")

    def _queue_search(self):
        if self.search_timeout != 0:
            gobject.source_remove(self.search_timeout)
            self.search_timeout = 0

        if self.get_text() == self.default_text or len(self.get_text()) == 0:
            self.emit("clear")
        else:
            self.search_timeout = gobject.timeout_add(200, self._typing_timeout)

    def _typing_timeout(self):
        if len(self.get_text()) > 0:
            self.emit("search", self.get_text())

        self.search_timeout = 0
        return False