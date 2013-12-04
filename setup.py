#!/usr/bin/python2
import os
from setuptools import setup
from setuptools import find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(name='barney',
      packages=find_packages(),
      version='0.1',
      description='A lightweight X11 bar with support for opacity, unicode and multiple alignments of text',
      author='Harvey Hunt',
      url='https://github.com/HarveyHunt/barney',
      author_email='harveyhuntnexus@gmail.com',
      license="GPLv3",
      keywords="python xpyb X11 bar dzen2 xmobar display opacity customisation",
      install_requires=[],
      long_description=read('README.md'),
      entry_points={'console_scripts': ['barney=barney.bar:main']})
