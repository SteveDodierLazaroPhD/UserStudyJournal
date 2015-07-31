# -.- coding: utf-8 -.-

# Zeitgeist - GNOME Activity Journal Extension
#
# Copyright © 2010 Siegfried-Angel Gevatter Pujals <siegfried@gevatter.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
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

import time
import dbus
import logging

from _zeitgeist.engine import constants
from _zeitgeist.engine.extension import Extension
#from _zeitgeist.engine.sql import get_default_cursor

GAJ_DBUS_OBJECT_PATH = "/uk/ac/ucl/cs/study/multitasking/journal/activity"

log = logging.getLogger("zeitgeist.activity_journal")

class ActivityJournalExtension(Extension, dbus.service.Object):
    """
    This is a specialized extension which adds a new :const:`GetHistogramData`
    method to Zeitgeist for use by UCL Study Journal.
    """
    PUBLIC_METHODS = ["get_histogram_data"]

    def __init__ (self, engine):
        Extension.__init__(self, engine)
        dbus.service.Object.__init__(self, dbus.SessionBus(),
            GAJ_DBUS_OBJECT_PATH)
        
        self._engine = engine
        self._cursor = engine._cursor
    
    # PUBLIC
    def get_histogram_data(self):
        """ 
        FIXME: Please write me!
        """
        sql =  """SELECT
                strftime('%s', datetime(timestamp/1000, 'unixepoch'), 'start of day') AS daystamp,
                COUNT(*)
            FROM event
            GROUP BY daystamp
            ORDER BY daystamp DESC"""
        return self._cursor.execute(sql).fetchall()
    
    @dbus.service.method(constants.DBUS_INTERFACE,
                        in_signature="",
                        out_signature="a(tu)")
    def GetHistogramData(self):
        """
        FIXME: I do stuff.
        """
        return self.get_histogram_data()
