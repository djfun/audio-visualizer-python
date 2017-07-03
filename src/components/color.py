from PIL import Image, ImageDraw
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QColor
from PIL.ImageQt import ImageQt
import os

from component import Component
from frame import BlankFrame, FloodFrame, FramePainter, PaintColor


class Component(Component):
    '''Color'''

    modified = QtCore.pyqtSignal(int, dict)

    def widget(self, parent):
        self.parent = parent
        page = self.loadUi('color.ui')

        self.color1 = (0, 0, 0)
        self.color2 = (133, 133, 133)
        self.x = 0
        self.y = 0

        page.lineEdit_color1.setText('%s,%s,%s' % self.color1)
        page.lineEdit_color2.setText('%s,%s,%s' % self.color2)

        btnStyle1 = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*self.color1).name()

        btnStyle2 = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*self.color2).name()

        page.pushButton_color1.setStyleSheet(btnStyle1)
        page.pushButton_color2.setStyleSheet(btnStyle2)
        page.pushButton_color1.clicked.connect(lambda: self.pickColor(1))
        page.pushButton_color2.clicked.connect(lambda: self.pickColor(2))

        # disable color #2 until non-default 'fill' option gets changed
        page.lineEdit_color2.setDisabled(True)
        page.pushButton_color2.setDisabled(True)
        page.spinBox_x.valueChanged.connect(self.update)
        page.spinBox_y.valueChanged.connect(self.update)
        page.spinBox_width.setValue(
            int(parent.settings.value("outputWidth")))
        page.spinBox_height.setValue(
            int(parent.settings.value("outputHeight")))

        page.lineEdit_color1.textChanged.connect(self.update)
        page.lineEdit_color2.textChanged.connect(self.update)
        page.spinBox_x.valueChanged.connect(self.update)
        page.spinBox_y.valueChanged.connect(self.update)
        page.spinBox_width.valueChanged.connect(self.update)
        page.spinBox_height.valueChanged.connect(self.update)
        page.checkBox_trans.stateChanged.connect(self.update)

        self.fillLabels = [
            'Solid',
            'Linear Gradient',
            'Radial Gradient',
        ]
        for label in self.fillLabels:
            page.comboBox_fill.addItem(label)
        page.comboBox_fill.setCurrentIndex(0)
        page.comboBox_fill.currentIndexChanged.connect(self.update)
        page.comboBox_spread.currentIndexChanged.connect(self.update)
        page.spinBox_radialGradient_end.valueChanged.connect(self.update)
        page.spinBox_radialGradient_start.valueChanged.connect(self.update)
        page.spinBox_radialGradient_spread.valueChanged.connect(self.update)
        page.spinBox_linearGradient_end.valueChanged.connect(self.update)
        page.spinBox_linearGradient_start.valueChanged.connect(self.update)
        page.checkBox_stretch.stateChanged.connect(self.update)

        self.page = page
        return page

    def update(self):
        self.color1 = self.RGBFromString(self.page.lineEdit_color1.text())
        self.color2 = self.RGBFromString(self.page.lineEdit_color2.text())
        self.x = self.page.spinBox_x.value()
        self.y = self.page.spinBox_y.value()
        self.sizeWidth = self.page.spinBox_width.value()
        self.sizeHeight = self.page.spinBox_height.value()
        self.trans = self.page.checkBox_trans.isChecked()
        self.spread = self.page.comboBox_spread.currentIndex()

        self.RG_start = self.page.spinBox_radialGradient_start.value()
        self.RG_end = self.page.spinBox_radialGradient_end.value()
        self.RG_centre = self.page.spinBox_radialGradient_spread.value()
        self.stretch = self.page.checkBox_stretch.isChecked()
        self.LG_start = self.page.spinBox_linearGradient_start.value()
        self.LG_end = self.page.spinBox_linearGradient_end.value()

        self.fillType = self.page.comboBox_fill.currentIndex()
        if self.fillType == 0:
            self.page.lineEdit_color2.setEnabled(False)
            self.page.pushButton_color2.setEnabled(False)
            self.page.checkBox_trans.setEnabled(False)
            self.page.checkBox_stretch.setEnabled(False)
            self.page.comboBox_spread.setEnabled(False)
        else:
            self.page.lineEdit_color2.setEnabled(True)
            self.page.pushButton_color2.setEnabled(True)
            self.page.checkBox_trans.setEnabled(True)
            self.page.checkBox_stretch.setEnabled(True)
            self.page.comboBox_spread.setEnabled(True)
        self.page.fillWidget.setCurrentIndex(self.fillType)

        self.parent.drawPreview()
        super().update()

    def previewRender(self, previewWorker):
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        return self.drawFrame(width, height)

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        return ['static']

    def frameRender(self, moduleNo, arrayNo, frameNo):
        width = int(self.worker.core.settings.value('outputWidth'))
        height = int(self.worker.core.settings.value('outputHeight'))
        return self.drawFrame(width, height)

    def drawFrame(self, width, height):
        r, g, b = self.color1
        shapeSize = (self.sizeWidth, self.sizeHeight)
        # in default state, skip all this logic and return a plain fill
        if self.fillType == 0 and shapeSize == (width, height) \
                and self.x == 0 and self.y == 0:
            return FloodFrame(width, height, (r, g, b, 255))

        # Return a solid image at x, y
        if self.fillType == 0:
            frame = BlankFrame(width, height)
            image = Image.new("RGBA", shapeSize, (r, g, b, 255))
            frame.paste(image, box=(self.x, self.y))
            return frame

        # Now fills that require using Qt...
        elif self.fillType > 0:
            image = FramePainter(width, height)

            if self.stretch:
                w = width
                h = height
            else:
                w = self.sizeWidth
                h = self.sizeWidth

        if self.fillType == 1:  # Linear Gradient
            brush = QtGui.QLinearGradient(
                self.LG_start,
                self.LG_start,
                self.LG_end+width/3,
                self.LG_end)

        elif self.fillType == 2:  # Radial Gradient
            brush = QtGui.QRadialGradient(
                self.RG_start,
                self.RG_end,
                w, h,
                self.RG_centre)

        brush.setSpread(self.spread)
        brush.setColorAt(0.0, PaintColor(*self.color1))
        if self.trans:
            brush.setColorAt(1.0, PaintColor(0, 0, 0, 0))
        elif self.fillType == 1 and self.stretch:
            brush.setColorAt(0.2, PaintColor(*self.color2))
        else:
            brush.setColorAt(1.0, PaintColor(*self.color2))
        image.setBrush(brush)
        image.drawRect(
            self.x, self.y,
            self.sizeWidth, self.sizeHeight
        )

        return image.finalize()

    def loadPreset(self, pr, presetName=None):
        super().loadPreset(pr, presetName)

        self.page.comboBox_fill.setCurrentIndex(pr['fillType'])
        self.page.lineEdit_color1.setText('%s,%s,%s' % pr['color1'])
        self.page.lineEdit_color2.setText('%s,%s,%s' % pr['color2'])
        self.page.spinBox_x.setValue(pr['x'])
        self.page.spinBox_y.setValue(pr['y'])
        self.page.spinBox_width.setValue(pr['width'])
        self.page.spinBox_height.setValue(pr['height'])
        self.page.checkBox_trans.setChecked(pr['trans'])

        self.page.spinBox_radialGradient_start.setValue(pr['RG_start'])
        self.page.spinBox_radialGradient_end.setValue(pr['RG_end'])
        self.page.spinBox_radialGradient_spread.setValue(pr['RG_centre'])
        self.page.spinBox_linearGradient_start.setValue(pr['LG_start'])
        self.page.spinBox_linearGradient_end.setValue(pr['LG_end'])
        self.page.checkBox_stretch.setChecked(pr['stretch'])
        self.page.comboBox_spread.setCurrentIndex(pr['spread'])

        btnStyle1 = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*pr['color1']).name()
        btnStyle2 = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*pr['color2']).name()
        self.page.pushButton_color1.setStyleSheet(btnStyle1)
        self.page.pushButton_color2.setStyleSheet(btnStyle2)

    def savePreset(self):
        return {
            'preset': self.currentPreset,
            'color1': self.color1,
            'color2': self.color2,
            'x': self.x,
            'y': self.y,
            'fillType': self.fillType,
            'width': self.sizeWidth,
            'height': self.sizeHeight,
            'trans': self.trans,
            'stretch': self.stretch,
            'spread': self.spread,
            'RG_start': self.RG_start,
            'RG_end': self.RG_end,
            'RG_centre': self.RG_centre,
            'LG_start': self.LG_start,
            'LG_end': self.LG_end,
        }

    def pickColor(self, num):
        RGBstring, btnStyle = super().pickColor()
        if not RGBstring:
            return
        if num == 1:
            self.page.lineEdit_color1.setText(RGBstring)
            self.page.pushButton_color1.setStyleSheet(btnStyle)
        else:
            self.page.lineEdit_color2.setText(RGBstring)
            self.page.pushButton_color2.setStyleSheet(btnStyle)

    def commandHelp(self):
        print('Specify a color:\n    color=255,255,255')

    def command(self, arg):
        if not arg.startswith('preset=') and '=' in arg:
            key, arg = arg.split('=', 1)
            if key == 'color':
                self.page.lineEdit_color1.setText(arg)
                return
        super().command(arg)
