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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import time
import gtk

import logwidget
from eventhandler import get_dayevents

from zeitgeist.datamodel import Interpretation

FILETYPES ={
    Interpretation.VIDEO.uri : "Video",
    Interpretation.MUSIC.uri : "Music",
    Interpretation.DOCUMENT.uri : "Document",
    Interpretation.IMAGE.uri : "Image",
    Interpretation.SOURCECODE.uri : "Source Code",
    Interpretation.UNKNOWN.uri : "Unknown",
    }

def get_tab_text_custom(obj):
    text = obj.subjects[0].text
    t1 = "<b>" + text + "</b>"
    interpretation = obj.subjects[0].interpretation
    t2 = FILETYPES[obj.subjects[0].interpretation] if interpretation in FILETYPES.keys() else "Unknown"
    t3 = time.strftime("%H:%M", time.localtime(int(obj.timestamp)/1000))
    return t1 + "\n" + t2 + "\n" + t3


class DetailedWindow(gtk.ScrolledWindow):
    day_i = 0
    def __init__(self):
        super(gtk.ScrolledWindow, self).__init__()
        self.set_shadow_type(gtk.SHADOW_NONE)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.view = logwidget.DetailedView()
        self.view.set_text_handler(get_tab_text_custom)
        self.view.connect("item-clicked", self.clicked_func)
        self.view.connect("private-area-clicked", self.arrow_clicked_func)
        self.add_with_viewport(self.view)
        self.get_children()[0].set_shadow_type(gtk.SHADOW_NONE)
        for widget in self:
            self.set_shadow_type(gtk.SHADOW_NONE)


    def clicked_func(self, widget, zevent):
        """
        A sample event for clicks
        """
        print zevent.subjects[0].text, time.strftime("Day:%d Time:%H:%S", time.localtime(int(zevent.timestamp)/1000))

    def arrow_clicked_func(self, widget, arrow):
        if arrow == gtk.ARROW_LEFT:
            self.day_i = self.day_i + 86400
            start = time.time() - day - self.day_i
            end = start + 86400
        elif arrow == gtk.ARROW_RIGHT:
            self.day_i = self.day_i - 86400
            start = time.time() - day - self.day_i
            end = start + 86400
        get_dayevents(start*1000, end*1000, self.view.set_datastore)
        widget.queue_draw()


if __name__ == "__main__":
    win =  gtk.Window()
    scroll = DetailedWindow()
    day = (int(time.time() - time.timezone) % 86400) #- time.timezone
    start = time.time() - day
    end = start + 86400
    get_dayevents(start*1000, end*1000, scroll.view.set_datastore)
    win.add(scroll)
    win.connect("delete_event", gtk.main_quit)
    win.show_all()
    gtk.main()















