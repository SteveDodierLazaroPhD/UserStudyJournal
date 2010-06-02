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

import gobject
import gtk

from src.main import ViewContainer
from src.supporting_widgets import ContextMenu

__plugin_name__ = "Minimal Mode"
__description__ = "reduces the size which journal takes on the screen"


def activate(client, store, window):
    """
    This function is called to activate the plugin.

    :param client: the zeitgeist client used by journal
    :param store: the date based store which is used by journal to handle event and content object request
    :param window: the activity journal primary window
    """

    def f():
        # Information Container
        info = window.panedcontainer.informationcontainer
        window.panedcontainer.h1.remove(info)
        window.panedcontainer.h1.destroy()
        window.panedcontainer.right_box.destroy()
        i = window.view.register_new_view(ViewContainer.ViewStruct(info,gtk.ToolButton(gtk.STOCK_INFO)))
        info.close_button.destroy()
        window.view.queue_draw()
        def infomenu_cb(*args):
            window.view.set_view_page(i)
        info.connect("content-object-set", infomenu_cb)

        # Pinbox
        pin = window.panedcontainer.pinbox
        window.panedcontainer.h2.remove(pin)
        window.panedcontainer.h2.destroy()
        window.panedcontainer.left_box.destroy()
        pin.close_button.destroy()
        pin.set_shadow_type(gtk.SHADOW_NONE)
        mv = window.view.pages[0]
        today_box = mv.pages[len(mv)-1].box
        pin.pinbox.label.show()
        today_box.pack_start(pin, False, False)
        today_box.reorder_child(pin, 0)
        return False
    gobject.timeout_add_seconds(1, f)

def deactivate(client, store, window):
    md = gtk.MessageDialog(
        window,
        gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_WARNING,
        gtk.BUTTONS_CLOSE, "This plugin requires a restart to be disabled.")
    md.run()
    md.destroy()

