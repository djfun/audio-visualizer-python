from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageQt import ImageQt
import core
import time
from queue import Queue, Empty
import numpy

class Worker(QtCore.QObject):

  imageCreated = pyqtSignal(['QImage'])

  def __init__(self, parent=None, queue=None):
    QtCore.QObject.__init__(self)
    parent.newTask.connect(self.createPreviewImage)
    parent.processTask.connect(self.process)
    self.core = core.Core()
    self.queue = queue


  @pyqtSlot(str, str, QtGui.QFont, int, int, int, int, tuple, tuple)
  def createPreviewImage(self, backgroundImage, titleText, titleFont, fontSize,\
                            alignment, xOffset, yOffset, textColor, visColor):
    # print('worker thread id: {}'.format(QtCore.QThread.currentThreadId()))
    dic = {
      "backgroundImage": backgroundImage,
      "titleText": titleText,
      "titleFont": titleFont,
      "fontSize": fontSize,
      "alignment": alignment,
      "xoffset": xOffset,
      "yoffset": yOffset,
      "textColor" : textColor,
      "visColor" : visColor
    }
    self.queue.put(dic)

  @pyqtSlot()
  def process(self):
    try:
      nextPreviewInformation = self.queue.get(block=False)
      while self.queue.qsize() >= 2:
        try:
          self.queue.get(block=False)
        except Empty:
          continue

      bgImage = self.core.parseBaseImage(\
                   nextPreviewInformation["backgroundImage"],
                   preview=True
                )
      if bgImage == []:
        bgImage = ''
      else:
        bgImage = bgImage[0]

      im = self.core.drawBaseImage(
        bgImage,
        nextPreviewInformation["titleText"],
        nextPreviewInformation["titleFont"],
        nextPreviewInformation["fontSize"],
        nextPreviewInformation["alignment"],
        nextPreviewInformation["xoffset"],
        nextPreviewInformation["yoffset"],
        nextPreviewInformation["textColor"],
        nextPreviewInformation["visColor"])
      spectrum = numpy.fromfunction(lambda x: 0.008*(x-128)**2, (255,), dtype="int16")

      im = self.core.drawBars(spectrum, im, nextPreviewInformation["visColor"])

      self._image = ImageQt(im)
      self._previewImage = QtGui.QImage(self._image)

      self._scaledPreviewImage = self._previewImage.scaled(320, 180, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)

      self.imageCreated.emit(self._scaledPreviewImage)
    except Empty:
      True
