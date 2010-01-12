# -.- coding: utf-8 -.-
#
# GNOME Activity Journal
#
# Copyright © 2010 Seif Lotfy <seif@lotfy.com>
# Copyright © 2010 Randal Barlow <email.tehk@gmail.com>
# Copyright © 2010 Siegfried-Angel Gevatter Pujals <siegfried@gevatter.com>
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

iszeitgeist = True

from datetime import timedelta, datetime
import time
from zeitgeist.client import ZeitgeistClient
from zeitgeist.datamodel import Event, Subject, Interpretation, Manifestation, \
    ResultType

CLIENT = ZeitgeistClient()

def datelist(n, callback):
    today = int(time.mktime(time.strptime(time.strftime("%d %B %Y"), "%d %B %Y")))
    today = today - n*86400 
    
    x = []
    
    def _handle_find_events(ids):
        if len(ids) > 100:
            count = 101
        else:
            count = len(ids)
        x.append((today+len(x)*86400, count))
        if len(x) == n+1:
            callback(x)
    
    def get_ids(start, end):
        event_templates = [
            Event.new_for_values(interpretation=Interpretation.VISIT_EVENT.uri),
            Event.new_for_values(interpretation=Interpretation.MODIFY_EVENT.uri)]
        CLIENT.find_event_ids_for_templates(event_templates,
            _handle_find_events, [start * 1000, end * 1000],
            num_events=50000, result_type=0)
    
    for i in xrange(n+1):
       get_ids(today+i*86400, today+i*86400+86399)
