import numpy
from PIL import Image, ImageDraw
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QColor
import os
import time
from copy import copy

from component import Component
from toolkit.frame import BlankFrame
from toolkit import rgbFromString, pickColor


class Component(Component):
    name = 'Classic Visualizer'
    version = '1.0.0'

    def names():
        return ['Original Audio Visualization']

    def widget(self, parent):
        self.parent = parent
        self.settings = parent.settings
        self.visColor = (255, 255, 255)
        self.scale = 20
        self.y = 0
        self.canceled = False

        page = self.loadUi('original.ui')
        page.comboBox_visLayout.addItem("Classic")
        page.comboBox_visLayout.addItem("Split")
        page.comboBox_visLayout.addItem("Bottom")
        page.comboBox_visLayout.addItem("Top")
        page.comboBox_visLayout.setCurrentIndex(0)
        page.comboBox_visLayout.currentIndexChanged.connect(self.update)
        page.lineEdit_visColor.setText('%s,%s,%s' % self.visColor)
        page.pushButton_visColor.clicked.connect(lambda: self.pickColor())
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*self.visColor).name()
        page.pushButton_visColor.setStyleSheet(btnStyle)
        page.lineEdit_visColor.textChanged.connect(self.update)
        page.spinBox_scale.valueChanged.connect(self.update)
        page.spinBox_y.valueChanged.connect(self.update)

        self.page = page
        return page

    def update(self):
        self.layout = self.page.comboBox_visLayout.currentIndex()
        self.visColor = rgbFromString(self.page.lineEdit_visColor.text())
        self.scale = self.page.spinBox_scale.value()
        self.y = self.page.spinBox_y.value()

        super().update()

    def loadPreset(self, pr, presetName=None):
        super().loadPreset(pr, presetName)

        self.page.lineEdit_visColor.setText('%s,%s,%s' % pr['visColor'])
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*pr['visColor']).name()
        self.page.pushButton_visColor.setStyleSheet(btnStyle)
        self.page.comboBox_visLayout.setCurrentIndex(pr['layout'])
        self.page.spinBox_scale.setValue(pr['scale'])
        self.page.spinBox_y.setValue(pr['y'])

    def savePreset(self):
        return {
            'layout': self.layout,
            'visColor': self.visColor,
            'scale': self.scale,
            'y': self.y,
        }

    def previewRender(self, previewWorker):
        spectrum = numpy.fromfunction(
            lambda x: float(self.scale)/2500*(x-128)**2, (255,), dtype="int16")
        width = int(self.settings.value('outputWidth'))
        height = int(self.settings.value('outputHeight'))
        return self.drawBars(
            width, height, spectrum, self.visColor, self.layout
        )

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        self.smoothConstantDown = 0.08
        self.smoothConstantUp = 0.8
        self.lastSpectrum = None
        self.spectrumArray = {}
        self.width = int(self.settings.value('outputWidth'))
        self.height = int(self.settings.value('outputHeight'))

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

    def frameRender(self, layerNo, frameNo):
        arrayNo = frameNo * self.sampleSize
        return self.drawBars(
            self.width, self.height,
            self.spectrumArray[arrayNo],
            self.visColor, self.layout)

    def pickColor(self):
        RGBstring, btnStyle = pickColor()
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

        y = self.scale * numpy.log10(y)
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
        imTop = BlankFrame(width, height)
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

        im = BlankFrame(width, height)

        if layout == 0:  # Classic
            y = self.y - int(height/100*43)
            im.paste(imTop, (0, y), mask=imTop)
            y = self.y + int(height/100*43)
            im.paste(imBottom, (0, y), mask=imBottom)

        if layout == 1:  # Split
            y = self.y + int(height/100*10)
            im.paste(imTop, (0, y), mask=imTop)
            y = self.y - int(height/100*10)
            im.paste(imBottom, (0, y), mask=imBottom)

        if layout == 2:  # Bottom
            y = self.y + int(height/100*10)
            im.paste(imTop, (0, y), mask=imTop)

        if layout == 3:  # Top
            y = self.y - int(height/100*10)
            im.paste(imBottom, (0, y), mask=imBottom)

        return im

    def command(self, arg):
        if not arg.startswith('preset=') and '=' in arg:
            key, arg = arg.split('=', 1)
            try:
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
                    elif arg == 'top':
                        self.page.comboBox_visLayout.setCurrentIndex(3)
                    return
                elif key == 'scale':
                    arg = int(arg)
                    self.page.spinBox_scale.setValue(arg)
                    return
                elif key == 'y':
                    arg = int(arg)
                    self.page.spinBox_y.setValue(arg)
                    return
            except ValueError:
                print('You must enter a number.')
                quit(1)
        super().command(arg)

    def commandHelp(self):
        print('Give a layout name:\n    layout=[classic/split/bottom/top]')
        print('Specify a color:\n    color=255,255,255')
        print('Visualizer scale (20 is default):\n    scale=number')
        print('Y position:\n    y=number')
