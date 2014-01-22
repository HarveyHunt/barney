barney
======

A lightweight X11 bar with support for opacity, unicode and multiple alignments of text.

Barney requires:
* [Python 2] (http://www.python.org/)
* [Cairo] (http://cairographics.org/)
* [PyCairo] (http://cairographics.org/pycairo/)
* [Pango] (http://www.pango.org/)
* [xpyb] (https://pypi.python.org/pypi/xpyb)

In order to get the correct PangoCairo support, it is easiest to install [PyGTK](http://www.pygtk.org/), at least
that is the case on Arch Linux.

Installing
======

Barney can be installed using the following commands (assuming that you have installed the dependencies):

    git clone https://github.com/HarveyHunt/barney
  
    cd barney
  
    sudo python2 setup.py install
  
Alternatively, it can installed from the [AUR](https://aur.archlinux.org/packages/barney-git/).

Arguments
=====

Barney waits for input to be passed over STDIN. Pango markup languages can be used, as described [here](http://www.pygtk.org/docs/pygtk/pango-markup-language.html).

Text can be aligned using the following formatters:
- **^l**: Align to the left.
- **^c**: Align centrally.
- **^r** Align to the right.

The following command line parameters can be passed to barney:
* **-h, --height**: The height, in pixels, of the bar.
* **-o, --opacity**: The level of opacity of the bar. 0 being transparent and 1.0 being opaque.
* **-fg, --foreground**: The colour of the text, expressed as a hex colour code.
* **-bg, --background**: The colour of the background, expressed as a hex colour code.
* **-b, --bottom**: Dock the bar at the bottom of the display.
* **-f, --font**: The name of the font to be used.
* **-fs, --fontsize**: The size of the font to be displayed.
* **-s, --seperator**: The seperator character to be used between text that is aligned in the same way.
