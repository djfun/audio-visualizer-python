import numpy
from PIL import Image, ImageDraw
from PyQt4 import uic, QtGui
from PyQt4.QtGui import QColor
import os, random
from . import __base__


class Component(__base__.Component):
    '''Original Audio Visualization'''
    def widget(self, parent):
        self.parent = parent
        self.visColor = (255,255,255)

        page = uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'original.ui'))
        page.comboBox_visLayout.addItem("Classic")
        page.comboBox_visLayout.addItem("Split")
        page.comboBox_visLayout.addItem("Bottom")
        #visLayoutValue = int(self.settings.value('visLayout'))
        page.comboBox_visLayout.setCurrentIndex(0)
        page.comboBox_visLayout.currentIndexChanged.connect(self.update)
        page.lineEdit_visColor.setText('%s,%s,%s' % self.visColor)
        page.pushButton_visColor.clicked.connect(lambda: self.pickColor())
        btnStyle = "QPushButton { background-color : %s; outline: none; }" % QColor(*self.visColor).name()
        page.pushButton_visColor.setStyleSheet(btnStyle)
        page.lineEdit_visColor.textChanged.connect(self.update)
        self.page = page
        return page
    
    def update(self):
        self.layout = self.page.comboBox_visLayout.currentIndex()
        self.visColor = self.RGBFromString(self.page.lineEdit_visColor.text())
        self.parent.drawPreview()

    def previewRender(self, previewWorker):
        spectrum = numpy.fromfunction(lambda x: 0.008*(x-128)**2, (255,), dtype="int16")
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        return drawBars(width, height, spectrum, self.visColor, self.layout)
    
    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        self.smoothConstantDown = 0.08
        self.smoothConstantUp = 0.8
        self.lastSpectrum = None
    
    def frameRender(self, moduleNo, frameNo):
        self.lastSpectrum = transformData(frameNo, self.completeAudioArray, self.sampleSize,
                    self.smoothConstantDown, self.smoothConstantUp, self.lastSpectrum)
        width = int(self.worker.core.settings.value('outputWidth'))
        height = int(self.worker.core.settings.value('outputHeight'))
        return drawBars(width, height, self.lastSpectrum, self.visColor, self.layout)

    def pickColor(self):
        RGBstring, btnStyle = super().pickColor()
        self.page.lineEdit_visColor.setText(RGBstring)
        self.page.pushButton_visColor.setStyleSheet(btnStyle)

def transformData(i, completeAudioArray, sampleSize, smoothConstantDown, smoothConstantUp, lastSpectrum):
    if len(completeAudioArray) < (i + sampleSize):
      sampleSize = len(completeAudioArray) - i
    numpy.seterr(divide='ignore')
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
    
def drawBars(width, height, spectrum, color, layout):
    vH = height-height/8
    bF = width / 64
    bH = bF / 2
    bQ = bF / 4
    imTop = Image.new("RGBA", (width, height),(0,0,0,0))
    draw = ImageDraw.Draw(imTop)
    r, g, b = color
    color2 = (r, g, b, 125)

    bP = height / 1200

    for j in range(0, 63):
      draw.rectangle((bH + j * bF, vH+bQ, bH + j * bF + bF, vH + bQ - spectrum[j * 4] * bP - bH), fill=color2)
      draw.rectangle((bH + bQ + j * bF, vH , bH + bQ + j * bF + bH, vH - spectrum[j * 4] * bP), fill=color)


    imBottom = imTop.transpose(Image.FLIP_TOP_BOTTOM)

    im = Image.new("RGBA", (width, height),(0,0,0,0))

    if layout == 0:
      y = 0 - int(height/100*43)
      im.paste(imTop, (0, y), mask=imTop)
      y = 0 + int(height/100*43)
      im.paste(imBottom, (0, y), mask=imBottom)

    if layout == 1:
      y = 0 + int(height/100*10)
      im.paste(imTop, (0, y), mask=imTop)
      y = 0 - int(height/100*10)
      im.paste(imBottom, (0, y), mask=imBottom)

    if layout == 2:
      y = 0 + int(height/100*10)
      im.paste(imTop, (0, y), mask=imTop)

    return im
