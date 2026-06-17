"""
Thread that runs to create QImages for MainWindow's preview label.
Processes a queue of component lists.
"""

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PIL import Image
from PIL.ImageQt import ImageQt
from queue import Queue, Empty
import time
import logging

from ..toolkit.frame import Checkerboard
from ..toolkit import disableWhenOpeningProject


log = logging.getLogger(__name__)


class Worker(QtCore.QObject):

    imageCreated = pyqtSignal(QtGui.QImage)
    error = pyqtSignal(str)

    def __init__(self, core, settings):
        super().__init__()
        self.core = core
        self.settings = settings
        self.queue = Queue()
        self.newBackground()
        self.frameNo = 0

    def newBackground(self):
        width = int(self.settings.value("outputWidth"))
        height = int(self.settings.value("outputHeight"))
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
        """Process one preview image from the queue"""
        try:
            nextPreviewInformation = self.queue.get(block=False)
            while self.queue.qsize() >= 2:
                try:
                    self.queue.get(block=False)
                except Empty:
                    continue
            timeElapsed = time.time()
            frame = self.background.copy()
            components = nextPreviewInformation["components"]
            for component in reversed(components):
                try:
                    lockAcquired = component.lockSize(frame.width, frame.height)
                    if not lockAcquired:
                        break
                    isCompositeComponent = "composite" in component.properties()
                    if isCompositeComponent:
                        newFrame = component.previewRender(frame)
                    else:
                        newFrame = component.previewRender()
                    if isCompositeComponent:
                        frame = newFrame
                    else:
                        frame = Image.alpha_composite(frame, newFrame)

                except (AttributeError, ValueError) as e:
                    errMsg = (
                        "Bad frame returned by %s's preview renderer. "
                        "%s. New frame %s."
                        % (
                            str(component),
                            str(e).capitalize(),
                            (
                                "is None"
                                if newFrame is None
                                else "size was %s*%s; should be %s*%s"
                                % (
                                    newFrame.width,
                                    newFrame.height,
                                    frame.width,
                                    frame.height,
                                )
                            ),
                        )
                    )
                    log.critical(errMsg)
                    self.error.emit(errMsg)
                    break
                except RuntimeError as e:
                    log.error(str(e))
                finally:
                    component.unlockSize()
            else:
                # We must store a reference to this QImage
                # or else Qt will garbage-collect it on the C++ side
                self.frame = ImageQt(frame)
                timeElapsed = time.time() - timeElapsed
                self.frameNo += 1
                log.info(
                    "Generated preview frame #{0} in {1:.3f}s using {2} components".format(
                        self.frameNo, timeElapsed, len(components)
                    )
                )
                self.imageCreated.emit(QtGui.QImage(self.frame))

        except Empty:
            True
