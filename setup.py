#! /usr/bin/env python

import os
from glob import glob
from distutils.core import setup
from distutils.command.install import install as orig_install
from DistUtilsExtra.command import *

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
        raise NotImplementedError, "Installation is not yet available."
        """
        if self.root and self.prefix:
            self._destdir = os.path.join(self.root, self.prefix.strip('/'))
        else:
            self._destdir = self.prefix
        orig_install.run(self)
        # Ensure the needed directories exist
        self._create_directory('bin')
        self._create_directory('share/pixmaps')
        # Create a symlink for the executable file
        self._create_symlink('share/espeak-gui/espeak-gui', 'bin/espeak-gui')
        # Create a symlink for the icon
        self._create_symlink('share/espeak-gui/data/espeak-gui.png',
            'share/pixmaps/espeak-gui.png')
        """

setup(
    name = 'GNOME Activity Journal',
    version = '0.1',
    description = 'Zeitgeist GUI',
    author = 'GNOME Activity Journal Developers',
    author_email = 'zeitgeist@lists.launchpad.net',
    url = 'https://launchpad.net/gnome-activity-journal',
    license = 'GPL',
    data_files = [
        #('share/espeak-gui', ['espeak-gui']),
        #('share/espeak-gui/data', glob('data/*')),
        #('share/espeak-gui/src', glob('src/*')),
        ],
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
