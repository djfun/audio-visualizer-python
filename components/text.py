from PIL import Image, ImageDraw
from PyQt4.QtGui import QPainter, QColor, QFont
from PyQt4 import uic, QtGui, QtCore
from PIL.ImageQt import ImageQt
import os, io
from . import __base__


class Component(__base__.Component):
    '''Title Text'''
    def __init__(self):
        super().__init__()
        self.titleFont = QFont()

    def widget(self, parent):
        height = int(parent.settings.value('outputHeight'))
        width = int(parent.settings.value('outputWidth'))
        self.parent = parent
        self.textColor = (255,255,255)
        self.title = 'Text'
        self.titleFont = None
        self.alignment = 1
        self.fontSize = height / 13.5
        self.xPosition = width / 2
        self.yPosition = height / 2 * 1.036
        
        page = uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'text.ui'))
        page.comboBox_textAlign.addItem("Left")
        page.comboBox_textAlign.addItem("Middle")
        page.comboBox_textAlign.addItem("Right")

        page.lineEdit_textColor.setText('%s,%s,%s' % self.textColor)
        page.pushButton_textColor.clicked.connect(lambda: self.pickColor())
        btnStyle = "QPushButton { background-color : %s; outline: none; }" % QColor(*self.textColor).name()
        page.pushButton_textColor.setStyleSheet(btnStyle)

        page.lineEdit_title.setText(self.title)
        #if self.titleFont:
        #  page.fontComboBox_titleFont.setCurrentFont(QFont(self.titleFont))
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
        self.textColor = self.RGBFromString(self.page.lineEdit_textColor.text())
        
        self.parent.drawPreview()
        
    def getXY(self):
        '''Returns true x, y after considering alignment settings'''
        fm = QtGui.QFontMetrics(self.titleFont)
        if self.alignment == 0:      #Left
           x = self.xPosition
        if self.alignment == 1:      #Middle
           offset = fm.width(self.title)/2
           x = self.xPosition - offset
        if self.alignment == 2:      #Right
           offset = fm.width(self.title)
           x = self.xPosition - offset
        return x, self.yPosition
        
        
    def loadPreset(self, pr):
        self.page.lineEdit_title.setText(pr['title'])
        font = QFont(); font.fromString(pr['titleFont'])
        self.page.fontComboBox_titleFont.setCurrentFont(font)
        self.page.spinBox_fontSize.setValue(pr['fontSize'])
        self.page.comboBox_textAlign.setCurrentIndex(pr['alignment'])
        self.page.spinBox_xTextAlign.setValue(pr['xPosition'])
        self.page.spinBox_yTextAlign.setValue(pr['yPosition'])
        self.page.lineEdit_textColor.setText('%s,%s,%s' % pr['textColor'])
        btnStyle = "QPushButton { background-color : %s; outline: none; }" % QColor(*pr['textColor']).name()
        self.page.pushButton_textColor.setStyleSheet(btnStyle)
        
    def savePreset(self):
        return {
                'title' : self.title,
                'titleFont' : self.titleFont.toString(),
                'alignment' : self.alignment,
                'fontSize' : self.fontSize,
                'xPosition' : self.xPosition,
                'yPosition' : self.yPosition,
                'textColor' : self.textColor
                }

    def previewRender(self, previewWorker):
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        return self.addText(width, height)

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        return ['static']
        
    def frameRender(self, moduleNo, frameNo):
        width = int(self.worker.core.settings.value('outputWidth'))
        height = int(self.worker.core.settings.value('outputHeight'))
        return self.addText(width, height)

    def addText(self, width, height):
        x, y = self.getXY()
        im = Image.new("RGBA", (width, height),(0,0,0,0))
        image = ImageQt(im)
   
        painter = QPainter(image)
        self.titleFont.setPixelSize(self.fontSize)
        painter.setFont(self.titleFont)
        painter.setPen(QColor(*self.textColor))
        painter.drawText(x, y, self.title)
        painter.end()

        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.ReadWrite)
        image.save(buffer, "PNG")

        strio = io.BytesIO()
        strio.write(buffer.data())
        buffer.close()
        strio.seek(0)
        return Image.open(strio)

    def pickColor(self):
        RGBstring, btnStyle = super().pickColor()
        if not RGBstring:
            return
        self.page.lineEdit_textColor.setText(RGBstring)
        self.page.pushButton_textColor.setStyleSheet(btnStyle)

    def cancel(self):
        self.canceled = True

    def reset(self):
        self.canceled = False
