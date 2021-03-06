# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Siegfried Gevatter <siegfried@gevatter.com>
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
# Copyright © 2011 Stefano Candori <stefano.candori@gmail.com>
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

import gtk
import gettext
import pango
import gobject
import time
import datetime
import os

from activity_widgets import MultiViewContainer, TimelineViewContainer, ThumbViewContainer
from supporting_widgets import DayButton, DayLabel, Toolbar, SearchBox, PreferencesDialog, ContextMenu, ThrobberPopupButton, \
ContextMenuMolteplicity, NiceBar
from histogram import HistogramWidget
from store import Store, tdelta, STORE, CLIENT
from config import settings, get_icon_path, get_data_path, PluginManager
from Indicator import TrayIconManager
from common import SIZE_THUMBVIEW, SIZE_TIMELINEVIEW

#TODO granularity scrool, alignment timelineview_icon
#more metadata? use website cache as thumbpreview??
class ViewContainer(gtk.Notebook):
    __gsignals__ = {
        "new-view-added" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,)),
        "view-button-clicked" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,gobject.TYPE_INT)),
    }

    class ViewStruct(object):
        view = None
        button = None

        def __init__(self, view, button):
            self.view = view
            self.button = button

    def __init__(self, store):
        super(ViewContainer, self).__init__()
        self.store = store
        self.set_show_tabs(False)
        self.set_show_border(False)
        self.pages = []
        self.tool_buttons = []

    def set_day(self, day, page=None):
        force_update = True
        if page == None:
            page = self.page
            force_update = False
        if hasattr(self.pages[page], "set_day"):
            self.pages[page].set_day(day, self.store, force_update)
            
    def set_zoom(self, zoom):
        page = self.page
        if hasattr(self.pages[page], "set_zoom"):
            self.pages[page].set_zoom(zoom)

    def _register_new_view(self, viewstruct):
        self.append_page(viewstruct.view)
        self.pages.append(viewstruct.view)
        self.tool_buttons.append(viewstruct.button)
        if(len(self.tool_buttons)) > 1:
            viewstruct.button.set_group(self.tool_buttons[0])  
        viewstruct.button.set_flags(gtk.CAN_FOCUS) 
        viewstruct.button.connect("toggled", self.view_button_toggled, len(self.pages)-1)
        viewstruct.view.show_all()
        return self.pages.index(viewstruct.view)

    def register_new_view(self, viewstruct):
        i = self._register_new_view(viewstruct)
        self.emit("new-view-added", viewstruct)
        return i

    def remove_view(self, i, destroy=False):
        """
        :param i: a page number index starting at zero
        """
        tb = self.tool_buttons[i]
        page = self.pages[i]
        del self.pages[i]
        del self.tool_buttons[i]
        self.remove_page(i)
        tb.parent.remove(tb)
        if destroy:
            page.destroy()
            tb.destroy()

    @property
    def page(self):
        return self.get_current_page()

    def view_button_toggled(self, button, i):
        if not button.get_active():return
        button.grab_focus()
    	self.emit("view-button-clicked", button, i)

    def set_view_page(self, i):
        self.set_current_page(i)

    def _register_default_view(self, view):
        toolbutton = Toolbar.get_toolbutton(view.icon_path, view.dsc_text)
        self._register_new_view(self.ViewStruct(view, toolbutton))
        self.set_view_page(0)
        
    def set_zoom_slider(self, hscale):
        #FIXME dirty hack
        for page in self.pages:
            page.set_slider(hscale)
            
    def toggle_erase_mode(self):
        for page in self.pages:
            page.toggle_erase_mode()
        

