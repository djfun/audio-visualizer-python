from PIL import Image, ImageDraw
from PyQt4 import uic, QtGui, QtCore
import os
from . import __base__

class Component(__base__.Component):
    '''Video'''
    def widget(self, parent):
        self.parent = parent
        page = uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'video.ui'))
        self.page = page
        return page

    def update(self):
        # read widget values
        self.parent.drawPreview()
        
    def previewRender(self, previewWorker):
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        return self.drawFrame(width, height)
        
    def frameRender(self, moduleNo, frameNo):
        width = int(self.worker.core.settings.value('outputWidth'))
        height = int(self.worker.core.settings.value('outputHeight'))
        return self.drawFrame(width, height)
        
    def drawFrame(self, width, height):
        return Image.new("RGBA", (width, height), (0,0,0,255))

    def loadPreset(self, presetDict):
        # update widgets using a preset dict
        pass
        
    def savePreset(self):
        return {}

    def cancel(self):
        self.canceled = True

    def reset(self):
        self.canceled = False
