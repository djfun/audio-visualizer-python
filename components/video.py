from PIL import Image, ImageDraw
from PyQt4 import uic, QtGui, QtCore
import os, subprocess
import numpy
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
        frame1 = self.getPreviewFrame()
        if not hasattr(self, 'staticFrame') or not self.working and frame1:
            frame = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            if frame1:
                im = Image.open(frame1)
                self.realSize = im.size
                im = self.resize(im)
                frame.paste(im)
            if not self.working:
                self.staticFrame = frame
        return self.staticFrame
    
    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        self.width = int(self.worker.core.settings.value('outputWidth'))
        self.height = int(self.worker.core.settings.value('outputHeight'))
        self.working = True
        self.frames = self.getVideoFrames()
        
    def frameRender(self, moduleNo, arrayNo, frameNo):
        # don't make a new frame
        if not self.working:
            return self.staticFrame
        byteFrame = self.frames.stdout.read(self.chunkSize)
        if len(byteFrame) == 0:
            self.working = False
            self.frames.kill()
            return self.staticFrame
            
        # make a new frame
        width, height = self.realSize
        image = numpy.fromstring(byteFrame, dtype='uint8')
        image = image.reshape((width, height, 4))
        image = Image.frombytes('RGBA', (width, height), image, 'raw', 'RGBa')
        image = self.resize(image)
        self.staticFrame = image
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
    
    def getPreviewFrame(self):
        if not self.videoPath:
            return
        name = os.path.basename(self.videoPath).split('.', 1)[0]
        filename = 'preview%s.jpg' % name
        if os.path.exists(os.path.join(self.parent.core.tempDir, filename)):
            # no, we don't need a new preview frame
            return False
        
        # get a preview frame
        subprocess.call( \
         '%s -i "%s" -y %s "%s"' % ( \
            self.parent.core.FFMPEG_BIN,
            self.videoPath,
            '-ss 10 -vframes 1',
            os.path.join(self.parent.core.tempDir, filename)
         ),
         shell=True
        )
        print('### Got Preview Frame From %s ###' % name)
        return os.path.join(self.parent.core.tempDir, filename)
    
    def getVideoFrames(self):
        if not self.videoPath:
            return
        
        command = [
            self.parent.core.FFMPEG_BIN,
            '-i', self.videoPath,
            '-f', 'image2pipe',
            '-pix_fmt', 'rgba',
            '-vcodec', 'rawvideo', '-',
        ]
        
        # pipe in video frames from ffmpeg
        in_pipe = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
        width, height = self.realSize
        self.chunkSize = 4*width*height

        return in_pipe

    def resize(self, im):
        if im.size != (self.width, self.height):
            im = im.resize((self.width, self.height), Image.ANTIALIAS)
        return im
