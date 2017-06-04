from PIL import Image, ImageDraw
from PyQt4 import uic, QtGui, QtCore
import os
from . import __base__

class Component(__base__.Component):
    '''Image'''
    def widget(self, parent):
        self.parent = parent
        self.settings = parent.settings
        page = uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'image.ui'))
        self.imagePath = ''
        self.x = 0
        self.y = 0
        
        page.lineEdit_image.textChanged.connect(self.update)
        page.pushButton_image.clicked.connect(self.pickImage)
        
        self.page = page
        return page

    def update(self):
        self.imagePath = self.page.lineEdit_image.text()
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
        if self.imagePath and os.path.exists(self.imagePath):
            image = Image.open(self.imagePath)
            if image.size != (width, height):
                image = image.resize((width, height), Image.ANTIALIAS)
            frame.paste(image)
        return frame

    def loadPreset(self, pr):
        self.page.lineEdit_image.setText(pr['image'])
        
    def savePreset(self):
        return {
            'image' : self.imagePath,
        }

    def cancel(self):
        self.canceled = True

    def reset(self):
        self.canceled = False
        
    def pickImage(self):
        imgDir = self.settings.value("backgroundDir", os.path.expanduser("~"))
        filename = QtGui.QFileDialog.getOpenFileName(self.page,
            "Choose Image", imgDir, "Image Files (*.jpg *.png)")
        if filename: 
            self.settings.setValue("backgroundDir", os.path.dirname(filename))
            self.page.lineEdit_image.setText(filename)
            self.update()
