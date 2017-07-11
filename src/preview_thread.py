'''
    Thread that runs to create QImages for MainWindow's preview label.
    Processes a queue of component lists.
'''
from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PIL import Image
from PIL.ImageQt import ImageQt
import core
from queue import Queue, Empty
import os

from frame import FloodFrame


class Worker(QtCore.QObject):

    imageCreated = pyqtSignal(['QImage'])
    error = pyqtSignal()

    def __init__(self, parent=None, queue=None):
        QtCore.QObject.__init__(self)
        parent.newTask.connect(self.createPreviewImage)
        parent.processTask.connect(self.process)
        self.parent = parent
        self.core = self.parent.core
        self.queue = queue
        self.width = int(self.core.settings.value('outputWidth'))
        self.height = int(self.core.settings.value('outputHeight'))

        # create checkerboard background to represent transparency
        self.background = FloodFrame(1920, 1080, (0, 0, 0, 0))
        self.background.paste(Image.open(os.path.join(
            self.core.wd, "background.png")))

    @pyqtSlot(list)
    def createPreviewImage(self, components):
        dic = {
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

            if self.background.width != self.width:
                self.background = self.background.resize(
                    (self.width, self.height))
            frame = self.background.copy()

            components = nextPreviewInformation["components"]
            for component in reversed(components):
                try:
                    frame = Image.alpha_composite(
                        frame, component.previewRender(self)
                    )

                except ValueError as e:
                    errMsg = "Bad frame returned by %s's preview renderer. " \
                        "%s. This is a fatal error." % (
                            str(component), str(e).capitalize()
                        )
                    print(errMsg)
                    self.parent.showMessage(
                        msg=errMsg,
                        detail=str(e),
                        icon='Warning',
                        parent=None  # MainWindow is in a different thread
                    )
                    self.error.emit()
                    break
            else:
                self.imageCreated.emit(QtGui.QImage(ImageQt(frame)))

        except Empty:
            True
