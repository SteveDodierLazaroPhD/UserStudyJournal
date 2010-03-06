# -.- coding: utf-8 -.-
#
# Filename
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

# Purpose:

import cairo
import gobject
import gtk
import os
import pango
import pangocairo
import time

from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType, TimeRange

from common import *

from thumb import ImageView
from gio_file import GioFile

CLIENT = ZeitgeistClient()


class RelatedPane(ImageView):
    """
    ...............
    .             . <--- Related files
    ...............
    """
    def __init__(self):
        super(RelatedPane, self).__init__()
        self.set_size_request(int(self.child_height*1.9), self.child_width)
        self.set_orientation(gtk.ORIENTATION_HORIZONTAL)


class InformationPane(gtk.Frame):
    """
    . . . . . . . .
    .             .
    .    Info     .
    .             .
    .             .
    . . . . . . . .
    """
    def __init__(self):
        """"""
        super(InformationPane, self).__init__()
        self.image = gtk.Image()
        self.add(self.image)
        self.set_shadow_type(gtk.SHADOW_IN)
        self.label = gtk.Label()
        self.set_label_widget(self.label)

    def set_uri(self, uri):
        """
        :param uri:
        """
        gfile = GioFile.create(uri)
        if gfile:
            if gfile.has_preview():
                pixbuf = gfile.get_thumbnail(size=SIZE_LARGE, border=3)
            else:
                pixbuf = gfile.get_icon(size=256)
            self.image.set_from_pixbuf(pixbuf)
            filename = os.path.basename(uri).replace("&", "&amp;")
            self.label.set_markup("<span size='18336'>" + filename + "</span>")


class InformationWindow(gtk.Window):
    """
    . . . . . . . .
    .             .
    .    Info     .
    .             .
    .             .
    . . . . . . . .
    ...............
    .             . <--- Related files
    ...............
    """
    def __init__(self):
        super(InformationWindow, self).__init__()
        vbox = gtk.VBox()
        vbox.set_border_width(10)
        self.infopane = InformationPane()
        self.relatedpane = RelatedPane()
        vbox.pack_start(self.infopane, True, True, 10)
        scrolledwindow = gtk.ScrolledWindow()
        scrolledwindow.set_shadow_type(gtk.SHADOW_IN)
        scrolledwindow.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_NEVER)
        scrolledwindow.add(self.relatedpane)
        vbox.pack_end(scrolledwindow, False, False, 10)
        self.add(vbox)
        self.set_size_request(500, 600)
        self.connect("delete-event", lambda w, e: w.hide() or True)

    def event_request_handler(self, uris):
        """
        :params uris: a list of uris which are related to the windows current uri
        Seif look here
        """
        print "Request"
        for uri in uris: print uri
        end = time.time() * 1000
        start = end - 60*60*14*1000
        templates = []
        def _handle_events(events):
            self.relatedpane.set_model_from_list(events)

        for uri in uris:
            templates += [
                Event.new_for_values(interpretation=Interpretation.VISIT_EVENT.uri, subject_uri=uri),
                Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri, subject_uri=uri),
                Event.new_for_values(interpretation=Interpretation.CREATE_EVENT.uri, subject_uri=uri),
                Event.new_for_values(interpretation=Interpretation.OPEN_EVENT.uri, subject_uri=uri)
            ]
        CLIENT.find_events_for_templates(templates, _handle_events,
                                         [start, end], num_events=50000,
                                         result_type=ResultType.MostRecentSubjects)
    def set_uri(self, uri):
        """
        :param uri: a uri which is set as the window's current focus
        """
        self.infopane.set_uri(uri)
        CLIENT.find_related_uris_for_uris([uri], self.event_request_handler)
        self.show_all()


InformationWindow = InformationWindow()
