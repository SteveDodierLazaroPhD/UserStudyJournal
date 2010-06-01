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
    def f():
        info = window.panedcontainer.informationcontainer
        window.panedcontainer.h1.remove(info)
        window.panedcontainer.h1.destroy()
        window.panedcontainer.right_box.destroy()
        i = window.view.register_new_view(ViewContainer.ViewStruct(info,gtk.ToolButton(gtk.STOCK_INFO)))
        info.close_button.destroy()
        window.view.pages[0].queue_draw()
        def infomenu_cb(*args):
            for button in window.view.tool_buttons:
                button.set_sensitive(True)
            window.view.tool_buttons[i].set_sensitive(False)
            window.view.set_current_page(i)
        info.connect("content-object-set", infomenu_cb)
        return False
    gobject.timeout_add_seconds(1, f)
    #window.view.register_new_view(
    #    ViewContainer.ViewStruct(window.panedcontainer.informationcontainer,
    #                             gtk.ToolButton(gtk.STOCK_INFO)))

    #window.panedcontainer.informationcontainer
    #window.panedcontainer.pinbox

def deactivate(client, store, window):
    pass
