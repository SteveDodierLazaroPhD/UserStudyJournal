# -.- coding: utf-8 -.-
#
# blacklist_manager.py GNOME Activity Journal Plugin
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

import dbus
import gobject
import gtk
import pango

__plugin_name__ = _("Blacklist Manager")
__description__ = _("Add and remove items from the zeitgeist blacklist")

from zeitgeist.datamodel import Event

from src.supporting_widgets import StockIconButton
from src.common import get_icon_for_name


class BlacklistManager(object):
    def __init__(self):
        obj = dbus.SessionBus().get_object("org.gnome.zeitgeist.Engine", "/org/gnome/zeitgeist/blacklist")
        self.iface = dbus.Interface(obj, "org.gnome.zeitgeist.Blacklist")

    def get_templates(self):
        return map(Event.new_for_struct, self.iface.GetBlacklist())

    def append_template(self, new_template):
        templates = self.get_templates()
        templates.append(new_template)
        self.iface.SetBlacklist(templates)

    def remove_template(self, new_template):
        templates = self.get_templates()
        for template in templates:
            if template.matches_template(new_template):
                templates.remove(template)
                return self.iface.SetBlacklist(templates)
        raise ValueError()

    def delete_events_matching_blacklist(self):
        raise NotImplementedError("This function is not available yet")
        templates = self.get_templates()


class BlacklistView(gtk.TreeView):
    empty_row_text = _("[Insert Path]")
    def __init__(self):
        super(BlacklistView, self).__init__()
        self.manager = BlacklistManager()
        delcolumn = gtk.TreeViewColumn("")
        pixbuf_render = gtk.CellRendererPixbuf()
        delcolumn.pack_start(pixbuf_render, False)
        stock_pb = get_icon_for_name("remove", 8)
        delcolumn.set_cell_data_func(pixbuf_render, lambda *x: pixbuf_render.set_property("pixbuf", stock_pb), "pixbuf")
        self.append_column(delcolumn)
        bcolumn = gtk.TreeViewColumn("Blacklisted subject URIs")
        text_render = gtk.CellRendererText()
        text_render.set_property("editable", True)
        text_render.set_property("ellipsize", pango.ELLIPSIZE_MIDDLE)
        text_render.connect("edited", self._edited)
        bcolumn.pack_start(text_render, True)
        bcolumn.add_attribute(text_render, "markup", 0)
        self.append_column(bcolumn)

        self.connect("row-activated", self._on_row_activated)
        self.load_list()

    def _on_row_activated(self, this, path, column):
        if isinstance(column.get_cell_renderers()[0], gtk.CellRendererPixbuf):
            model = self.get_model()
            template = model[path][1]
            self.manager.remove_template(template)
            del model[path]

    def _edited(self, renderer, path, new_text):
        if not new_text or new_text == self.empty_row_text:
            return
        model = self.get_model()
        template = model[path][1]
        if template and new_text == template.subjects[0].uri:
            return
        if not template:
            template = Event.new_for_values(subject_uri=new_text)
            model[path][1] = template
        else:
            template.subjects[0].uri = new_text
        try:
            self.manager.remove_template(template)
        except ValueError:
            pass
        self.manager.append_template(template)
        model[path][0] = new_text

    def load_list(self):
        store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
        for template in self.manager.get_templates():
            store.append([template.subjects[0].uri, template])
        self.set_model(store)



def activate(client, store, window):
    """
    This function is called to activate the plugin.

    :param client: the zeitgeist client used by journal
    :param store: the date based store which is used by journal to handle event and content object request
    :param window: the activity journal primary window
    """
    window.preferences_dialog.notebook.page = page = gtk.VBox()
    treescroll = gtk.ScrolledWindow()
    page.set_border_width(10)
    treescroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    treescroll.set_shadow_type(gtk.SHADOW_IN)
    tree = BlacklistView()
    treescroll.add(tree)
    bbox = gtk.HBox()
    new_template_button = StockIconButton(gtk.STOCK_NEW)
    new_template_button.set_alignment(1, 0.5)
    # apply_black_list = StockIconButton(gtk.STOCK_APPLY, label="Apply to existing")
    page.pack_start(bbox, False, False, 2)
    page.add(treescroll)
    bbox.pack_start(new_template_button, False, False)
    # bbox.pack_end(apply_black_list, False, False)
    new_template_button.connect("clicked", lambda w: tree.get_model().append([tree.empty_row_text, None]))
    window.preferences_dialog.notebook.append_page(page, tab_label=gtk.Label(_("Blacklist")))
    window.preferences_dialog.notebook.show_all()
    pass


def deactivate(client, store, window):
    """
    This function is called to deactivate the plugin.

    :param client: the zeitgeist client used by journal
    :param store: the date based store which is used by journal to handle event and content object request
    :param window: the activity journal primary window
    """
    window.preferences_dialog.notebook.page.destroy()
    del window.preferences_dialog.notebook.page
    pass
