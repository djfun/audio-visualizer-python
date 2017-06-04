from PIL import Image, ImageDraw
from PyQt4 import uic, QtGui, QtCore
import os, subprocess
from . import __base__

class Component(__base__.Component):
    '''Video'''
    def __init__(self):
        super().__init__()
        self.working = False
        
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
        if not hasattr(self, 'staticFrame') or not self.working and frames:
            frame = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            if frames:
                im = Image.open(frames[0])
                im = self.resize(im)
                frame.paste(im)
            if not self.working:
                self.staticFrame = frame
        return self.staticFrame
    
    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        self.width = int(self.worker.core.settings.value('outputWidth'))
        self.height = int(self.worker.core.settings.value('outputHeight'))
        self.frames = self.getVideoFrames()
        self.working = True
        
    def frameRender(self, moduleNo, arrayNo, frameNo):
        print(frameNo)
        try:
            if frameNo < len(self.frames)-1:
                self.staticFrame = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
                im = Image.open(self.frames[frameNo])
                im = self.resize(im)
                self.staticFrame.paste(im)
        except FileNotFoundError:
            print("Video component encountered an error")
            self.frames = []
        return self.staticFrame

    def loadPreset(self, pr):
        self.page.lineEdit_video.setText(pr['video'])
        
    def savePreset(self):
        return {
            'video' : self.videoPath,
        }
        
    def pickVideo(self):
        imgDir = self.settings.value("backgroundDir", os.path.expanduser("~"))
        filename = QtGui.QFileDialog.getOpenFileName(self.page,
            "Choose Video", imgDir, "Video Files (*.mp4)")
        if filename: 
            self.settings.setValue("backgroundDir", os.path.dirname(filename))
            self.page.lineEdit_video.setText(filename)
            self.update()
            
    def getVideoFrames(self, preview=False):
        # recreate the temporary directory so it is empty
        # FIXME: don't dump all the frames at once, don't dump more than sound length
        # FIXME: make cancellable, report status to user, etc etc etc
        if not self.videoPath:
            return
        name = os.path.basename(self.videoPath).split('.', 1)[0]
        if preview:
            filename = 'preview%s.jpg' % name
            if os.path.exists(os.path.join(self.parent.core.tempDir, filename)):
                return False
        else:
            filename = name+'-frame%05d.jpg'
         
        # recreate tempDir and dump needed frame(s)
        self.parent.core.deleteTempDir()
        os.mkdir(self.parent.core.tempDir)
        if preview:
            options = '-ss 10 -vframes 1'
        else:
            options = '' #'-vframes 99999'
        subprocess.call( \
         '%s -i "%s" -y %s "%s"' % ( \
            self.parent.core.FFMPEG_BIN,
            self.videoPath,
            options,
            os.path.join(self.parent.core.tempDir, filename)
         ),
         shell=True
        )
        print('### Got Preview Frame From %s ###' % name if preview else '### Finished Dumping Frames From %s ###' % name)
        return sorted([os.path.join(self.parent.core.tempDir, f) for f in os.listdir(self.parent.core.tempDir)])

    def resize(self, im):
        if im.size != (self.width, self.height):
            im = im.resize((self.width, self.height), Image.ANTIALIAS)
        return im
