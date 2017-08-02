from PIL import Image, ImageDraw
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QColor
from PIL.ImageQt import ImageQt
import os

from component import Component
from toolkit.frame import BlankFrame, FloodFrame, FramePainter, PaintColor


class Component(Component):
    name = 'Color'
    version = '1.0.0'

    def widget(self, *args):
        self.x = 0
        self.y = 0
        super().widget(*args)

        self.page.lineEdit_color1.setText('0,0,0')
        self.page.lineEdit_color2.setText('133,133,133')

        # disable color #2 until non-default 'fill' option gets changed
        self.page.lineEdit_color2.setDisabled(True)
        self.page.pushButton_color2.setDisabled(True)
        self.page.spinBox_width.setValue(
            int(self.settings.value("outputWidth")))
        self.page.spinBox_height.setValue(
            int(self.settings.value("outputHeight")))

        self.fillLabels = [
            'Solid',
            'Linear Gradient',
            'Radial Gradient',
        ]
        for label in self.fillLabels:
            self.page.comboBox_fill.addItem(label)
        self.page.comboBox_fill.setCurrentIndex(0)

        self.trackWidgets(
            {
                'x': self.page.spinBox_x,
                'y': self.page.spinBox_y,
                'sizeWidth': self.page.spinBox_width,
                'sizeHeight': self.page.spinBox_height,
                'trans': self.page.checkBox_trans,
                'spread': self.page.comboBox_spread,
                'stretch': self.page.checkBox_stretch,
                'RG_start': self.page.spinBox_radialGradient_start,
                'LG_start': self.page.spinBox_linearGradient_start,
                'RG_end': self.page.spinBox_radialGradient_end,
                'LG_end': self.page.spinBox_linearGradient_end,
                'RG_centre': self.page.spinBox_radialGradient_spread,
                'fillType': self.page.comboBox_fill,
                'color1': self.page.lineEdit_color1,
                'color2': self.page.lineEdit_color2,
            }, presetNames={
                'sizeWidth': 'width',
                'sizeHeight': 'height',
            }, colorWidgets={
                'color1': self.page.pushButton_color1,
                'color2': self.page.pushButton_color2,
            }, relativeWidgets={
                'x': 'x',
                'y': 'y',
                'sizeWidth': 'x',
                'sizeHeight': 'y',
            },
        )

    def update(self):
        fillType = self.page.comboBox_fill.currentIndex()
        if fillType == 0:
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
        if self.page.checkBox_trans.isChecked():
            self.page.lineEdit_color2.setEnabled(False)
            self.page.pushButton_color2.setEnabled(False)
        self.page.fillWidget.setCurrentIndex(fillType)

        super().update()

    def previewRender(self):
        return self.drawFrame(self.width, self.height)

    def properties(self):
        return ['static']

    def frameRender(self, frameNo):
        return self.drawFrame(self.width, self.height)

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

    def commandHelp(self):
        print('Specify a color:\n    color=255,255,255')

    def command(self, arg):
        if '=' in arg:
            key, arg = arg.split('=', 1)
            if key == 'color':
                self.page.lineEdit_color1.setText(arg)
                return
        super().command(arg)
