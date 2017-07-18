from PIL import Image, ImageDraw
from PyQt5.QtGui import QColor, QFont
from PyQt5 import QtGui, QtCore, QtWidgets
import os

from component import Component
from toolkit.frame import FramePainter
from toolkit import rgbFromString, pickColor


class Component(Component):
    '''Title Text'''

    modified = QtCore.pyqtSignal(int, dict)

    def __init__(self, *args):
        super().__init__(*args)
        self.titleFont = QFont()

    def widget(self, parent):
        self.parent = parent
        self.settings = self.parent.core.settings
        height = int(self.settings.value('outputHeight'))
        width = int(self.settings.value('outputWidth'))

        self.textColor = (255, 255, 255)
        self.title = 'Text'
        self.alignment = 1
        self.fontSize = height / 13.5
        fm = QtGui.QFontMetrics(self.titleFont)
        self.xPosition = width / 2 - fm.width(self.title)/2
        self.yPosition = height / 2 * 1.036

        page = self.loadUi('text.ui')
        page.comboBox_textAlign.addItem("Left")
        page.comboBox_textAlign.addItem("Middle")
        page.comboBox_textAlign.addItem("Right")

        page.lineEdit_textColor.setText('%s,%s,%s' % self.textColor)
        page.pushButton_textColor.clicked.connect(self.pickColor)
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*self.textColor).name()
        page.pushButton_textColor.setStyleSheet(btnStyle)

        page.lineEdit_title.setText(self.title)
        page.comboBox_textAlign.setCurrentIndex(int(self.alignment))
        page.spinBox_fontSize.setValue(int(self.fontSize))
        page.spinBox_xTextAlign.setValue(int(self.xPosition))
        page.spinBox_yTextAlign.setValue(int(self.yPosition))

        page.fontComboBox_titleFont.currentFontChanged.connect(self.update)
        page.lineEdit_title.textChanged.connect(self.update)
        page.comboBox_textAlign.currentIndexChanged.connect(self.update)
        page.spinBox_xTextAlign.valueChanged.connect(self.update)
        page.spinBox_yTextAlign.valueChanged.connect(self.update)
        page.spinBox_fontSize.valueChanged.connect(self.update)
        page.lineEdit_textColor.textChanged.connect(self.update)
        self.page = page
        return page

    def update(self):
        self.title = self.page.lineEdit_title.text()
        self.alignment = self.page.comboBox_textAlign.currentIndex()
        self.titleFont = self.page.fontComboBox_titleFont.currentFont()
        self.fontSize = self.page.spinBox_fontSize.value()
        self.xPosition = self.page.spinBox_xTextAlign.value()
        self.yPosition = self.page.spinBox_yTextAlign.value()
        self.textColor = rgbFromString(
            self.page.lineEdit_textColor.text())
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*self.textColor).name()
        self.page.pushButton_textColor.setStyleSheet(btnStyle)

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

    def loadPreset(self, pr, presetName=None):
        super().loadPreset(pr, presetName)

        self.page.lineEdit_title.setText(pr['title'])
        font = QFont()
        font.fromString(pr['titleFont'])
        self.page.fontComboBox_titleFont.setCurrentFont(font)
        self.page.spinBox_fontSize.setValue(pr['fontSize'])
        self.page.comboBox_textAlign.setCurrentIndex(pr['alignment'])
        self.page.spinBox_xTextAlign.setValue(pr['xPosition'])
        self.page.spinBox_yTextAlign.setValue(pr['yPosition'])
        self.page.lineEdit_textColor.setText('%s,%s,%s' % pr['textColor'])
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*pr['textColor']).name()
        self.page.pushButton_textColor.setStyleSheet(btnStyle)

    def savePreset(self):
        return {
            'preset': self.currentPreset,
            'title': self.title,
            'titleFont': self.titleFont.toString(),
            'alignment': self.alignment,
            'fontSize': self.fontSize,
            'xPosition': self.xPosition,
            'yPosition': self.yPosition,
            'textColor': self.textColor
        }

    def previewRender(self, previewWorker):
        width = int(self.settings.value('outputWidth'))
        height = int(self.settings.value('outputHeight'))
        return self.addText(width, height)

    def properties(self):
        props = ['static']
        if not self.title:
            props.append('error')
        return props

    def error(self):
        return "No text provided."

    def frameRender(self, layerNo, frameNo):
        width = int(self.settings.value('outputWidth'))
        height = int(self.settings.value('outputHeight'))
        return self.addText(width, height)

    def addText(self, width, height):

        image = FramePainter(width, height)
        self.titleFont.setPixelSize(self.fontSize)
        image.setFont(self.titleFont)
        image.setPen(self.textColor)
        x, y = self.getXY()
        image.drawText(x, y, self.title)

        return image.finalize()

    def pickColor(self):
        RGBstring, btnStyle = pickColor()
        if not RGBstring:
            return
        self.page.lineEdit_textColor.setText(RGBstring)
        self.page.pushButton_textColor.setStyleSheet(btnStyle)

    def commandHelp(self):
        print('Enter a string to use as centred white text:')
        print('    "title=User Error"')
        print('Specify a text color:\n    color=255,255,255')
        print('Set custom x, y position:\n    x=500 y=500')

    def command(self, arg):
        if not arg.startswith('preset=') and '=' in arg:
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
