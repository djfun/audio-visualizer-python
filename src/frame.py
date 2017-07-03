'''
    Common tools for drawing compatible frames in a Component's frameRender()
'''
from PyQt5 import QtGui
from PIL import Image
from PIL.ImageQt import ImageQt
import sys


class FramePainter(QtGui.QPainter):
    def __init__(self, width, height):
        image = BlankFrame(width, height)
        self.image = ImageQt(image)
        super().__init__(self.image)

    def setPen(self, RgbTuple):
        if sys.byteorder == 'big':
            color = QtGui.QColor(*RgbTuple)
        else:
            color = QtGui.QColor(*RgbTuple[::-1])
        super().setPen(QtGui.QColor(color))

    def finalize(self):
        self.end()
        imBytes = self.image.bits().asstring(self.image.byteCount())

        return Image.frombytes(
            'RGBA', (self.image.width(), self.image.height()), imBytes
        )

class PaintColor(QtGui.QColor):
    def __init__(self, r, g, b, a=255):
        if sys.byteorder == 'big':
            super().__init__(r, g, b, a)
        else:
            super().__init__(b, g, r, a)

def FloodFrame(width, height, RgbaTuple):
    return Image.new("RGBA", (width, height), RgbaTuple)

def BlankFrame(width, height):
    return FloodFrame(width, height, (0, 0, 0, 0))
