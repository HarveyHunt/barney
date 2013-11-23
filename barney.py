import struct
import time
import select
import argparse
import sys
import cairo
import pango
import pangocairo
import xcb
from xcb.xproto import *

class AtomCache(object):
    """
    A read only object that caches atom replies and cookies. 

    Cookies are collected at initialisation and replies are only requested when
    they are actually needed.
    """
    def __init__(self):
        self.atomCookies = {}
        self.atoms = {}
        atomNames = ['_NET_WM_WINDOW_TYPE', '_NET_WM_WINDOW_TYPE_DOCK',
                        '_NET_WM_DESKTOP', '_NET_WM_STRUT_PARTIAL',
                        '_NET_WM_STRUT', '_NET_WM_STATE',
                        '_NET_WM_STATE_ABOVE', '_NET_WM_STATE_ABOVE',
                        '_NET_WM_NAME', '_NET_WM_WINDOW_OPACITY',
                        '_NET_WM_STATE_STICKY', '_NET_WM_ICON_NAME',
                        '_NET_WM_CLASS', 'UTF8_STRING']
        for name in atomNames:
            self.atomCookies[name] = conn.core.InternAtomUnchecked(False,
                    len(name),
                    name)

    def __getitem__(self, key):
        if key in self.atoms:
            return self.atoms[key]
        elif key in self.atomCookies:
            self.atoms[key] = self.atomCookies[key].reply().atom
            return self.atoms[key]
        else:
            raise KeyError(str(key))

    def __len__(self):
        return len(self.atomCookies)

