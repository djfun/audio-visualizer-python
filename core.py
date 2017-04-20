import sys, io, os
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtGui import QPainter, QColor
from os.path import expanduser
import subprocess as sp
import numpy
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageQt import ImageQt

class Core():

  def __init__(self):
    self.lastBackgroundImage = ""
    self._image = None

    self.FFMPEG_BIN = self.findFfmpeg()

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

  def drawBaseImage(self, backgroundImage, titleText, titleFont, alignment, xOffset, yOffset):

    if self._image == None or not self.lastBackgroundImage == backgroundImage:
      self.lastBackgroundImage = backgroundImage

      if backgroundImage == "":
        im = Image.new("RGB", (1280, 720), "black")
      else:
        im = Image.open(backgroundImage)

      # resize if necessary
      if not im.size == (1280, 720):
        im = im.resize((1280, 720), Image.ANTIALIAS)

      self._image = ImageQt(im)
    
    self._image1 = QtGui.QImage(self._image)
    painter = QPainter(self._image1)
    font = titleFont
    font.setPointSizeF(35)
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255))

    yPosition = 375 + yOffset

    fm = QtGui.QFontMetrics(font)
    if alignment == "Left":
       xPosition = 70 + xOffset
    if alignment == "Middle":
       xPosition = xOffset + (1280/2 - fm.width(titleText)/2)
    if alignment == "Right":
       xPosition = xOffset + (1210 - fm.width(titleText))
    painter.drawText(xPosition, yPosition, titleText)
    painter.end()

    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.ReadWrite)
    self._image1.save(buffer, "PNG")

    strio = io.BytesIO()
    strio.write(buffer.data())
    buffer.close()
    strio.seek(0)
    return Image.open(strio)

  def drawBars(self, spectrum, image):

    imTop = Image.new("RGBA", (1280, 360))
    draw = ImageDraw.Draw(imTop)
    for j in range(0, 63):
      draw.rectangle((10 + j * 20, 325, 10 + j * 20 + 20, 325 - spectrum[j * 4] * 1 - 10), fill=(255, 255, 255, 50))
      draw.rectangle((15 + j * 20, 320, 15 + j * 20 + 10, 320 - spectrum[j * 4] * 1), fill="white")


    imBottom = imTop.transpose(Image.FLIP_TOP_BOTTOM)

    im = Image.new("RGB", (1280, 720), "black")

    im.paste(image, (0, 0))
    im.paste(imTop, (0, 0), mask=imTop)
    im.paste(imBottom, (0, 360), mask=imBottom)

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

  def transformData(self, i, completeAudioArray, sampleSize, smoothConstantDown, smoothConstantUp, lastSpectrum):
    if len(completeAudioArray) < (i + sampleSize):
      sampleSize = len(completeAudioArray) - i

    window = numpy.hanning(sampleSize)
    data = completeAudioArray[i:i+sampleSize][::1] * window
    paddedSampleSize = 2048
    paddedData = numpy.pad(data, (0, paddedSampleSize - sampleSize), 'constant')
    spectrum = numpy.fft.fft(paddedData)
    sample_rate = 44100
    frequencies = numpy.fft.fftfreq(len(spectrum), 1./sample_rate)

    y = abs(spectrum[0:int(paddedSampleSize/2) - 1])

    # filter the noise away
    # y[y<80] = 0

    y = 20 * numpy.log10(y)
    y[numpy.isinf(y)] = 0

    if lastSpectrum is not None:
      lastSpectrum[y < lastSpectrum] = y[y < lastSpectrum] * smoothConstantDown + lastSpectrum[y < lastSpectrum] * (1 - smoothConstantDown)
      lastSpectrum[y >= lastSpectrum] = y[y >= lastSpectrum] * smoothConstantUp + lastSpectrum[y >= lastSpectrum] * (1 - smoothConstantUp)
    else:
      lastSpectrum = y

    x = frequencies[0:int(paddedSampleSize/2) - 1]

    return lastSpectrum
