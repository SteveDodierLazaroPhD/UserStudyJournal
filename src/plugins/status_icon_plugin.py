# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Randal Barlow
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
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#try:
#    import appindicator
#except ImportError:
appindicator = None

import gobject
import gtk
import pango
import time

from zeitgeist.datamodel import Event, Interpretation, Manifestation, ResultType

# Import from journal by using 'from src'
from src import config

__plugin_name__ = "Status Icon"
__description__ = "Displays a icon in the notification area which shows recent" + \
                " and most used items as collected by zeitgeist"


THIS, CLIENT, STORE, JOURNAL_WINDOW = None, None, None, None


class LabelSeparatorMenuItem(gtk.MenuItem):
    def __init__(self, label_text=""):
        super(LabelSeparatorMenuItem, self).__init__()
        box = gtk.HBox()
        self.label = gtk.Label(label_text)
        self.label.set_alignment(0.4, 0.5)
        #box.pack_start(gtk.HSeparator(), True, True)
        box.pack_start(self.label, True, True)
        #box.pack_end(gtk.HSeparator(), True, True)
        self.add(box)
        self.set_sensitive(False)


class IconMenuItem(gtk.ImageMenuItem):
    def __init__(self, obj=None):
        super(IconMenuItem, self).__init__("Sample")
        self.label = self.get_child()
        self.remove(self.label)

        box = gtk.HBox()
        self.actor_image = gtk.Image()
        box.pack_start(self.label, False, False)
        box.pack_end(self.actor_image, False, False)
        self.add(box)
        self.image = gtk.Image()
        self.set_image(self.image)
        if obj: self.set_from_content_object(obj)

    def set_from_content_object(self, obj):
        self.connect("activate", lambda w, obj: obj.launch(), obj)
        self.label.set_text(obj.text)
        self.image.set_from_pixbuf(obj.get_icon(24))
        self.actor_image.set_from_pixbuf(obj.get_actor_pixbuf(16))


class MostUsedMenu(gtk.Menu):
    def __init__(self, templates):
        super(MostUsedMenu, self).__init__()
        self.templates = templates
        self.request_items()

    def clear(self): map(self.remove, self.get_children)

    def ids_reply_handler(self, ids):
        structs = map(STORE.get_event_from_id, ids)
        for struct in structs:
            if struct.content_object:
                item = IconMenuItem(struct.content_object)
                item.show_all()
                self.append(item)

    def request_items(self):
        CLIENT.find_event_ids_for_templates(
            self.templates, self.ids_reply_handler,
            num_events=10, result_type=ResultType.MostPopularSubjects)


class AppletMenu(gtk.Menu):
    __gsignals__ = {
        "set" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
    }

    event_templates = (
        Event.new_for_values(interpretation=Interpretation.VISIT_EVENT.uri),
        Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri),
        Event.new_for_values(interpretation=Interpretation.CREATE_EVENT.uri),
        Event.new_for_values(interpretation=Interpretation.OPEN_EVENT.uri),
    )
    day_connection_id = None
    day = None

    sources = (
        (Interpretation.VIDEO, "gnome-mime-video"),
        (Interpretation.MUSIC, "gnome-mime-audio"),
        (Interpretation.IMAGE, "gnome-mime-image"),
        (Interpretation.DOCUMENT, "x-office-document"),
        (Interpretation.SOURCECODE, "gnome-mime-text"),
        (Interpretation.IM_MESSAGE, "empathy"),
        (Interpretation.EMAIL, "email"),
        (Interpretation.UNKNOWN, "gnome-other"),
        (Manifestation.WEB_HISTORY, "text-html"),
        )

    def __init__(self):
        super(AppletMenu, self).__init__()
        self.toggle_button = gtk.CheckMenuItem(_("Show Activity Journal"))
        self.toggle_button.set_active(True)
        self.quit_button = gtk.ImageMenuItem(stock_id=gtk.STOCK_QUIT)
        self.kept_members = [LabelSeparatorMenuItem(_("Recently Used")), LabelSeparatorMenuItem(_("Most Used"))]
        for symbol, icon_name in self.sources:
            menu = gtk.ImageMenuItem(symbol.display_name)
            image = gtk.image_new_from_icon_name(icon_name, 24)
            image.show_all()
            menu.set_image(image)
            if symbol.uri in Interpretation:
                templates = [Event.new_for_values(subject_interpretation=symbol.uri)]
            elif symbol.uri in Manifestation:
                templates = [Event.new_for_values(subject_manifestation=symbol.uri)]
            else:
                templates = []
            child_menu = MostUsedMenu(templates)
            menu.set_submenu(child_menu)
            self.kept_members.append(menu)
        self.kept_members += [gtk.SeparatorMenuItem(), self.toggle_button, self.quit_button]
        for item in self.kept_members:
            self.append(item)
            item.show_all()
        self.set_day(STORE.today)

    def clear(self):
        for item in self:
            if item not in self.kept_members:
                self.remove(item)
        return True

    def set_day(self, day):
        if self.day:
            self.day.disconnect(self.day_connection_id)
        day.connect("update", self.set)
        self.day = day
        self.set()

    def set(self, *args):
        self.clear()
        for struct in self.day.filter(self.event_templates, result_type=ResultType.MostRecentSubjects)[-8::]:
            if struct.content_object:
                m = IconMenuItem(struct.content_object)
                self.insert(m, 1)
                m.show_all()
        self.emit("set")


class StatusIcon(gtk.StatusIcon):
    __gsignals__ = {
        "toggle-visibility": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_BOOLEAN,)),
        "quit": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
        }

    def __init__(self):
        gtk.StatusIcon.__init__(self)
        self.menu = AppletMenu()
        self.menu.toggle_button.connect(
            "toggled",
            lambda *args: self.emit("toggle-visibility", self.menu.toggle_button.get_active()))
        self.menu.quit_button.connect("activate", lambda *args: self.emit("quit"))
        #self.set_from_file(get_icon_path("hicolor/scalable/apps/gnome-activity-journal.svg"))
        self.set_from_file(config.get_icon_path("hicolor/24x24/apps/gnome-activity-journal.png"))
        self.set_tooltip( _("Activity Journal"))
        self.connect("popup-menu", self.popup_menu_cb)

    def popup_menu_cb(self, widget, button, activate_time):
        self.menu.popup(None, None, gtk.status_icon_position_menu,
                   button, activate_time, self)

    def activate(self):
        if not self.menu:
            self.menu = gtk.Menu()

    def deactivate(self):
        self.menu.destroy()
        self.set_visible(False)
        del self.menu
        self.menu = None


def activate(client, store, window):
    """
    Called by the PluginManager as the plugins entry point which initializes the plugin"""
    # Check if the status icon was loaded
    global THIS
    if THIS:
        THIS.activate()
        return True
    # Imports and globals
    global CLIENT
    global STORE
    global JOURNAL_WINDOW
    CLIENT = client
    STORE = store
    JOURNAL_WINDOW = window
    # Plugin Setup
    if appindicator:
        THIS = status = IndicatorIcon()
    else:
        THIS = status = StatusIcon()
        status.set_visible(True)
    status.connect("toggle-visibility", lambda w, v: window.set_visibility(v))
    status.connect("quit", lambda *args: gtk.main_quit())
    def _cb(*args):
        val = window.toggle_visibility()
        status.menu.toggle_button.set_active(val)
    status.connect("activate", _cb)
    return True


def deactivate(client, store, window):
    """ Tears down the plugin"""
    global THIS
    if THIS:
        THIS.deactivate()

