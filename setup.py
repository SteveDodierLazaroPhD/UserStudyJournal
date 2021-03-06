#! /usr/bin/env python
# -.- coding: utf-8 -.-
#
# GNOME Activity Journal - Installation script
#
# Copyright © 2009-2010 Siegfried Gevatter <siegfried@gevatter.com>
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

from __future__ import with_statement
import os
from glob import glob
from distutils.core import setup
from DistUtilsExtra.command import *

class _build_i18n(build_i18n.build_i18n):

	def run(self):
		# Generate POTFILES.in from POTFILES.in.in
		if os.path.isfile("po/POTFILES.in.in"):
			lines = []
			with open("po/POTFILES.in.in") as f:
				for line in f:
					lines.extend(glob(line.strip()))
			with open("po/POTFILES.in", "w") as f:
				f.write("\n".join(lines) + "\n")
		
		build_i18n.build_i18n.run(self)

def recursive_install(dst, directory, prefix=None, ext=None):
    l = []
    this = []
    for name in glob('%s/*' % directory):
        if os.path.isdir(name):
            l.extend(recursive_install(dst, name, os.path.join(prefix,
                os.path.basename(name)) if prefix is not None else None))
        elif not ext or os.path.splitext(name)[1] in ext:
            this.append(name)
    l.append((os.path.join(dst,
        prefix if prefix is not None else directory), this))
    return l

def list_from_lists(*args):
    l = []
    for arg in args:
        l.extend(arg)
    return l

try:
    VERSION = [line for line in open('src/config.py')
        if line.startswith('VERSION')][0].split('"')[1]
except (IOError, IndexError):
    VERSION = 'unknown'

setup(
    name = 'ucl-study-journal',
    version = VERSION,
    description = 'GUI to browse and search your Zeitgeist activities',
    long_description = \
        'The UCL Study Journal is a tool for easily browsing and finding '\
        'files on your computer. It shows a chronological journal of all '\
        'file activity and supports full-text search through Tracker.',
    author = 'GNOME Activity Journal Developers, forked by Steve Dodier-Lazaro',
    author_email = 'sidnioulz@gmail.com (original developers: zeitgeist@lists.launchpad.net)',
    url = 'https://launchpad.net/activityfinder',
    license = 'GPLv3+',
    platforms = ['GNU/Linux'],
    data_files = list_from_lists(
        [('bin/', ['ucl-study-journal'])],
        [('share/ucl-study-journal/data', glob('data/*.svg'))],
        [('share/ucl-study-journal/data', glob('data/*.png'))],
        [('share/ucl-study-journal/data/zlogo', glob('data/zlogo/*.png'))],
        [('share/pixmaps/', ['data/ucl-study-journal.xpm'])],
        recursive_install('share/icons/hicolor', 'data/icons/hicolor/', '',
            ext=['.png', '.svg']),
        recursive_install('share/ucl-study-journal', 'src/', ext=['.py']),
        [('share/man/man1/', ['extra/ucl-study-journal.1'])],
        [('share/ucl-study-journal/fungtk', glob('fungtk/*.py'))],
        [('share/zeitgeist/_zeitgeist/engine/extensions/', glob('extension/*.py'))],
        ),
    cmdclass = {
        'build': build_extra.build_extra,
        'build_i18n': _build_i18n,
        #'build_help':  build_help.build_help,
        #'build_icons': build_icons.build_icons,
        },
    classifiers = [
        # http://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI-Approved :: GNU General Public License (GPL)',
        'Intended Audience :: End Users/Desktop',
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Environment :: X11 Applications :: GTK',
        ]
    )