class Bar(object):

    def __init__(self, config):
        self.config = config
        self.window = conn.generate_id()
        self.pixmap = conn.generate_id()
        self.gc = conn.generate_id() 
        self.cache = AtomCache()
        self.text = ''

        conn.core.CreateWindow(setup.roots[0].root_depth, self.window,
                                setup.roots[0].root, self.config.x, self.config.y,
                                self.config.width, self.config.height, 0,
                                WindowClass.InputOutput,
                                setup.roots[0].root_visual, CW.BackPixel |
                                CW.EventMask, [setup.roots[0].white_pixel,
                                EventMask.ButtonPress | EventMask.EnterWindow |
                                EventMask.LeaveWindow | EventMask.Exposure])

        conn.core.CreatePixmap(setup.roots[0].root_depth, self.pixmap,
                                setup.roots[0].root, self.config.width,
                                self.config.height)

        conn.core.CreateGC(self.gc, setup.roots[0].root, GC.Foreground | GC.Background,
                            [setup.roots[0].black_pixel, setup.roots[0].white_pixel])

        self.surf = cairo.XCBSurface(conn, self.pixmap,
                                setup.roots[0].allowed_depths[0].visuals[0],
                                self.config.width, self.config.height)

        self.winAttr = conn.core.GetGeometry(self.window).reply()
        self.setXProperties()
        self.setupCairo()
        self.setupPangoCairo()
        conn.flush()

    def setupCairo(self):
        self.ctx = cairo.Context(self.surf)
        self.ctx.set_operator(cairo.OPERATOR_SOURCE)
        
    def setupPangoCairo(self):
        self.pcCtx = pangocairo.CairoContext(self.ctx)
        self.pcCtx.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
        self.layout = self.pcCtx.create_layout()
        fontName = self.config.font
        self.layout.set_font_description(pango.FontDescription(fontName + ' ' +
                                                self.config.fontsize))

    def draw(self):
        self.ctx.set_source_rgb(*self.config.background)
        self.ctx.paint()
        self.ctx.set_source_rgb(*self.config.foreground)
        self.layout.set_text(self.text)
        self.pcCtx.update_layout(self.layout)
        self.pcCtx.show_layout(self.layout)
        conn.core.CopyArea(self.pixmap, self.window, self.gc, 0, 0, 0, 0,
                self.config.width, self.config.height)
    
    def setXProperties(self):
        strut = [0] * 12
        if self.config.bottom:
            strut[3] = self.config.height
            strut[11] = self.config.width
        else:
            strut[2] = self.config.height
            strut[9] = self.config.width

        self.changeXProp(PropMode.Replace, '_NET_WM_NAME', 
                            'UTF8_STRING', 8, len("Barney"), "Barney")

        self.changeXProp(PropMode.Replace, '_NET_WM_ICON_NAME', 
                            'UTF8_STRING', 8, len("Barney"), "Barney")

        self.changeXProp(PropMode.Replace, '_NET_WM_CLASS', 
                            'UTF8_STRING', 8, len("Barney"), "Barney")

        if self.config.opacity != 1.0:
            self.changeXProp(PropMode.Replace, '_NET_WM_WINDOW_OPACITY',
                            Atom.CARDINAL, 32, 1,
                            struct.pack('I', int(self.config.opacity * 0xffffffff)))

        # Partial strut is in the form: {left, right, top, bottom, left_start_y,
        # left_end_y,right_start_y, right_end_y, top_start_x, top_end_x,
        # bottom_start_x, bottom_end_x}

        self.changeXProp(PropMode.Replace, '_NET_WM_STRUT_PARTIAL',
                        Atom.CARDINAL, 32, 12,
                        struct.pack('I' * 12, *strut))

        self.changeXProp(PropMode.Replace, '_NET_WM_STRUT',
                Atom.CARDINAL, 32, 4, struct.pack('IIII', *strut[0:4]))
        
        self.changeXProp(PropMode.Replace, '_NET_WM_WINDOW_TYPE',
                        Atom.ATOM, 32, 1,
                        struct.pack('I', self.cache['_NET_WM_WINDOW_TYPE_DOCK']))

        self.changeXProp(PropMode.Replace, '_NET_WM_STATE', 
                        Atom.ATOM, 32, 1,
                        struct.pack('I', self.cache['_NET_WM_STATE_ABOVE']))
    
        self.changeXProp(PropMode.Append, '_NET_WM_STATE',
                        Atom.ATOM, 32, 1,
                        struct.pack('I', self.cache['_NET_WM_STATE_STICKY']))

        self.changeXProp(PropMode.Replace, '_NET_WM_DESKTOP',
                        Atom.CARDINAL, 32, 1, struct.pack('I', 0xFFFFFFFF))

    def changeXProp(self, mode, prop, propType, form, dataLen, data):
        if type(prop) is str:
            prop = self.cache[prop]
        if type(propType) is str:
            propType = self.cache[propType]
        conn.core.ChangePropertyChecked(mode, self.window, prop,
                                propType, form, dataLen, data).check()

    def run(self):
        while True:
            if select.select([sys.stdin,], [], [], 0.0):
                self.text = sys.stdin.readline()
                time.sleep(0.1)
                self.draw()
            try:
                event = conn.poll_for_event()
            except xcb.ProtocolException, error:
                print 'Protocol error %s received.' % error.__class__.__name__
                break

            if isinstance(event, ExposeEvent):
                conn.core.CopyArea(self.pixmap, self.window, self.gc, 0, 0, 0,
                            0, self.config.width, self.config.height)
            elif isinstance(event, ButtonPressEvent):
                break
            conn.flush()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=
                                'A lightweight X11 bar written in Python.',
                                conflict_handler='resolve')
    parser.add_argument('-w', '--width', type=int, required=True)
    parser.add_argument('-h', '--height', type=int, required=True)
    parser.add_argument('-x', type=int, default=0)
    parser.add_argument('-y', type=int, default=0)
    parser.add_argument('-fg', '--foreground', type=str, default='#FFFFFF')
    parser.add_argument('-bg', '--background', type=str, default='#000000')
    parser.add_argument('-b', '--bottom', action='store_true', default=False)
    parser.add_argument('-o', '--opacity', type=float, default=1)
    parser.add_argument('-f', '--font', default="Sans")
    parser.add_argument('-fs', '--fontsize', default="12")
    args = parser.parse_args()
    args.foreground = tuple(ord(c) for c in args.foreground.strip('#').decode('hex'))
    args.background = tuple(ord(c) for c in args.background.strip('#').decode('hex'))

    conn = xcb.connect()
    setup = conn.get_setup()
    b = Bar(args)
    conn.core.MapWindow(b.window)
    conn.flush()
    b.run()
