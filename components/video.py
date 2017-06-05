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
        frame1 = self.getPreviewFrame()
        if not hasattr(self, 'staticFrame') or not self.working and frame1:
            frame = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            if frame1:
                im = Image.open(frame1)
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
        # FIXME: make cancellable, report status to user, etc etc etc
        if not self.videoPath:
            return
        
        command = [
            self.parent.core.FFMPEG_BIN,
            '-i', self.videoPath,
            '-f', 'image2pipe',
            '-vcodec', 'rawvideo', '-',
            '-pix_fmt', 'rgba',
        ]
        
        # pipe in video frames from ffmpeg
        in_pipe = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=8**10)
        # maybe bufsize=4*self.width*self.height+100 ?
        chunk = 4*self.width*self.height
        
        frames = []
        while True:
            byteFrame = in_pipe.stdout.read(chunk)
            if len(byteFrame) == 0:
                break
            img = Image.frombytes('RGBA', (self.width, self.height), byteFrame, 'raw', 'RGBa')
            frames.append(img)

        return frames

    def resize(self, im):
        if im.size != (self.width, self.height):
            im = im.resize((self.width, self.height), Image.ANTIALIAS)
        return im
