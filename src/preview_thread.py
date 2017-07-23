'''
    Thread that runs to create QImages for MainWindow's preview label.
    Processes a queue of component lists.
'''
from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PIL import Image
from PIL.ImageQt import ImageQt
from queue import Queue, Empty
import os

from toolkit.frame import Checkerboard
from toolkit import disableWhenOpeningProject


class Worker(QtCore.QObject):

    imageCreated = pyqtSignal(QtGui.QImage)
    error = pyqtSignal(str)

    def __init__(self, parent=None, queue=None):
        QtCore.QObject.__init__(self)
        parent.newTask.connect(self.createPreviewImage)
        parent.processTask.connect(self.process)
        self.parent = parent
        self.core = parent.core
        self.settings = parent.settings
        self.queue = queue

        width = int(self.settings.value('outputWidth'))
        height = int(self.settings.value('outputHeight'))
        self.background = Checkerboard(width, height)

    @disableWhenOpeningProject
    @pyqtSlot(list)
    def createPreviewImage(self, components):
        dic = {
          "components": components,
        }
        self.queue.put(dic)

    @pyqtSlot()
    def process(self):
        width = int(self.settings.value('outputWidth'))
        height = int(self.settings.value('outputHeight'))
        try:
            nextPreviewInformation = self.queue.get(block=False)
            while self.queue.qsize() >= 2:
                try:
                    self.queue.get(block=False)
                except Empty:
                    continue
            if self.background.width != width \
                    or self.background.height != height:
                self.background = Checkerboard(width, height)

            frame = self.background.copy()

            components = nextPreviewInformation["components"]
            for component in reversed(components):
                try:
                    newFrame = component.previewRender(self)
                    frame = Image.alpha_composite(
                        frame, newFrame
                    )

                except ValueError as e:
                    errMsg = "Bad frame returned by %s's preview renderer. " \
                        "%s. New frame size was %s*%s; should be %s*%s." % (
                            str(component), str(e).capitalize(),
                            newFrame.width, newFrame.height,
                            width, height
                        )
                    self.error.emit(errMsg)
                    break
                except RuntimeError as e:
                    print(e)
            else:
                self.frame = ImageQt(frame)
                self.imageCreated.emit(QtGui.QImage(self.frame))

        except Empty:
            True
