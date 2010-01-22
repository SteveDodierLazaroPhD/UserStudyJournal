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
        # Symlink the 48x48 PNG icon into share/pixmaps
        self._create_symlink(
            'share/gnome-activity-journal/data/icons/hicolor/48x48/apps/' \
                'gnome-activity-journal.png',
            'share/pixmaps/gnome-activity-journal.png')
        # Symlink the icons so that the Journal can find them
        self._create_symlink(
            'share/icons/',
            'share/gnome-activity-journal/data/icons')

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
    name = 'gnome-activity-journal',
    version = VERSION,
    description = 'GUI to browse and search your Zeitgeist activities',
    long_description = \
        'GNOME Activity Journal is a tool for easily browsing and finding '\
        'files on your computer. It shows a chronological journal of all '\
        'file activity and supports full-text search through Tracker.',
    author = 'GNOME Activity Journal Developers',
    author_email = 'zeitgeist@lists.launchpad.net',
    url = 'https://launchpad.net/gnome-activity-journal',
    license = 'GPLv3+',
    platforms = ['GNU/Linux'],
    data_files = list_from_lists(
        [('share/gnome-activity-journal', ['gnome-activity-journal'])],
        [('share/gnome-activity-journal/data', glob('data/*.svg'))],
        [('share/pixmaps/', ['data/gnome-activity-journal.xpm'])],
        recursive_install('share/icons/hicolor', 'data/icons/hicolor/', '',
            ext=['.png', '.svg']),
        recursive_install('share/gnome-activity-journal', 'src/', ext=['.py']),
        [('share/man/man1/', ['extra/gnome-activity-journal.1'])],
        [('share/gnome-activity-journal/fungtk', glob('fungtk/*.py'))],
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
