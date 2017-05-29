''' Title Text '''
from PIL import Image, ImageDraw
from PyQt4.QtGui import QPainter, QColor, QFont
from PyQt4 import uic, QtGui, QtCore
from PIL.ImageQt import ImageQt
import os, io


class Component:
    def __str__(self):
        return __doc__
        
    def widget(self, parent):
        height = int(parent.settings.value('outputHeight'))
        width = int(parent.settings.value('outputWidth'))
        self.parent = parent
        self.textColor = (255,255,255)
        self.title = 'Text'
        self.titleFont = None
        self.alignment = 1
        self.fontSize = height / 16
        self.xPosition = width / 2
        self.yPosition = height / 2
        
        page = uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'text.ui'))
        page.comboBox_textAlign.addItem("Left")
        page.comboBox_textAlign.addItem("Middle")
        page.comboBox_textAlign.addItem("Right")
        page.comboBox_textAlign.setCurrentIndex(1)

        page.spinBox_fontSize.setValue(int(int(parent.settings.value("outputHeight")) / 14 ))
        page.spinBox_xTextAlign.setValue(int(int(parent.settings.value('outputWidth'))/2))
        page.spinBox_yTextAlign.setValue(int(int(parent.settings.value('outputHeight'))/2))

        page.lineEdit_textColor.setText('%s,%s,%s' % self.textColor)
        page.pushButton_textColor.clicked.connect(lambda: self.pickColor())
        btnStyle = "QPushButton { background-color : %s; outline: none; }" % QColor(*self.textColor).name()
        page.pushButton_textColor.setStyleSheet(btnStyle)

        page.lineEdit_title.setText(self.title)
        if not self.titleFont == None: 
          page.fontComboBox_titleFont.setCurrentFont(QFont(self.titleFont))
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
        self.textColor = RGBFromString(self.page.lineEdit_textColor.text())
        fm = QtGui.QFontMetrics(self.titleFont)
        if self.alignment == 0:      #Left
           self.xPosition = self.xPosition
        if self.alignment == 1:      #Middle
           self.xPosition = self.xPosition - fm.width(self.title)/2
        if self.alignment == 2:      #Right
           self.xPosition = self.xPosition - fm.width(self.title)
        
        self.parent.drawPreview()
        
    def savePreset(self):
        return {}

    def previewRender(self, previewWorker):
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        return self.addText(width, height)

    def preFrameRender(self, **kwargs):
        for kwarg, value in kwargs.items():
            exec('self.%s = value' % kwarg)
        
    def frameRender(self, moduleNo, frameNo):
        width = int(self.worker.core.settings.value('outputWidth'))
        height = int(self.worker.core.settings.value('outputHeight'))
        return self.addText(width, height)

    def addText(self, width, height):
        im = Image.new("RGBA", (width, height),(0,0,0,0))
        image = ImageQt(im)
   
        image1 = QtGui.QImage(image)
        painter = QPainter(image1)
        self.titleFont.setPixelSize(self.fontSize)
        painter.setFont(self.titleFont)
        painter.setPen(QColor(*self.textColor))

        fm = QtGui.QFontMetrics(self.titleFont)
        painter.drawText(self.xPosition, self.yPosition, self.title)
        painter.end()

        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.ReadWrite)
        image1.save(buffer, "PNG")

        strio = io.BytesIO()
        strio.write(buffer.data())
        buffer.close()
        strio.seek(0)
        return Image.open(strio)

    def pickColor(self):
        color = QtGui.QColorDialog.getColor()
        if color.isValid():
           RGBstring = '%s,%s,%s' % (str(color.red()), str(color.green()), str(color.blue()))
           btnStyle = "QPushButton { background-color : %s; outline: none; }" % color.name()
           self.page.lineEdit_textColor.setText(RGBstring)
           self.page.pushButton_textColor.setStyleSheet(btnStyle)

def RGBFromString(string):
   ''' turns an RGB string like "255, 255, 255" into a tuple '''
   try:
     tup = tuple([int(i) for i in string.split(',')])
     if len(tup) != 3:
        raise ValueError
     for i in tup:
        if i > 255 or i < 0:
           raise ValueError
     return tup
   except:
     return (255, 255, 255)
