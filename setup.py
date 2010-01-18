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
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement
import os
from glob import glob
from distutils.core import setup
from distutils.command.install import install as orig_install
from DistUtilsExtra.command import *

if __name__ == "__main__":
    """ Generate POTFILES.in from POTFILES.in.in. """
    os.chdir(os.path.realpath(os.path.dirname(__file__)))
    if os.path.isfile("po/POTFILES.in.in"):
        lines = []
        with open("po/POTFILES.in.in") as f:
            for line in f:
                lines.extend(glob(line.strip()))
        with open("po/POTFILES.in", "w") as f:
            f.write("\n".join(lines) + "\n")

class _install(orig_install):
    
    def _create_symlink(self, src, dst):
        src = os.path.join(self.prefix, src)
        dst = os.path.join(self._destdir, dst)
        if not os.path.islink(dst):
            print 'Creating symlink "%s"...' % dst
            os.symlink(src, dst)
    
    def _create_directory(self, dir):
        dir = os.path.join(self._destdir, dir)
        if not os.path.isdir(dir):
            print 'Creating directory "%s"...' % dir
            os.mkdir(dir)
    
    def run(self):
        if self.root and self.prefix:
            self._destdir = os.path.join(self.root, self.prefix.strip('/'))
        else:
            self._destdir = self.prefix
        orig_install.run(self)
        # Ensure the needed directories exist
        self._create_directory('bin')
        self._create_directory('share/pixmaps')
        # Create a symlink for the executable file
        self._create_symlink(
            'share/gnome-activity-journal/gnome-activity-journal',
            'bin/gnome-activity-journal')
        # Create a symlink for the icon
        self._create_symlink(
            'share/gnome-activity-journal/data/icons/hicolor/scalable/'\
                'gnome-activity-journal.svg',
            'share/pixmaps/gnome-activity-journal.svg')

def recursive_install(dst, directory):
    l = []
    this = []
    for name in glob('%s/*' % directory):
        if os.path.isdir(name):
            l.extend(recursive_install(dst, name))
        else:
            this.append(name)
    l.append((os.path.join(dst, directory), this))
    return l

def list_from_lists(*args):
    l = []
    for arg in args:
        l.extend(arg)
    return l

setup(
    name = 'GNOME Activity Journal',
    version = '0.1',
    description = 'Zeitgeist GUI',
    author = 'GNOME Activity Journal Developers',
    author_email = 'zeitgeist@lists.launchpad.net',
    url = 'https://launchpad.net/gnome-activity-journal',
    license = 'GPL',
    data_files = list_from_lists(
        [('share/gnome-activity-journal', ['gnome-activity-journal'])],
        recursive_install('share/gnome-activity-journal', 'data/'),
        recursive_install('share/gnome-activity-journal', 'src/')
        ),
    cmdclass = {
        'install': _install,
        'build': build_extra.build_extra,
        'build_i18n': build_i18n.build_i18n,
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
