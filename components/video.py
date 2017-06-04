from PIL import Image, ImageDraw
from PyQt4 import uic, QtGui, QtCore
import os, subprocess
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
        self.width = int(previewWorker.core.settings.value('outputWidth'))
        self.height = int(previewWorker.core.settings.value('outputHeight'))
        frames = self.getVideoFrames(True)
        if frames:
            im = Image.open(frames[0])
            im = self.resize(im)
            return im
        else:
            return Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
    
    def preFrameRender(self, **kwargs):
        super().__init__(**kwargs)
        self.width = int(self.worker.core.settings.value('outputWidth'))
        self.height = int(self.worker.core.settings.value('outputHeight'))
        self.frames = self.getVideoFrames()
        
    def frameRender(self, moduleNo, frameNo):
        i = frameNo if frameNo < len(self.frames)-1 else len(self.frames)-1
        im = Image.open(self.frames[i])
        im = self.resize(im)
        return im

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
            
    def getVideoFrames(self, firstOnly=False):
        # recreate the temporary directory so it is empty
        # FIXME: don't dump too many frames at once
        if not self.videoPath:
            return
        self.parent.core.deleteTempDir()
        os.mkdir(self.parent.core.tempDir)
        if firstOnly:
         filename = 'preview%s.jpg' % os.path.basename(self.videoPath).split('.', 1)[0]
         options = '-ss 10 -vframes 1'
        else:
         filename = '$frame%05d.jpg'
         options = ''
        subprocess.call( \
         '%s -i "%s" -y %s "%s"' % ( \
            self.parent.core.FFMPEG_BIN,
            self.videoPath,
            options,
            os.path.join(self.parent.core.tempDir, filename)
         ),
         shell=True
        )
        return sorted([os.path.join(self.parent.core.tempDir, f) for f in os.listdir(self.parent.core.tempDir)])

    def resize(self, im):
        if im.size != (self.width, self.height):
            im = im.resize((self.width, self.height), Image.ANTIALIAS)
        return im
