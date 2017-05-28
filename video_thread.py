from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSignal, pyqtSlot
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageQt import ImageQt
import core
import numpy
import subprocess as sp
import sys

class Worker(QtCore.QObject):

  videoCreated = pyqtSignal()
  progressBarUpdate = pyqtSignal(int)
  progressBarSetText = pyqtSignal(str)

  def __init__(self, parent=None):
    QtCore.QObject.__init__(self)
    self.core = core.Core()
    self.core.settings = parent.settings
    self.modules = parent.modules
    self.stackedWidget = parent.window.stackedWidget
    parent.videoTask.connect(self.createVideo)

  @pyqtSlot(str, str, str, list)
  def createVideo(self, backgroundImage, inputFile, outputFile, components):
    # print('worker thread id: {}'.format(QtCore.QThread.currentThreadId()))
    def getBackgroundAtIndex(i):
        return self.core.drawBaseImage(backgroundFrames[i])

    progressBarValue = 0
    self.progressBarUpdate.emit(progressBarValue)
    self.progressBarSetText.emit('Loading background image…')

    backgroundFrames = self.core.parseBaseImage(backgroundImage)
    if len(backgroundFrames) < 2:
        # the base image is not a video so we can draw it now
        imBackground = getBackgroundAtIndex(0)
    else:
        # base images will be drawn while drawing the audio bars
        imBackground = None
        
    self.progressBarSetText.emit('Loading audio file…')
    completeAudioArray = self.core.readAudioFile(inputFile)

    # test if user has libfdk_aac
    encoders = sp.check_output(self.core.FFMPEG_BIN + " -encoders -hide_banner", shell=True)
    acodec = self.core.settings.value('outputAudioCodec')

    if b'libfdk_aac' in encoders and acodec == 'aac':
      acodec = 'libfdk_aac'

    ffmpegCommand = [ self.core.FFMPEG_BIN,
       '-y', # (optional) means overwrite the output file if it already exists.
       '-f', 'rawvideo',
       '-vcodec', 'rawvideo',
       '-s', self.core.settings.value('outputWidth')+'x'+self.core.settings.value('outputHeight'), # size of one frame
       '-pix_fmt', 'rgb24',
       '-r', self.core.settings.value('outputFrameRate'), # frames per second
       '-i', '-', # The input comes from a pipe
       '-an',
       '-i', inputFile,
       '-acodec', acodec, # output audio codec
       '-b:a', self.core.settings.value('outputAudioBitrate'),
       '-vcodec', self.core.settings.value('outputVideoCodec'),
       '-pix_fmt', self.core.settings.value('outputVideoFormat'),
       '-preset', self.core.settings.value('outputPreset'),
       '-f', self.core.settings.value('outputFormat')]

    if acodec == 'aac':
      ffmpegCommand.append('-strict')
      ffmpegCommand.append('-2')

    ffmpegCommand.append(outputFile)
    
    out_pipe = sp.Popen(ffmpegCommand,
        stdin=sp.PIPE,stdout=sys.stdout, stderr=sys.stdout)

    # initialize components
    componentWidgets = [self.stackedWidget.widget(i) for i in range(self.stackedWidget.count())]

    print('######################## Data')
    print(components)
    print(componentWidgets)
    sampleSize = 1470
    for component, widget in zip(components, componentWidgets):
        component.preFrameRender(worker=self, widget=widget, completeAudioArray=completeAudioArray, sampleSize=sampleSize)

    numpy.seterr(divide='ignore')
    frame = getBackgroundAtIndex(0)
    bgI = 0
    # create video for output
    for i in range(0, len(completeAudioArray), sampleSize):
        newFrame = Image.new("RGBA", (int(self.core.settings.value('outputWidth')), int(self.core.settings.value('outputHeight'))),(0,0,0,255))

        if imBackground:
            newFrame.paste(imBackground)
        else:
            newFrame.paste(getBackgroundAtIndex(bgI))

        for compNo, comp in enumerate(components):
            newFrame = Image.alpha_composite(newFrame,comp.frameRender(compNo, i))

        if not imBackground:
            if bgI < len(backgroundFrames)-1:
                bgI += 1
      # write to out_pipe
        try:
            frame = Image.new("RGB", (int(self.core.settings.value('outputWidth')), int(self.core.settings.value('outputHeight'))),(0,0,0))
            frame.paste(newFrame)
            out_pipe.stdin.write(frame.tobytes())
        finally:
            True

        # increase progress bar value
        if progressBarValue + 1 <= (i / len(completeAudioArray)) * 100:
            progressBarValue = numpy.floor((i / len(completeAudioArray)) * 100)
            self.progressBarUpdate.emit(progressBarValue)
            self.progressBarSetText.emit('%s%%' % str(int(progressBarValue)))

    numpy.seterr(all='print')

    out_pipe.stdin.close()
    if out_pipe.stderr is not None:
      print(out_pipe.stderr.read())
      out_pipe.stderr.close()
    # out_pipe.terminate() # don't terminate ffmpeg too early
    out_pipe.wait()
    print("Video file created")
    self.core.deleteTempDir()
    self.progressBarUpdate.emit(100)
    self.progressBarSetText.emit('100%')
    self.videoCreated.emit()
