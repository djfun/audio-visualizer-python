"""
Thread that runs to create QImages for MainWindow's preview label.
Processes a queue of component lists.
"""

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PIL import Image
from PIL.ImageQt import ImageQt
from queue import Empty
import time
import logging

from ..toolkit.frame import Checkerboard
from ..toolkit import disableWhenOpeningProject


log = logging.getLogger("AVP.Gui.PreviewThread")


class Worker(QtCore.QObject):

    imageCreated = pyqtSignal(QtGui.QImage)
    error = pyqtSignal(str)

    def __init__(self, core, settings, queue):
        super().__init__()
        self.core = core
        self.settings = settings
        self.queue = queue
        self.newBackground()

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
        for component in reversed(components):
            if "composite" not in component.properties():
                dic[component.compPos] = component.previewRender()
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
            timeElapsed = time.time()
            frame = self.background.copy()
            components = nextPreviewInformation["components"]
            for component in reversed(components):
                if component.width != frame.width or component.height != frame.height:
                    self.newBackground()
                    break

                try:
                    isCompositeComponent = "composite" in component.properties()
                    if isCompositeComponent:
                        newFrame = component.previewRender(frame)
                    elif (
                        component.compPos in nextPreviewInformation
                        and nextPreviewInformation[component.compPos].width
                        == frame.width
                    ):
                        newFrame = nextPreviewInformation[component.compPos]
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
            else:
                # We must store a reference to this QImage
                # or else Qt will garbage-collect it on the C++ side
                self.frame = ImageQt(frame)
                timeElapsed = time.time() - timeElapsed
                log.info("Generated preview frame in {0:.3f}s".format(timeElapsed))
                self.imageCreated.emit(QtGui.QImage(self.frame))

        except Empty:
            True
