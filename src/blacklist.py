# -.- coding: utf-8 -.-
#
# History Manager
#
# Copyright © 2011 Collabora Ltd.
#             By Siegfried-Angel Gevatter Pujals <siegfried@gevatter.com>
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

from itertools import imap

from zeitgeist.datamodel import Event, Subject

from external import CLIENT, CLIENT_VERSION

class OldBlacklistInterface:

    INCOGNITO = Event.new_for_values()

    def __init__(self):
        self._blacklist = CLIENT._iface.get_extension('Blacklist', 'blacklist')

    def _get_blacklist_templates(self):
        return map(Event.new_for_struct, self._blacklist.GetBlacklist())

    def _add_blacklist_template(self, template):
        templates = self._get_blacklist_templates()
        templates.append(template)
        self._blacklist.SetBlacklist(templates)

    def _remove_blacklist_template(self, template):
        templates = self._get_blacklist_templates()
        updated_templates = list(templates)
        for template in templates:
            if self.INCOGNITO.matches_template(template):
                updated_templates.remove(template)
        self._blacklist.SetBlacklist(updated_templates)

    def get_incognito(self):
        templates = self._get_blacklist_templates()
        return any(imap(self.INCOGNITO.matches_template, templates))

    def set_incognito(self, enabled):
        if enabled:
            self._add_blacklist_template(self.INCOGNITO)
        else:
            self._remove_blacklist_template(self.INCOGNITO)

class NewBlacklistInterface:

    INCOGNITO = Event.new_for_values()
    INCOGNITO_ID = 'incognito'

    def __init__(self):
        self._blacklist = CLIENT._iface.get_extension('Blacklist', 'blacklist')

    def _get_blacklist_templates(self):
        return self._blacklist.GetTemplates()

    def _add_blacklist_template(self, template):
        self._blacklist.AddTemplate(self.INCOGNITO_ID, self.INCOGNITO)

    def _remove_blacklist_template(self, template_id):
        self._blacklist.RemoveTemplate(self.INCOGNITO_ID)

    def get_incognito(self):
        templates = self._get_blacklist_templates()
        return self.INCOGNITO_ID in templates

    def set_incognito(self, enabled):
        if enabled:
            self._add_blacklist_template(self.INCOGNITO)
        else:
            self._remove_blacklist_template(self.INCOGNITO)

if CLIENT_VERSION >= [0, 7, 99]:
	BLACKLIST = NewBlacklistInterface()
else:
	BLACKLIST = OldBlacklistInterface()