class PortalWindow(gtk.Window):
    """
    The primary application window
    """
    def __init__(self):
        super(PortalWindow, self).__init__()
        # Important
        self._request_size()
        self.store = STORE
        self.day_iter = self.store.today
        self.pages_loaded = 0
        self.current_zoom = 1
        self.in_erase_mode = False
        self.view = ViewContainer(self.store)
        self.toolbar = Toolbar()
        default_views = (MultiViewContainer(), ThumbViewContainer(), TimelineViewContainer())
        default_views[0].connect("view-ready", self._on_view_ready)
        map(self.view._register_default_view, default_views)
        map(self.toolbar.add_new_view_button, self.view.tool_buttons[::-1])
        self.preferences_dialog = PreferencesDialog(parent=self)
        ContextMenu.set_parent_window(self)
        ContextMenuMolteplicity.set_parent_window(self)
        self.histogram = HistogramWidget()
        self.histogram.set_store(self.store)
        self.backward_button, ev_backward_button = DayButton.new(0)
        self.forward_button, ev_forward_button = DayButton.new(1, sensitive=False)
        self.nicebar = NiceBar()
        self.nicebar_timeout = None
        
        # use a table for the spinner (otherwise the spinner is massive!)
        spinner_table = gtk.Table(3, 3, False)
        label = gtk.Label()
        label.set_markup(_("<span size=\"larger\"><b>Loading Journal...</b></span>"))
        vbox = gtk.VBox(False, 5)
        pix = gtk.gdk.pixbuf_new_from_file(get_data_path("zeitgeist-logo.svg"))
        pix = pix.scale_simple(100, 100, gtk.gdk.INTERP_BILINEAR)
        zlogo = gtk.image_new_from_pixbuf(pix)
        vbox.pack_start(zlogo, False, False)
        vbox.pack_start(label, True)
        spinner_table.attach(vbox, 1, 2, 1, 2, gtk.EXPAND, gtk.EXPAND)
        self.hscale = gtk.HScale(gtk.Adjustment(1.0, 0.0, 3.0, 1.0, 1.0, 0.0))
        self.hscale.set_size_request(120, -1)
        self.hscale.set_draw_value(False)
        al = gtk.Alignment(yalign=0.5)
        al.set_padding(0, 0, 8, 8)
        al.add(self.hscale)
        im_in = gtk.image_new_from_stock(gtk.STOCK_ZOOM_IN, gtk.ICON_SIZE_MENU)
        im_out =  gtk.image_new_from_stock(gtk.STOCK_ZOOM_OUT, gtk.ICON_SIZE_MENU)
        self.throbber_popup_button = ThrobberPopupButton()
        # Widget placement
        vbox = gtk.VBox(); hbox = gtk.HBox();self.scale_box = gtk.HBox();self.histogramhbox = gtk.HBox()
        vbox_general = gtk.VBox();scale_toolbar_box = gtk.HBox()
        hbox.pack_start(ev_backward_button, False, False); hbox.pack_start(self.view, True, True, 6)
        hbox.pack_end(ev_forward_button, False, False);
        self.scale_box.pack_start(im_out,False,False);self.scale_box.pack_start(al, False, False)
        self.scale_box.pack_start(im_in,False,False);self.scale_box.pack_end(gtk.SeparatorToolItem(),False,False)
        scale_toolbar_box.pack_start(self.toolbar); scale_toolbar_box.pack_end(self.throbber_popup_button,False,False);
        scale_toolbar_box.pack_end(self.scale_box, False, False);
        vbox.pack_start(scale_toolbar_box, False, False); vbox.pack_start(self.nicebar,False,False);vbox.pack_start(hbox, True, True, 5);
        self.histogramhbox.pack_end(self.histogram, True, True, 32);
        self.histogramhbox.set_sensitive(False)
        self.spinner_notebook = gtk.Notebook()
        self.spinner_notebook.set_show_tabs(False)
        self.spinner_notebook.set_show_border(False)
        self.spinner_notebook.append_page(spinner_table)
        self.spinner_notebook.append_page(vbox)
        vbox_general.pack_start(self.spinner_notebook)
        vbox_general.pack_end(self.histogramhbox, False, False)
        self.add(vbox_general)
        vbox_general.show_all()
        self.scale_box.hide()
        
        self.show()
        self.nicebar.hide()
        SearchBox.hide()
        
        #Tray Icon
        self.tray_manager = TrayIconManager(self)
        # Settings
        self.view.set_day(self.store.today)
        self.view.set_zoom_slider(self.hscale)
        # Signal connections
        self.view.connect("new-view-added", lambda w, v: self.toolbar.add_new_view_button(v.button, len(self.view.tool_buttons)))
        self.connect("destroy", self.quit)
        self.connect("delete-event", self.on_delete)
        self.toolbar.connect("previous", self.previous)
        self.toolbar.connect("jump-to-today", lambda w: self.set_date(datetime.date.today()))
        self.toolbar.connect("next", self.next)
        self.hscale.connect("value-changed", self._on_zoom_changed)
        self.backward_button.connect("clicked", self.previous)
        self.forward_button.connect("clicked", self.next)
        self.forward_button.connect("jump-to-today", lambda w: self.set_date(datetime.date.today()))
        self.histogram.connect("date-changed", lambda w, date: self.set_date(date))
        self.view.connect("view-button-clicked", self.on_view_button_click)
        self.store.connect("update", self.histogram.histogram.set_store)
        SearchBox.connect("search", self._on_search)
        self.throbber_popup_button.connect("toggle-erase-mode", self._on_toggle_erase_mode)
        SearchBox.connect("clear", self._on_search_clear)
        # Window configuration
        self.set_icon_name("ucl-study-journal")
        self.set_icon_list(
            *[gtk.gdk.pixbuf_new_from_file(get_icon_path(f)) for f in (
                "hicolor/16x16/apps/ucl-study-journal.png",
                "hicolor/24x24/apps/ucl-study-journal.png",
                "hicolor/32x32/apps/ucl-study-journal.png",
                "hicolor/48x48/apps/ucl-study-journal.png",
                "hicolor/256x256/apps/ucl-study-journal.png")])
        gobject.idle_add(self.setup)
        gobject.idle_add(self.load_plugins)

    def load_plugins(self):
        self.plug_manager = PluginManager(CLIENT, STORE, self)
        self.preferences_dialog.notebook.show_all()
        self.throbber_popup_button.preferences.connect("activate", lambda *args: self.preferences_dialog.show())
        self.preferences_dialog.plug_tree.set_items(self.plug_manager)
        return False

    def setup(self, *args):
        self.set_title_from_date(self.day_iter.date)
        self.histogram.set_dates(self.active_dates)
        self.histogram.scroll_to_end()
        return False
    
    def set_visibility(self, val):
        if val: self.show()
        else: self.hide()

    def toggle_visibility(self):
        if self.get_property("visible"):
            self.hide()
            return False
        self.show()
        return True

    @property
    def active_dates(self):
        date = self.day_iter.date
        if self.view.page != 0: return [date]
        dates = []
        for i in range(self.view.pages[0].num_pages):
            dates.append(date + tdelta(-i))
        dates.sort()
        return dates

    def set_day(self, day):
        self.throbber_popup_button.image.animate_for_seconds(1)
        self.day_iter = day
        self.handle_button_sensitivity(day.date)
        self.view.set_day(day)
        self.histogram.set_dates(self.active_dates)
        self.set_title_from_date(day.date)

    def set_date(self, date):
        self.set_day(self.store[date])

    def next(self, *args):
        day = self.day_iter.next(self.store)
        self.set_day(day)

    def previous(self, *args):
        day = self.day_iter.previous(self.store)
        self.set_day(day)

    def handle_button_sensitivity(self, date):
        today = datetime.date.today()
        if date == today:
            self.forward_button.set_sensitive(False)
            self.toolbar.nextd_button.set_sensitive(False)
            self.toolbar.home_button.set_sensitive(False)
        else:
            self.forward_button.set_leading(True)
            self.forward_button.set_sensitive(True)
            self.toolbar.nextd_button.set_sensitive(True)
            self.toolbar.home_button.set_sensitive(True)

    def on_view_button_click(self, w, button, i):
        self.view.set_view_page(i)
        self.view.set_day(self.day_iter, page=i)
        self.histogram.set_dates(self.active_dates)
        self.set_title_from_date(self.day_iter.date)        
        if i == 0:
            self.scale_box.hide()
        else:
            self.view.set_zoom(self.current_zoom)
            self.scale_box.show()

    def _on_view_ready(self, view):
        if self.pages_loaded == view.num_pages - 1:
            self.histogramhbox.set_sensitive(True)
            self.spinner_notebook.set_current_page(1)
        else:
            self.pages_loaded += 1

    def _on_search(self, box, results):
        dates = []
        for obj in results:
            dates.append(datetime.date.fromtimestamp(int(obj.event.timestamp)/1000.0))
        self.histogram.histogram.set_highlighted(dates)

    def _on_search_clear(self, *args):
        self.histogram.histogram.clear_highlighted()

    def _request_size(self):
        screen = self.get_screen().get_monitor_geometry(
            self.get_screen().get_monitor_at_point(*self.get_position()))
        min_size = (1024, 600) # minimum netbook size
        size = [
            min(max(int(screen[2] * 0.80), min_size[0]), screen[2]),
            min(max(int(screen[3] * 0.75), min_size[1]), screen[3])
        ]
        if settings["window_width"] and settings["window_width"] <= screen[2]:
            size[0] = settings['window_width']
        if settings["window_height"] and settings["window_height"] <= screen[3]:
            size[1] = settings["window_height"]

        self.set_geometry_hints(min_width=1024, min_height=360)
        self.resize(size[0], size[1])
        self._requested_size = size     
             
    def _on_zoom_changed(self, hscale):
        self.current_zoom = int(hscale.get_value())
        self.view.set_zoom(self.current_zoom) 
        
    def _on_toggle_erase_mode(self, *args):
        self.in_erase_mode = not self.in_erase_mode
        if self.in_erase_mode:
            if self.nicebar_timeout:
                gobject.source_remove(self.nicebar_timeout)
                self.nicebar_timeout = None
            hand = gtk.gdk.Cursor(gtk.gdk.PIRATE) 
            message = _("Erase Mode is active")
            background = NiceBar.ALERTBACKGROUND
            stock = gtk.STOCK_DIALOG_WARNING
        else:
            hand = gtk.gdk.Cursor(gtk.gdk.ARROW)
            message = _("Erase Mode deactivated")
            background = NiceBar.NORMALBACKGROUND
            stock = gtk.STOCK_DIALOG_INFO 
            self.nicebar_timeout = gobject.timeout_add(3000, self.nicebar.remove_message)
            
        self.nicebar.display_message(message, background=background, stock=stock)
        self.window.set_cursor(hand)
        self.view.toggle_erase_mode()              

    def set_title_from_date(self, date):
        pages = self.view.pages[0].num_pages
        if self.view.page == 0:
            start_date = date + tdelta(-pages+1)
        else:
            start_date = date
        if date == datetime.date.today():
            end = _("Today")
            start = start_date.strftime("%A")
        elif date == datetime.date.today() + tdelta(-1):
            end = _("Yesterday")
            start = start_date.strftime("%A")
        elif date + tdelta(6) > datetime.date.today():
            end = date.strftime("%A")
            start = start_date.strftime("%A")
        else:
            start = start_date.strftime("%d %B")
            end = date.strftime("%d %B")
        if self.view.page != 0:
            self.set_title(end + " - Study Journal")
        else:
            self.set_title(_("%s to %s") % (start, end) + " - " + _("Study Journal"))

    def on_delete(self, w, event):
        x, y = self.get_size()
        settings["window_width"] = x
        settings["window_height"] = y
        if settings.get("tray_icon", False):
            self.set_visibility(False)
            return True

    def quit_and_save(self, *args):
        x, y = self.get_size()
        settings["window_width"] = x
        settings["window_height"] = y
        gtk.main_quit()

    def quit(self, *args):
        gtk.main_quit()

