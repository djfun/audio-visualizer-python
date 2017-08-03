from PIL import Image, ImageDraw
from PyQt5.QtGui import QColor, QFont
from PyQt5 import QtGui, QtCore, QtWidgets
import os

from component import Component
from toolkit.frame import FramePainter


class Component(Component):
    name = 'Title Text'
    version = '1.0.0'

    def __init__(self, *args):
        super().__init__(*args)
        self.titleFont = QFont()

    def widget(self, *args):
        super().widget(*args)
        self.textColor = (255, 255, 255)
        self.title = 'Text'
        self.alignment = 1
        self.fontSize = self.height / 13.5

        self.page.comboBox_textAlign.addItem("Left")
        self.page.comboBox_textAlign.addItem("Middle")
        self.page.comboBox_textAlign.addItem("Right")

        self.page.lineEdit_textColor.setText('%s,%s,%s' % self.textColor)
        self.page.lineEdit_title.setText(self.title)
        self.page.comboBox_textAlign.setCurrentIndex(int(self.alignment))
        self.page.spinBox_fontSize.setValue(int(self.fontSize))

        fm = QtGui.QFontMetrics(self.titleFont)
        self.page.spinBox_xTextAlign.setValue(
            self.width / 2 - fm.width(self.title)/2)
        self.page.spinBox_yTextAlign.setValue(self.height / 2 * 1.036)

        self.page.fontComboBox_titleFont.currentFontChanged.connect(
            self.update
        )
        self.trackWidgets({
            'textColor': self.page.lineEdit_textColor,
            'title': self.page.lineEdit_title,
            'alignment': self.page.comboBox_textAlign,
            'fontSize': self.page.spinBox_fontSize,
            'xPosition': self.page.spinBox_xTextAlign,
            'yPosition': self.page.spinBox_yTextAlign,
        }, colorWidgets={
            'textColor': self.page.pushButton_textColor,
        }, relativeWidgets={
            'xPosition': 'x',
            'yPosition': 'y',
            'fontSize': 'y',
        })

    def update(self):
        self.titleFont = self.page.fontComboBox_titleFont.currentFont()
        super().update()

    def getXY(self):
        '''Returns true x, y after considering alignment settings'''
        fm = QtGui.QFontMetrics(self.titleFont)
        if self.alignment == 0:             # Left
            x = int(self.xPosition)

        if self.alignment == 1:             # Middle
            offset = int(fm.width(self.title)/2)
            x = self.xPosition - offset

        if self.alignment == 2:             # Right
            offset = fm.width(self.title)
            x = self.xPosition - offset
        return x, self.yPosition

    def loadPreset(self, pr, *args):
        super().loadPreset(pr, *args)

        font = QFont()
        font.fromString(pr['titleFont'])
        self.page.fontComboBox_titleFont.setCurrentFont(font)

    def savePreset(self):
        saveValueStore = super().savePreset()
        saveValueStore['titleFont'] = self.titleFont.toString()
        return saveValueStore

    def previewRender(self):
        return self.addText(self.width, self.height)

    def properties(self):
        props = ['static']
        if not self.title:
            props.append('error')
        return props

    def error(self):
        return "No text provided."

    def frameRender(self, frameNo):
        return self.addText(self.width, self.height)

    def addText(self, width, height):
        image = FramePainter(width, height)
        self.titleFont.setPixelSize(self.fontSize)
        image.setFont(self.titleFont)
        image.setPen(self.textColor)
        x, y = self.getXY()
        image.drawText(x, y, self.title)

        return image.finalize()

    def commandHelp(self):
        print('Enter a string to use as centred white text:')
        print('    "title=User Error"')
        print('Specify a text color:\n    color=255,255,255')
        print('Set custom x, y position:\n    x=500 y=500')

    def command(self, arg):
        if '=' in arg:
            key, arg = arg.split('=', 1)
            if key == 'color':
                self.page.lineEdit_textColor.setText(arg)
                return
            elif key == 'size':
                self.page.spinBox_fontSize.setValue(int(arg))
                return
            elif key == 'x':
                self.page.spinBox_xTextAlign.setValue(int(arg))
                return
            elif key == 'y':
                self.page.spinBox_yTextAlign.setValue(int(arg))
                return
            elif key == 'title':
                self.page.lineEdit_title.setText(arg)
                return
        super().command(arg)
