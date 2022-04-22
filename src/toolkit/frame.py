'''
    Common tools for drawing compatible frames in a Component's frameRender()
'''
from PyQt5 import QtGui
from PIL import Image
from PIL.ImageQt import ImageQt
import sys
import os
import math
import logging

from .. import core


log = logging.getLogger('AVP.Toolkit.Frame')


class FramePainter(QtGui.QPainter):
    '''
        A QPainter for a blank frame, which can be converted into a
        Pillow image with finalize()
    '''
    def __init__(self, width, height):
        image = BlankFrame(width, height)
        self.image = QtGui.QImage(ImageQt(image))
        super().__init__(self.image)

    def setPen(self, penStyle):
        if type(penStyle) is tuple:
            super().setPen(PaintColor(*penStyle))
        else:
            super().setPen(penStyle)

    def finalize(self):
        log.verbose("Finalizing FramePainter")
        imBytes = self.image.bits().asstring(self.image.byteCount())
        frame =  Image.frombytes(
            'RGBA', (self.image.width(), self.image.height()), imBytes
        )
        self.end()
        return frame


class PaintColor(QtGui.QColor):
    '''Reverse the painter colour if the hardware stores RGB values backward'''
    def __init__(self, r, g, b, a=255):
        if sys.byteorder == 'big':
            super().__init__(r, g, b, a)
        else:
            super().__init__(b, g, r, a)


def scale(scalePercent, width, height, returntype=None):
    width = (float(width) / 100.0) * float(scalePercent)
    height = (float(height) / 100.0) * float(scalePercent)
    if returntype == str:
        return (str(math.ceil(width)), str(math.ceil(height)))
    elif returntype == int:
        return (math.ceil(width), math.ceil(height))
    else:
        return (width, height)


def defaultSize(framefunc):
    '''Makes width/height arguments optional'''
    def decorator(*args):
        if len(args) < 2:
            newArgs = list(args)
            if len(args) == 0 or len(args) == 1:
                height = int(core.Core.settings.value("outputHeight"))
                newArgs.append(height)
            if len(args) == 0:
                width = int(core.Core.settings.value("outputWidth"))
                newArgs.insert(0, width)
            args = tuple(newArgs)
        return framefunc(*args)
    return decorator


def FloodFrame(width, height, RgbaTuple):
    return Image.new("RGBA", (width, height), RgbaTuple)


@defaultSize
def BlankFrame(width, height):
    '''The base frame used by each component to start drawing.'''
    return FloodFrame(width, height, (0, 0, 0, 0))


@defaultSize
def Checkerboard(width, height):
    '''
        A checkerboard to represent transparency to the user.
        TODO: Would be cool to generate this image with numpy instead.
    '''
    log.debug('Creating new %s*%s checkerboard' % (width, height))
    image = FloodFrame(1920, 1080, (0, 0, 0, 0))
    image.paste(Image.open(
        os.path.join(core.Core.wd, 'gui', "background.png")),
        (0, 0)
    )
    image = image.resize((width, height))
    return image
