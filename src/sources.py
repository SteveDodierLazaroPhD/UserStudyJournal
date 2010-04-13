# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2009-2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2009-2010 Siegfried Gevatter <siegfried@gevatter.com>
# Copyright © 2007 Alex Graveley <alex@beatniksoftware.com>
# Copyright © 2010 Markus Korn <thekorn@gmx.de>
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

import gettext

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
    # TODO: Move this into Zeitgeist's library, implemented properly
    Interpretation.VIDEO.uri: Source(Interpretation.VIDEO, "gnome-mime-video", _("Worked with a Video"), _("Worked with Videos")),
    Interpretation.MUSIC.uri: Source(Interpretation.MUSIC, "gnome-mime-audio", _("Worked with Audio"), _("Worked with Audio")),
    Interpretation.IMAGE.uri: Source(Interpretation.IMAGE, "image", _("Worked with an Image"), _("Worked with Images")),
    Interpretation.DOCUMENT.uri: Source(Interpretation.DOCUMENT, "stock_new-presentation", _("Edited or Read Document"), _("Edited or Read Documents")),
    Interpretation.SOURCECODE.uri: Source(Interpretation.SOURCECODE, "applications-development", _("Edited or Read Code"), _("Edited or Read Code")),
    Interpretation.IM_MESSAGE.uri: Source(Interpretation.IM_MESSAGE, "applications-internet", _("Conversation"), _("Conversations")),
    Interpretation.UNKNOWN.uri: Source(Interpretation.UNKNOWN, "applications-other", _("Other Activity"), _("Other Activities")),
}
