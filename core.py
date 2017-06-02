import sys, io, os
from PyQt4 import QtCore, QtGui, uic
from os.path import expanduser
import subprocess as sp
import numpy
from PIL import Image
import tempfile
from shutil import rmtree
import atexit
import time

class Core():

  def __init__(self):
    self.lastBackgroundImage = ""
    self._image = None

    self.FFMPEG_BIN = self.findFfmpeg()
    self.tempDir = None
    atexit.register(self.deleteTempDir)

  def findFfmpeg(self):
    if sys.platform == "win32":
      return "ffmpeg.exe"
    else:
      try:
        with open(os.devnull, "w") as f:
          sp.check_call(['ffmpeg', '-version'], stdout=f, stderr=f)
        return "ffmpeg"
      except:
        return "avconv"

  def parseBaseImage(self, backgroundImage, preview=False):
      ''' determines if the base image is a single frame or list of frames '''
      if backgroundImage == "":
         return ['']
      else:
         _, bgExt = os.path.splitext(backgroundImage)
         if not bgExt == '.mp4':
            return [backgroundImage]
         else:
            return self.getVideoFrames(backgroundImage, preview)

  def drawBaseImage(self, backgroundFile):
    if backgroundFile == '':
       im = Image.new("RGB", (int(self.settings.value('outputWidth')), int(self.settings.value('outputHeight'))), "black")
    else:
       im = Image.open(backgroundFile)

    if self._image == None or not self.lastBackgroundImage == backgroundFile:
      self.lastBackgroundImage = backgroundFile
      # resize if necessary
      if not im.size == (int(self.settings.value('outputWidth')), int(self.settings.value('outputHeight'))):
        im = im.resize((int(self.settings.value('outputWidth')), int(self.settings.value('outputHeight'))), Image.ANTIALIAS)
        
    return im

  def readAudioFile(self, filename):
    command = [ self.FFMPEG_BIN,
          '-i', filename,
          '-f', 's16le',
          '-acodec', 'pcm_s16le',
          '-ar', '44100', # ouput will have 44100 Hz
          '-ac', '1', # mono (set to '2' for stereo)
          '-']
    in_pipe = sp.Popen(command, stdout=sp.PIPE, stderr=sp.DEVNULL, bufsize=10**8)
    
    completeAudioArray = numpy.empty(0, dtype="int16")

    while True:
      if self.canceled:
        break
      # read 2 seconds of audio
      raw_audio = in_pipe.stdout.read(88200*4)
      if len(raw_audio) == 0:
        break
      audio_array = numpy.fromstring(raw_audio, dtype="int16")
      completeAudioArray = numpy.append(completeAudioArray, audio_array)
      # print(audio_array)

    in_pipe.kill()
    in_pipe.wait()

    # add 0s the end
    completeAudioArrayCopy = numpy.zeros(len(completeAudioArray) + 44100, dtype="int16")
    completeAudioArrayCopy[:len(completeAudioArray)] = completeAudioArray
    completeAudioArray = completeAudioArrayCopy

    return completeAudioArray

  def deleteTempDir(self):
     if self.tempDir and os.path.exists(self.tempDir):
         rmtree(self.tempDir)

  def getVideoFrames(self, videoPath, firstOnly=False):
      self.tempDir = os.path.join(tempfile.gettempdir(), 'audio-visualizer-python-data')
      # recreate the temporary directory so it is empty
      self.deleteTempDir()
      os.mkdir(self.tempDir)
      if firstOnly:
         filename = 'preview%s.jpg' % os.path.basename(videoPath).split('.', 1)[0]
         options = '-ss 10 -vframes 1'
      else:
         filename = '$frame%05d.jpg'
         options = ''
      sp.call( \
         '%s -i "%s" -y %s "%s"' % ( \
            self.FFMPEG_BIN,
            videoPath,
            options,
            os.path.join(self.tempDir, filename)
         ),
         shell=True
      )
      return sorted([os.path.join(self.tempDir, f) for f in os.listdir(self.tempDir)])

  def cancel(self):
    self.canceled = True

  def reset(self):
    self.canceled = False
