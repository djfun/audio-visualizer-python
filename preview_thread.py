from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSignal, pyqtSlot
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
    self.core.settings = parent.settings
    self.stackedWidget = parent.window.stackedWidget


  @pyqtSlot(str, list)
  def createPreviewImage(self, backgroundImage, components):
    # print('worker thread id: {}'.format(QtCore.QThread.currentThreadId()))
    dic = {
      "backgroundImage": backgroundImage,
      "components": components,
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

      im = self.core.drawBaseImage(bgImage)
      width = int(self.core.settings.value('outputWidth'))
      height = int(self.core.settings.value('outputHeight'))
      frame = Image.new("RGBA", (width, height),(0,0,0,255))
      frame.paste(im)

      components = nextPreviewInformation["components"]
      for component in components:
        newFrame = Image.alpha_composite(frame,component.previewRender(self))
        frame = Image.alpha_composite(frame,newFrame)

      self._image = ImageQt(frame)
      self.imageCreated.emit(QtGui.QImage(self._image))
      
    except Empty:
      True
