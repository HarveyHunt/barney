import struct
import time
import select
import argparse
import sys
import cairo
import pango
import pangocairo
import xcb
from xcb import xproto


class AtomCache(object):
    """
    A read only object that caches atom replies and cookies.

    Cookies are collected at initialisation and replies are only requested when
    they are actually needed.
    """
    def __init__(self, conn):
        self.atom_cookies = {}
        self.atoms = {}
        atom_names = ['_NET_WM_WINDOW_TYPE', '_NET_WM_WINDOW_TYPE_DOCK',
                        '_NET_WM_DESKTOP', '_NET_WM_STRUT_PARTIAL',
                        '_NET_WM_STRUT', '_NET_WM_STATE',
                        '_NET_WM_STATE_ABOVE', '_NET_WM_STATE_ABOVE',
                        '_NET_WM_NAME', '_NET_WM_WINDOW_OPACITY',
                        '_NET_WM_STATE_STICKY', '_NET_WM_ICON_NAME',
                        '_NET_WM_CLASS', 'UTF8_STRING']
        for name in atom_names:
            self.atom_cookies[name] = conn.core.InternAtomUnchecked(False,
                    len(name),
                    name)

    def __getitem__(self, key):
        if key in self.atoms:
            return self.atoms[key]
        elif key in self.atom_cookies:
            self.atoms[key] = self.atom_cookies[key].reply().atom
            return self.atoms[key]
        else:
            raise KeyError(str(key))

    def __len__(self):
        return len(self.atom_cookies)

