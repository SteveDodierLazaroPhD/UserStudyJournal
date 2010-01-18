# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2009-2010 Siegfried Gevatter <siegfried@gevatter.com>
# Copyright © 2007 Alex Graveley <alex@beatniksoftware.com>
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

import os.path
import gobject
import urllib
import os
import gtk
import gnome.ui
import gettext
import zipfile

from tempfile import NamedTemporaryFile

from fungtk.quickconf import QuickConf
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation

class Source:

    def __init__(self, interpretation, icon, desc_sing, desc_pl):
        self.name = interpretation.name
        self.icon = icon
        self._desc_sing = desc_sing
        self._desc_pl = desc_pl

    def group_label(self, num):
        return gettext.ngettext(self._desc_sing, self._desc_pl, num)

SUPPORTED_SOURCES = {
    # TODO: Please change this description stuff. To give a single reason,
    # saying "videos watched" is a lie because you may have edited them, or
    # it may just be a "bookmark event".
    #
    # Also, how this is implemented now won't work fine with i18n.
    Interpretation.VIDEO.uri: Source(Interpretation.VIDEO, "gnome-mime-video", _("Worked with a Video"), _("Worked with Videos")),
    Interpretation.MUSIC.uri: Source(Interpretation.MUSIC, "gnome-mime-audio", _("Worked with Audio"), _("Worked with Audio")),
    Interpretation.IMAGE.uri: Source(Interpretation.IMAGE, "image", _("Worked with an Image"), _("Worked with Images")),
    Interpretation.DOCUMENT.uri: Source(Interpretation.DOCUMENT, "stock_new-presentation", _("Edited or Read Document"), _("Edited or Read Documents")),
    Interpretation.SOURCECODE.uri: Source(Interpretation.SOURCECODE, "applications-development", _("Edited or Read Code"), _("Edited or Read Code")),
    Interpretation.UNKNOWN.uri: Source(Interpretation.UNKNOWN, "applications-other", _("Other Activity"), _("Other Activities")),
}

settings = QuickConf('/apps/gnome-activity-journal')
