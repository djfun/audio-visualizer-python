import numpy
from PIL import Image, ImageDraw
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QColor
import os
from . import __base__
import time
from copy import copy


class Component(__base__.Component):
    '''Original Audio Visualization'''

    modified = QtCore.pyqtSignal(int, dict)

    def widget(self, parent):
        self.parent = parent
        self.visColor = (255, 255, 255)

        page = self.loadUi('original.ui')
        page.comboBox_visLayout.addItem("Classic")
        page.comboBox_visLayout.addItem("Split")
        page.comboBox_visLayout.addItem("Bottom")
        page.comboBox_visLayout.setCurrentIndex(0)
        page.comboBox_visLayout.currentIndexChanged.connect(self.update)
        page.lineEdit_visColor.setText('%s,%s,%s' % self.visColor)
        page.pushButton_visColor.clicked.connect(lambda: self.pickColor())
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*self.visColor).name()
        page.pushButton_visColor.setStyleSheet(btnStyle)
        page.lineEdit_visColor.textChanged.connect(self.update)
        self.page = page
        self.canceled = False
        return page

    def update(self):
        self.layout = self.page.comboBox_visLayout.currentIndex()
        self.visColor = self.RGBFromString(self.page.lineEdit_visColor.text())
        self.parent.drawPreview()
        super().update()

    def loadPreset(self, pr, presetName=None):
        super().loadPreset(pr, presetName)

        self.page.lineEdit_visColor.setText('%s,%s,%s' % pr['visColor'])
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*pr['visColor']).name()
        self.page.pushButton_visColor.setStyleSheet(btnStyle)
        self.page.comboBox_visLayout.setCurrentIndex(pr['layout'])

    def savePreset(self):
        return {
            'preset': self.currentPreset,
            'layout': self.layout,
            'visColor': self.visColor,
        }

    def previewRender(self, previewWorker):
        spectrum = numpy.fromfunction(
            lambda x: 0.008*(x-128)**2, (255,), dtype="int16")
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        return self.drawBars(
            width, height, spectrum, self.visColor, self.layout)

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        self.smoothConstantDown = 0.08
        self.smoothConstantUp = 0.8
        self.lastSpectrum = None
        self.spectrumArray = {}
        self.width = int(self.worker.core.settings.value('outputWidth'))
        self.height = int(self.worker.core.settings.value('outputHeight'))

        for i in range(0, len(self.completeAudioArray), self.sampleSize):
            if self.canceled:
                break
            self.lastSpectrum = self.transformData(
                i, self.completeAudioArray, self.sampleSize,
                self.smoothConstantDown, self.smoothConstantUp,
                self.lastSpectrum)
            self.spectrumArray[i] = copy(self.lastSpectrum)

            progress = int(100*(i/len(self.completeAudioArray)))
            if progress >= 100:
                progress = 100
            pStr = "Analyzing audio: "+str(progress)+'%'
            self.progressBarSetText.emit(pStr)
            self.progressBarUpdate.emit(int(progress))

    def frameRender(self, moduleNo, arrayNo, frameNo):
        return self.drawBars(
            self.width, self.height,
            self.spectrumArray[arrayNo],
            self.visColor, self.layout)

    def pickColor(self):
        RGBstring, btnStyle = super().pickColor()
        if not RGBstring:
            return
        self.page.lineEdit_visColor.setText(RGBstring)
        self.page.pushButton_visColor.setStyleSheet(btnStyle)

    def transformData(
      self, i, completeAudioArray, sampleSize,
      smoothConstantDown, smoothConstantUp, lastSpectrum):
        if len(completeAudioArray) < (i + sampleSize):
            sampleSize = len(completeAudioArray) - i

        window = numpy.hanning(sampleSize)
        data = completeAudioArray[i:i+sampleSize][::1] * window
        paddedSampleSize = 2048
        paddedData = numpy.pad(
            data, (0, paddedSampleSize - sampleSize), 'constant')
        spectrum = numpy.fft.fft(paddedData)
        sample_rate = 44100
        frequencies = numpy.fft.fftfreq(len(spectrum), 1./sample_rate)

        y = abs(spectrum[0:int(paddedSampleSize/2) - 1])

        # filter the noise away
        # y[y<80] = 0

        y = 20 * numpy.log10(y)
        y[numpy.isinf(y)] = 0

        if lastSpectrum is not None:
            lastSpectrum[y < lastSpectrum] = \
                y[y < lastSpectrum] * smoothConstantDown + \
                lastSpectrum[y < lastSpectrum] * (1 - smoothConstantDown)

            lastSpectrum[y >= lastSpectrum] = \
                y[y >= lastSpectrum] * smoothConstantUp + \
                lastSpectrum[y >= lastSpectrum] * (1 - smoothConstantUp)
        else:
            lastSpectrum = y

        x = frequencies[0:int(paddedSampleSize/2) - 1]

        return lastSpectrum

    def drawBars(self, width, height, spectrum, color, layout):
        vH = height-height/8
        bF = width / 64
        bH = bF / 2
        bQ = bF / 4
        imTop = self.blankFrame(width, height)
        draw = ImageDraw.Draw(imTop)
        r, g, b = color
        color2 = (r, g, b, 125)

        bP = height / 1200

        for j in range(0, 63):
            draw.rectangle((
                bH + j * bF, vH+bQ, bH + j * bF + bF, vH + bQ -
                spectrum[j * 4] * bP - bH), fill=color2)

            draw.rectangle((
                bH + bQ + j * bF, vH, bH + bQ + j * bF + bH, vH -
                spectrum[j * 4] * bP), fill=color)

        imBottom = imTop.transpose(Image.FLIP_TOP_BOTTOM)

        im = self.blankFrame(width, height)

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

    def command(self, arg):
        if not arg.startswith('preset=') and '=' in arg:
            key, arg = arg.split('=', 1)
            if key == 'color':
                self.page.lineEdit_visColor.setText(arg)
                return
            elif key == 'layout':
                if arg == 'classic':
                    self.page.comboBox_visLayout.setCurrentIndex(0)
                elif arg == 'split':
                    self.page.comboBox_visLayout.setCurrentIndex(1)
                elif arg == 'bottom':
                    self.page.comboBox_visLayout.setCurrentIndex(2)
                return
        super().command(arg)

    def commandHelp(self):
        print('Give a layout name:\n    layout=[classic/split/bottom]')
        print('Specify a color:\n    color=255,255,255')