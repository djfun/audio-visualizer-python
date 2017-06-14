from PIL import Image, ImageDraw
from PyQt4 import uic, QtGui, QtCore
from PyQt4.QtGui import QColor
import os
from . import __base__


class Component(__base__.Component):
    '''Color'''

    modified = QtCore.pyqtSignal(int, dict)

    def widget(self, parent):
        self.parent = parent
        page = uic.loadUi(os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'color.ui'))

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
        page.spinBox_x.setValue(self.x)
        page.spinBox_x.setValue(self.y)

        page.lineEdit_color1.textChanged.connect(self.update)
        page.lineEdit_color2.textChanged.connect(self.update)
        page.spinBox_x.valueChanged.connect(self.update)
        page.spinBox_y.valueChanged.connect(self.update)
        self.page = page
        return page

    def update(self):
        self.color1 = self.RGBFromString(self.page.lineEdit_color1.text())
        self.color2 = self.RGBFromString(self.page.lineEdit_color2.text())
        self.x = self.page.spinBox_x.value()
        self.y = self.page.spinBox_y.value()
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
        return Image.new("RGBA", (width, height), (r, g, b, 255))

    def loadPreset(self, pr, presetName=None):
        super().loadPreset(pr, presetName)

        self.page.lineEdit_color1.setText('%s,%s,%s' % pr['color1'])
        self.page.lineEdit_color2.setText('%s,%s,%s' % pr['color2'])

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
