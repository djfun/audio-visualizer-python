from PIL import Image, ImageDraw
from PyQt4 import uic, QtGui, QtCore
import os
from . import __base__

class Component(__base__.Component):
    '''Video'''
    def widget(self, parent):
        self.parent = parent
        self.settings = parent.settings
        page = uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'video.ui'))
        self.videoPath = ''
        self.x = 0
        self.y = 0
        
        page.lineEdit_video.textChanged.connect(self.update)
        page.pushButton_video.clicked.connect(self.pickVideo)
        
        self.page = page
        return page

    def update(self):
        self.videoPath = self.page.lineEdit_video.text()
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
        frame = Image.new("RGBA", (width, height), (0,0,0,0))
        '''
        if self.imagePath and os.path.exists(self.imagePath):
            image = Image.open(self.imagePath)
            if image.size != (width, height):
                image = image.resize((width, height), Image.ANTIALIAS)
            frame.paste(image)
        '''
        return frame

    def loadPreset(self, pr):
        self.page.lineEdit_video.setText(pr['video'])
        
    def savePreset(self):
        return {
            'video' : self.videoPath,
        }

    def cancel(self):
        self.canceled = True

    def reset(self):
        self.canceled = False
        
    def pickVideo(self):
        imgDir = self.settings.value("backgroundDir", os.path.expanduser("~"))
        filename = QtGui.QFileDialog.getOpenFileName(self.page,
            "Choose Video", imgDir, "Video Files (*.mp4)")
        if filename: 
            self.settings.setValue("backgroundDir", os.path.dirname(filename))
            self.page.lineEdit_video.setText(filename)
            self.update()
