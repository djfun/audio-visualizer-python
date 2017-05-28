''' Title Text '''
import numpy
from PIL import Image, ImageDraw
from PyQt4 import uic
import os


class Component:
    def widget(self,parent):
        page = uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'text.ui'))
        return page
    def previewRender(self, previewWorker, widget):
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        im = Image.new("RGBA", (width, height),(0,0,0,0))

        return im

    def preFrameRender(self, **kwargs):
        pass
    def frameRender(self, moduleNo, frameNo):
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        im = Image.new("RGBA", (width, height),(0,0,0,0))

        return im

    '''
      self._image = ImageQt(im)
   
    self._image1 = QtGui.QImage(self._image)
    painter = QPainter(self._image1)
    font = titleFont
    font.setPixelSize(fontSize)
    painter.setFont(font)
    painter.setPen(QColor(*textColor))

    yPosition = yOffset

    fm = QtGui.QFontMetrics(font)
    if alignment == 0:      #Left
       xPosition = xOffset
    if alignment == 1:      #Middle
       xPosition = xOffset - fm.width(titleText)/2
    if alignment == 2:      #Right
       xPosition = xOffset - fm.width(titleText)
    painter.drawText(xPosition, yPosition, titleText)
    painter.end()

    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.ReadWrite)
    self._image1.save(buffer, "PNG")

    strio = io.BytesIO()
    strio.write(buffer.data())
    buffer.close()
    strio.seek(0)
    return Image.open(strio)
    '''
