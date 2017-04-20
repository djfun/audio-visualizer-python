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

  def __init__(self, parent=None):
    QtCore.QObject.__init__(self)
    parent.videoTask.connect(self.createVideo)
    self.core = core.Core()


  @pyqtSlot(str, str, QtGui.QFont, int, int, int, int, str, str)
  def createVideo(self, backgroundImage, titleText, titleFont, fontSize, alignment, xOffset, yOffset,  inputFile, outputFile):
    # print('worker thread id: {}'.format(QtCore.QThread.currentThreadId()))
    
    imBackground = self.core.drawBaseImage(
      backgroundImage,
      titleText,
      titleFont,
      fontSize,
      alignment,
      xOffset,
      yOffset)

    self.progressBarUpdate.emit(0)
    
    completeAudioArray = self.core.readAudioFile(inputFile)

    # test if user has libfdk_aac
    encoders = sp.check_output(self.core.FFMPEG_BIN + " -encoders -hide_banner", shell=True)
    if b'libfdk_aac' in encoders:
      acodec = 'libfdk_aac'
    else:
      acodec = 'aac'

    ffmpegCommand = [ self.core.FFMPEG_BIN,
       '-y', # (optional) means overwrite the output file if it already exists.
       '-f', 'rawvideo',
       '-vcodec', 'rawvideo',
       '-s', '1280x720', # size of one frame
       '-pix_fmt', 'rgb24',
       '-r', '30', # frames per second
       '-i', '-', # The input comes from a pipe
       '-an',
       '-i', inputFile,
       '-acodec', acodec, # output audio codec
       '-b:a', "192k",
       '-vcodec', "libx264",
       '-pix_fmt', "yuv420p",
       '-preset', "medium",
       '-f', "mp4"]

    if acodec == 'aac':
      ffmpegCommand.append('-strict')
      ffmpegCommand.append('-2')

    ffmpegCommand.append(outputFile)
    
    out_pipe = sp.Popen(ffmpegCommand,
        stdin=sp.PIPE,stdout=sys.stdout, stderr=sys.stdout)

    smoothConstantDown = 0.08
    smoothConstantUp = 0.8
    lastSpectrum = None
    progressBarValue = 0
    sampleSize = 1470

    numpy.seterr(divide='ignore')

    for i in range(0, len(completeAudioArray), sampleSize):
      # create video for output
      lastSpectrum = self.core.transformData(
        i,
        completeAudioArray,
        sampleSize,
        smoothConstantDown,
        smoothConstantUp,
        lastSpectrum)
      im = self.core.drawBars(lastSpectrum, imBackground)

      # write to out_pipe
      try:
        out_pipe.stdin.write(im.tobytes())
      finally:
        True

      # increase progress bar value
      if progressBarValue + 1 <= (i / len(completeAudioArray)) * 100:
        progressBarValue = numpy.floor((i / len(completeAudioArray)) * 100)
        self.progressBarUpdate.emit(progressBarValue)

    numpy.seterr(all='print')

    out_pipe.stdin.close()
    if out_pipe.stderr is not None:
      print(out_pipe.stderr.read())
      out_pipe.stderr.close()
    # out_pipe.terminate() # don't terminate ffmpeg too early
    out_pipe.wait()
    print("Video file created")
    self.progressBarUpdate.emit(100)
    self.videoCreated.emit()
