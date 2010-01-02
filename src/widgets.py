'''
Created on Nov 28, 2009

@author: seif
'''
import gtk
import datetime
import gobject
import pango
from ui_utils import *
#from teamgeist import TeamgeistInterface


class DayListView(gtk.TreeView):
    def __init__(self):
        gtk.TreeView.__init__(self)
        self.store = gtk.ListStore(
                                gtk.gdk.Pixbuf,
                                str,    #TIME
                                gobject.TYPE_PYOBJECT,
                                gobject.TYPE_BOOLEAN,
                                str
                                )

        self.filters = {}
        # Icon 
        icon_cell = gtk.CellRendererPixbuf()
        icon_cell.set_property("yalign", 0.5)
        icon_column = gtk.TreeViewColumn("Icon", icon_cell, pixbuf=0)

        text_cell = gtk.CellRendererText()
        text_cell.set_property("ellipsize", pango.ELLIPSIZE_END)
        text_column = gtk.TreeViewColumn("Activity", text_cell, markup=1)
        text_column.set_expand(True)
        
        time_cell = gtk.CellRendererText()
        self.time_column = gtk.TreeViewColumn("Activity", time_cell, markup=4)
        
        self.append_column(icon_column)
        self.append_column(text_column)
        if settings.show_timestamps:
            #self.insert_column(self.time_column, 0)
            self.append_column(self.time_column)
            
        settings.connect("toggle-time", lambda x, y: self.revisit_timestamps())
        
        def _deselect_all(view, event):
            selection = self.get_selection()
            selection.unselect_all()
        
        self.connect("focus-out-event", _deselect_all)
        
        self.set_headers_visible(False)
        
        self.filterstore = self.store.filter_new()
        self.filterstore.set_visible_column(3)
        self.set_model(self.filterstore)
        
        self.connect("button-press-event", self._handle_click)
        self.connect("row-activated", self._handle_open)
        
    def _handle_open(self, view=None, path=None, column=None, item=None):
        if not item:
            item = view.get_model()[path][2].subjects[0]
        if item.mimetype == "x-tomboy/note":
            uri_to_open = "note://tomboy/%s" % os.path.splitext(os.path.split(item.uri)[1])[0]
        else:
            uri_to_open = item.uri
        if uri_to_open:
            launcher.launch_uri(uri_to_open, item.mimetype)
        
    def _handle_click(self, view, ev):
        if ev.button == 3:
            (path,col,x,y) = view.get_path_at_pos(int(ev.x),int(ev.y))
            iter = self.filterstore.get_iter(path)
            item = self.filterstore.get_value(iter, 2).subjects[0]
            if item:
                menu = gtk.Menu()
                menu.attach_to_widget(view, None)
                self._populate_popup(menu, item)
                menu.popup(None, None, None, ev.button, ev.time)

    def _populate_popup(self, menu, item):
        open = gtk.ImageMenuItem (gtk.STOCK_OPEN)
        open.connect("activate", lambda *discard: self._handle_open(item=item))
        open.show()
        menu.append(open)
        most = gtk.MenuItem(("Get most used with... (N/A)"))
        most.show()
        menu.append(most)
        prop = gtk.MenuItem(("Properties... (N/A)"))
        prop.show()
        menu.append(prop)

    def revisit_timestamps(self):
        if not settings.show_timestamps:
            self.remove_column(self.time_column)
        else:
            #self.insert_column(self.time_column, 0)
            self.append_column(self.time_column)
    
    def set_filters(self, filters):
        self.filters = filters
        for path in self.store:
            event =  path[2]
            path[3] = self.filters[event.subjects[0].interpretation]

    def clear(self):
        self.store.clear()
    
    def append_object(self, icon, text, event):
        #print text
        #text = "<span><b>"+text+"</b></span>"
        bool = self.filters[event.subjects[0].interpretation]
        timestamp = datetime.datetime.fromtimestamp(int(event.timestamp)/1000).strftime("%H:%M")
        self.store.append([
                        icon,
                        text,
                        event,
                        bool,
                        timestamp
                        ])

    def append_category(self, cat, events):
        bool = self.filters[cat]
        icon = get_category_icon(SUPPORTED_SOURCES[cat].icon, 24)
        text = "<span><b>%d %s</b></span>" % (len(events), SUPPORTED_SOURCES[cat].group_label(len(events)))
        self.store.append([
                        icon,
                        text,
                        events,
                        bool,
                        None
                        ])

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

class Calendar(gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self)
        self.vbox = gtk.VBox()
        evbox = gtk.EventBox()

        evbox2 = gtk.EventBox()
        evbox.add(evbox2)        
        evbox2.add(self.vbox)
        #evbox.set_border_width(3)
        evbox2.set_border_width(3)
        
        menu = gtk.Menu()
        evbox.modify_bg(gtk.STATE_NORMAL, menu.style.bg[gtk.STATE_SELECTED])
        evbox2.modify_bg(gtk.STATE_NORMAL, menu.style.bg[gtk.STATE_NORMAL])

        self.calendar = gtk.Calendar()

        self.timerangebox = gtk.HBox()
        label = gtk.Label("Days to display:")
        label.set_markup("<span><b>Days to display: </b></span>")
        self.timerangebox.pack_start(label)
        
        self.combox = gtk.combo_box_new_text()
        self.combox.append_text("1 day")
        self.combox.append_text("3 days")
        self.combox.append_text("1 week")
        self.combox.append_text("1 month")
        self.combox.set_active(1)
        
        self.timerangebox.pack_start(self.combox)

        self.add(evbox)
        self.vbox.pack_start(self.calendar)
        self.vbox.pack_start(self.timerangebox)
        self.set_decorated(False)