class Bar(object):
    """
    The main class of this application. It accepts a config and then proceeds
    to draw to the window that it creates using Pango and Cairo. It reads text
    from STDIN, has full support for pango markup and also has its own in text
    formatting.
    """

    def __init__(self, config):
        self.config = config
        self.conn = xcb.connect()
        self.setup = self.conn.get_setup()
        self.window = self.conn.generate_id()
        self.pixmap = self.conn.generate_id()
        self.gc = self.conn.generate_id()
        self.cache = AtomCache(self.conn)

        self.conn.core.CreateWindow(self.setup.roots[0].root_depth, self.window,
                                self.setup.roots[0].root, 0, 0,
                                self.setup.roots[0].width_in_pixels,
                                self.config.height, 0, 
                                xproto.WindowClass.InputOutput,
                                self.setup.roots[0].root_visual,
                                xproto.CW.BackPixel |
                                xproto.CW.EventMask,
                                [self.setup.roots[0].white_pixel,
                                xproto.EventMask.ButtonPress |
                                xproto.EventMask.EnterWindow |
                                xproto.EventMask.LeaveWindow |
                                xproto.EventMask.Exposure])

        self.conn.core.CreatePixmap(self.setup.roots[0].root_depth, self.pixmap,
                                self.setup.roots[0].root,
                                self.setup.roots[0].width_in_pixels, 
                                self.config.height)

        self.conn.core.CreateGC(self.gc, self.setup.roots[0].root,
                                xproto.GC.Foreground | xproto.GC.Background,
                                [self.setup.roots[0].black_pixel,
                                self.setup.roots[0].white_pixel])

        self.surf = cairo.XCBSurface(self.conn, self.pixmap,
                                self.setup.roots[0].allowed_depths[0].visuals[0],
                                self.setup.roots[0].width_in_pixels,
                                self.config.height)

        self.win_attr = self.conn.core.GetGeometry(self.window).reply()
        self.set_emwh()
        self.setup_cairo()
        self.setup_pango_cairo()
        self.conn.core.MapWindow(self.window)
        self.conn.flush()

    def setup_cairo(self):
        """
        Create the Cairo context and set the operator.
        """
        self.ctx = cairo.Context(self.surf)
        self.ctx.set_operator(cairo.OPERATOR_SOURCE)

    def setup_pango_cairo(self):
        """
        Creates a PangoCairo context, sets the antialiasing method for it,
        generates a blank layout and then loads a font.
        """
        self.pc_ctx = pangocairo.CairoContext(self.ctx)
        self.pc_ctx.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
        self.layout = self.pc_ctx.create_layout()
        font_name = self.config.font
        self.layout.set_font_description(pango.FontDescription(font_name + ' ' +
                                                self.config.fontsize))

    def draw_bg(self):
        """
        Draws the background of the bar using the background colour
        provided by the config.
        """
        self.ctx.set_source_rgb(*self.config.background)
        self.ctx.paint()

    def draw_text(self, markup, align):
        """
        Draws text that is passed in the markup parameter. The align
        parameter is used to determine how the text should be drawn.
        All of the text is built into a single string, joined by the
        seperator defined in the config, in order to reduce the complexity
        of having multiple segments of text aligned the same way.

        markup: A list of strings that contain markup and are to be rendered
        on the bar.

        align: A string representing the possible alignment of the text. Cairo
        will default to the left side of the bar, so this is assumed to be the
        default. Can have the possible values: center, left and right.
        """
        self.ctx.save()
        self.ctx.set_source_rgb(*self.config.foreground)
        markup = self.config.seperator.join(markup)
        self.layout.set_markup(markup)
        self.pc_ctx.update_layout(self.layout)
        if align == 'right':
            self.ctx.translate(self.setup.roots[0].width_in_pixels -
                            self.layout.get_pixel_size()[0], 0)

        elif align == 'center':
            self.ctx.translate((self.setup.roots[0].width_in_pixels / 2) -
                            (self.layout.get_pixel_size()[0] / 2), 0)

        self.pc_ctx.show_layout(self.layout)
        self.conn.core.CopyArea(self.pixmap, self.window, self.gc, 0, 0, 0, 0,
                self.setup.roots[0].width_in_pixels, self.config.height)
        self.ctx.restore()

    def set_emwh(self):
        """
        Sets the EMWHs for the application. A full list of EMWHs can be found
        here: http://standards.freedesktop.org/wm-spec/wm-spec-latest.html
        """
        strut = [0] * 12
        if self.config.bottom:
            strut[3] = self.config.height
            strut[11] = self.setup.roots[0].width_in_pixels
        else:
            strut[2] = self.config.height
            strut[9] = self.setup.roots[0].width_in_pixels

        self.change_x_prop(xproto.PropMode.Replace, '_NET_WM_NAME',
                            'UTF8_STRING', 8, len("Barney"), "Barney")

        self.change_x_prop(xproto.PropMode.Replace, '_NET_WM_ICON_NAME',
                            'UTF8_STRING', 8, len("Barney"), "Barney")

        self.change_x_prop(xproto.PropMode.Replace, '_NET_WM_CLASS',
                            'UTF8_STRING', 8, len("Barney"), "Barney")

        if self.config.opacity != 1.0:
            self.change_x_prop(xproto.PropMode.Replace, '_NET_WM_WINDOW_OPACITY',
                            xproto.Atom.CARDINAL, 32, 1,
                            struct.pack('I',
                                int(self.config.opacity * 0xffffffff)))

        # Partial strut is in the form: {left, right, top, bottom, left_start_y,
        # left_end_y,right_start_y, right_end_y, top_start_x, top_end_x,
        # bottom_start_x, bottom_end_x}

        self.change_x_prop(xproto.PropMode.Replace, '_NET_WM_STRUT_PARTIAL',
                        xproto.Atom.CARDINAL, 32, 12,
                        struct.pack('I' * 12, *strut))

        self.change_x_prop(xproto.PropMode.Replace, '_NET_WM_STRUT',
                xproto.Atom.CARDINAL, 32, 4, struct.pack('IIII', *strut[0:4]))

        self.change_x_prop(xproto.PropMode.Replace, '_NET_WM_WINDOW_TYPE',
                        xproto.Atom.ATOM, 32, 1,
                        struct.pack('I', self.cache['_NET_WM_WINDOW_TYPE_DOCK']))

        self.change_x_prop(xproto.PropMode.Replace, '_NET_WM_STATE',
                        xproto.Atom.ATOM, 32, 1,
                        struct.pack('I', self.cache['_NET_WM_STATE_ABOVE']))

        self.change_x_prop(xproto.PropMode.Append, '_NET_WM_STATE',
                        xproto.Atom.ATOM, 32, 1,
                        struct.pack('I', self.cache['_NET_WM_STATE_STICKY']))

        self.change_x_prop(xproto.PropMode.Replace, '_NET_WM_DESKTOP',
                        xproto.Atom.CARDINAL, 32, 1, struct.pack('I', 0xFFFFFFFF))

    def change_x_prop(self, mode, prop, prop_type, form, data_len, data):
        """
        A helper function to change X properties. If a property or
        property type are strings, the AtomCache is accessed in order to find
        out their atom values.
        """
        if type(prop) is str:
            prop = self.cache[prop]
        if type(prop_type) is str:
            prop_type = self.cache[prop_type]
        self.conn.core.ChangePropertyChecked(mode, self.window, prop,
                                prop_type, form, data_len, data).check()

    def run(self):
        """
        The main loop of the application. Listens for input on STDIN and only
        redraws if input is discovered. All event handling logic should be
        placed in here.
        """
        while True:
            try:
                event = self.conn.poll_for_event()
            except xcb.ProtocolException, error:
                print 'Protocol error %s received.' % error.__class__.__name__
                break

            if isinstance(event, xproto.ExposeEvent):
                self.conn.core.CopyArea(self.pixmap, self.window, self.gc, 0, 0,
                            0, 0, self.setup.roots[0].width_in_pixels,
                            self.config.height)

            if select.select([sys.stdin,], [], [], 0.0):
                markup = sys.stdin.readline()
                time.sleep(0.1)
                if markup != '':
                    self.draw_bg()
                    markup = self.parse(markup)
                    for alignment in markup:
                        if markup[alignment] != []:
                            self.draw_text(markup[alignment], alignment)
            self.conn.flush()

    def parse(self, markup):
        """
        Parses the incoming markup and returns a dictionary containing the
        markup and how it should be aligned, once the text formatters have been
        stripped and interpreted.

        markup: A string of Pango markup passed from STDIN. It can contain the
        text formatters: ^l, ^c, ^r.

        Returns a dictionary of the markup, with the keys being the alignment
        of the markup.
        """
        leftMarkup, centerMarkup, rightMarkup = [], [], []
        markup = markup.split('^')
        for section in markup:
            if len(section) != 0:
                if section[0] == 'l':
                    leftMarkup.append(section[1:])
                elif section[0] == 'c':
                    centerMarkup.append(section[1:])
                elif section[0] == 'r':
                    rightMarkup.append(section[1:])
        return {'left': leftMarkup, 'center': centerMarkup,
                'right': rightMarkup}



def main():
    parser = argparse.ArgumentParser(description=
                                'A lightweight X11 bar written in Python.',
                                conflict_handler='resolve')
    parser.add_argument('-h', '--height', type=int, required=True)
    parser.add_argument('-fg', '--foreground', type=str, default='#FFFFFF')
    parser.add_argument('-bg', '--background', type=str, default='#000000')
    parser.add_argument('-b', '--bottom', action='store_true', default=False)
    parser.add_argument('-o', '--opacity', type=float, default=1)
    parser.add_argument('-f', '--font', default="Sans")
    parser.add_argument('-s', '--seperator', type=str, default='')
    parser.add_argument('-fs', '--fontsize', default="12")
    args = parser.parse_args()
    args.foreground = tuple(ord(c) / 255.0 for c in 
                            args.foreground.strip('#').decode('hex'))
    args.background = tuple(ord(c) / 255.0 for c in
                            args.background.strip('#').decode('hex'))

    b = Bar(args)
    b.run()

if __name__ == '__main__':
    main()
