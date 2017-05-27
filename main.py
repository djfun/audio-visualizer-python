import sys, io, os
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtGui import QPainter, QColor, QFont
from os.path import expanduser
import subprocess as sp
import numpy
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageQt import ImageQt
import atexit
from queue import Queue
from PyQt4.QtCore import QSettings
import signal

import preview_thread, core, video_thread

class Command(QtCore.QObject):
  
  videoTask = QtCore.pyqtSignal(str, str, QFont, int, int, int, int, tuple, tuple, str, str)
  
  def __init__(self):
    QtCore.QObject.__init__(self)

    import argparse
    self.parser = argparse.ArgumentParser(description='Create a visualization for an audio file')
    self.parser.add_argument('-i', '--input', dest='input', help='input audio file', required=True)
    self.parser.add_argument('-o', '--output', dest='output', help='output video file', required=True)
    self.parser.add_argument('-b', '--background', dest='bgimage', help='background image file', required=True)
    self.parser.add_argument('-t', '--text', dest='text', help='title text', required=True)
    self.parser.add_argument('-f', '--font', dest='font', help='title font', required=False)
    self.parser.add_argument('-s', '--fontsize', dest='fontsize', help='title font size', required=False)
    self.parser.add_argument('-c', '--textcolor', dest='textcolor', help='title text color in r,g,b format', required=False)
    self.parser.add_argument('-C', '--viscolor', dest='viscolor', help='visualization color in r,g,b format', required=False)
    self.parser.add_argument('-x', '--xposition', dest='xposition', help='x position', required=False)
    self.parser.add_argument('-y', '--yposition', dest='yposition', help='y position', required=False)
    self.parser.add_argument('-a', '--alignment', dest='alignment', help='title alignment', required=False, type=int, choices=[0, 1, 2])
    self.args = self.parser.parse_args()

    self.settings = QSettings('settings.ini', QSettings.IniFormat)
    LoadDefaultSettings(self)
    
    # load colours as tuples from comma-separated strings
    self.textColor = core.Core.RGBFromString(self.settings.value("textColor", '255, 255, 255'))
    self.visColor = core.Core.RGBFromString(self.settings.value("visColor", '255, 255, 255'))
    if self.args.textcolor:
      self.textColor = core.Core.RGBFromString(self.args.textcolor)
    if self.args.viscolor:
      self.visColor = core.Core.RGBFromString(self.args.viscolor)
    
    # font settings
    if self.args.font:
      self.font = QFont(self.args.font)
    else:
      self.font = QFont(self.settings.value("titleFont", QFont()))
    
    if self.args.fontsize:
      self.fontsize = int(self.args.fontsize)
    else:
      self.fontsize = int(self.settings.value("fontSize", 35))
    if self.args.alignment:
      self.alignment = int(self.args.alignment)
    else:
      self.alignment = int(self.settings.value("alignment", 0))

    if self.args.xposition:
      self.textX = int(self.args.xposition)
    else:
      self.textX = int(self.settings.value("xPosition", 70))

    if self.args.yposition:
      self.textY = int(self.args.yposition)
    else:
      self.textY = int(self.settings.value("yPosition", 375))

    ffmpeg_cmd = self.settings.value("ffmpeg_cmd", expanduser("~"))

    self.videoThread = QtCore.QThread(self)
    self.videoWorker = video_thread.Worker(self)

    self.videoWorker.moveToThread(self.videoThread)
    self.videoWorker.videoCreated.connect(self.videoCreated)
    
    self.videoThread.start()
    self.videoTask.emit(self.args.bgimage,
      self.args.text,
      self.font,
      self.fontsize,
      self.alignment,
      self.textX,
      self.textY,
      self.textColor,
      self.visColor,
      self.args.input,
      self.args.output)

  def videoCreated(self):
    self.videoThread.quit()
    self.videoThread.wait()
    self.cleanUp()

  def cleanUp(self):
    self.settings.setValue("titleFont", self.font.toString())
    self.settings.setValue("alignment", str(self.alignment))
    self.settings.setValue("fontSize", str(self.fontsize))
    self.settings.setValue("xPosition", str(self.textX))
    self.settings.setValue("yPosition", str(self.textY))
    self.settings.setValue("visColor", '%s,%s,%s' % self.visColor)
    self.settings.setValue("textColor", '%s,%s,%s' % self.textColor)
    sys.exit(0)

class Main(QtCore.QObject):

  newTask = QtCore.pyqtSignal(str, str, QFont, int, int, int, int, tuple, tuple)
  processTask = QtCore.pyqtSignal()
  videoTask = QtCore.pyqtSignal(str, str, QFont, int, int, int, int, tuple, tuple, str, str)

  def __init__(self, window):
    QtCore.QObject.__init__(self)

    # print('main thread id: {}'.format(QtCore.QThread.currentThreadId()))
    self.window = window
    self.core = core.Core()
    self.settings = QSettings('settings.ini', QSettings.IniFormat)
    LoadDefaultSettings(self)
    
    # load colors as tuples from a comma-separated string
    self.textColor = core.Core.RGBFromString(self.settings.value("textColor", '255, 255, 255'))
    self.visColor = core.Core.RGBFromString(self.settings.value("visColor", '255, 255, 255'))

    self.previewQueue = Queue()

    self.previewThread = QtCore.QThread(self)
    self.previewWorker = preview_thread.Worker(self, self.previewQueue)

    self.previewWorker.moveToThread(self.previewThread)
    self.previewWorker.imageCreated.connect(self.showPreviewImage)
    
    self.previewThread.start()

    self.timer = QtCore.QTimer(self)
    self.timer.timeout.connect(self.processTask.emit)
    self.timer.start(500)

    window.toolButton_selectAudioFile.clicked.connect(self.openInputFileDialog)
    window.toolButton_selectBackground.clicked.connect(self.openBackgroundFileDialog)
    window.toolButton_selectOutputFile.clicked.connect(self.openOutputFileDialog)
    window.progressBar_createVideo.setValue(0)
    window.pushButton_createVideo.clicked.connect(self.createAudioVisualisation)
    window.setWindowTitle("Audio Visualizer")
    window.comboBox_textAlign.addItem("Left")
    window.comboBox_textAlign.addItem("Middle")
    window.comboBox_textAlign.addItem("Right")
    window.comboBox_textAlign.setCurrentIndex(1)

    window.comboBox_visLayout.addItem("Classic")
    window.comboBox_visLayout.addItem("Split")
    window.comboBox_visLayout.addItem("Bottom")
    visLayoutValue = int(self.settings.value('visLayout'))
    window.comboBox_visLayout.setCurrentIndex(visLayoutValue)

    currentRes = self.settings.value('outputWidth')+'x'+self.settings.value('outputHeight')
    for i, res in enumerate(self.resolutions):
      window.comboBox_resolution.addItem(res)
      if res == currentRes:
        currentRes = i
    window.comboBox_resolution.setCurrentIndex(currentRes)
    window.comboBox_resolution.currentIndexChanged.connect(self.updateResolution)

    # FIXME This needs to be changed in a future commit.
    # We should be setting these values somewhere else.
    window.spinBox_fontSize.setValue(int(int(self.settings.value("outputHeight")) / 14 ))
    window.spinBox_xTextAlign.setValue(int(int(self.settings.value('outputWidth'))/2))
    window.spinBox_yTextAlign.setValue(int(int(self.settings.value('outputHeight'))/2))

    window.lineEdit_textColor.setText('%s,%s,%s' % self.textColor)
    window.lineEdit_visColor.setText('%s,%s,%s' % self.visColor)
    window.pushButton_textColor.clicked.connect(lambda: self.pickColor('text'))
    window.pushButton_visColor.clicked.connect(lambda: self.pickColor('vis'))
    btnStyle = "QPushButton { background-color : %s; outline: none; }" % QColor(*self.textColor).name()
    window.pushButton_textColor.setStyleSheet(btnStyle)
    btnStyle = "QPushButton { background-color : %s; outline: none; }" % QColor(*self.visColor).name()
    window.pushButton_visColor.setStyleSheet(btnStyle)

    titleFont = self.settings.value("titleFont")
    if not titleFont == None: 
      window.fontComboBox_titleFont.setCurrentFont(QFont(titleFont))

    alignment = self.settings.value("alignment")
    if not alignment == None:
      window.comboBox_textAlign.setCurrentIndex(int(alignment))
    fontSize = self.settings.value("fontSize")
    if not fontSize == None:
      window.spinBox_fontSize.setValue(int(fontSize))
    xPosition = self.settings.value("xPosition")
    if not xPosition == None:
      window.spinBox_xTextAlign.setValue(int(xPosition))
    yPosition = self.settings.value("yPosition")
    if not yPosition == None:
      window.spinBox_yTextAlign.setValue(int(yPosition))

    window.fontComboBox_titleFont.currentFontChanged.connect(self.drawPreview)
    window.lineEdit_title.textChanged.connect(self.drawPreview)
    window.comboBox_textAlign.currentIndexChanged.connect(self.drawPreview)
    window.comboBox_visLayout.currentIndexChanged.connect(self.drawPreview)
    window.spinBox_xTextAlign.valueChanged.connect(self.drawPreview)
    window.spinBox_yTextAlign.valueChanged.connect(self.drawPreview)
    window.spinBox_fontSize.valueChanged.connect(self.drawPreview)
    window.lineEdit_textColor.textChanged.connect(self.drawPreview)
    window.lineEdit_visColor.textChanged.connect(self.drawPreview)
    
    self.drawPreview()

    window.show()

  def cleanUp(self):
    self.timer.stop()
    self.previewThread.quit()
    self.previewThread.wait()
       
    self.settings.setValue("titleFont", self.window.fontComboBox_titleFont.currentFont().toString())
    self.settings.setValue("alignment", str(self.window.comboBox_textAlign.currentIndex()))
    self.settings.setValue("fontSize", str(self.window.spinBox_fontSize.value()))
    self.settings.setValue("xPosition", str(self.window.spinBox_xTextAlign.value()))
    self.settings.setValue("yPosition", str(self.window.spinBox_yTextAlign.value()))
    self.settings.setValue("visColor", self.window.lineEdit_visColor.text())
    self.settings.setValue("textColor", self.window.lineEdit_textColor.text())

  def openInputFileDialog(self):
    inputDir = self.settings.value("inputDir", expanduser("~"))

    fileName = QtGui.QFileDialog.getOpenFileName(self.window,
       "Open Music File", inputDir, "Music Files (*.mp3 *.wav *.ogg *.flac)");

    if not fileName == "": 
      self.settings.setValue("inputDir", os.path.dirname(fileName))
      self.window.lineEdit_audioFile.setText(fileName)

  def openOutputFileDialog(self):
    outputDir = self.settings.value("outputDir", expanduser("~"))

    fileName = QtGui.QFileDialog.getSaveFileName(self.window,
       "Set Output Video File", outputDir, "Video Files (*.mkv)");

    if not fileName == "": 
      self.settings.setValue("outputDir", os.path.dirname(fileName))
      self.window.lineEdit_outputFile.setText(fileName)

  def openBackgroundFileDialog(self):
    backgroundDir = self.settings.value("backgroundDir", expanduser("~"))

    fileName = QtGui.QFileDialog.getOpenFileName(self.window,
       "Open Background Image", backgroundDir, "Image Files (*.jpg *.png);; Video Files (*.mp4)");

    if not fileName == "": 
      self.settings.setValue("backgroundDir", os.path.dirname(fileName))
      self.window.lineEdit_background.setText(fileName)
    self.drawPreview()

  def createAudioVisualisation(self):
    ffmpeg_cmd = self.settings.value("ffmpeg_cmd", expanduser("~"))

    self.videoThread = QtCore.QThread(self)
    self.videoWorker = video_thread.Worker(self)

    self.videoWorker.moveToThread(self.videoThread)
    self.videoWorker.videoCreated.connect(self.videoCreated)
    self.videoWorker.progressBarUpdate.connect(self.progressBarUpdated)
    self.videoWorker.progressBarSetText.connect(self.progressBarSetText)
    
    self.videoThread.start()
    self.videoTask.emit(self.window.lineEdit_background.text(),
      self.window.lineEdit_title.text(),
      self.window.fontComboBox_titleFont.currentFont(),
      self.window.spinBox_fontSize.value(),
      self.window.comboBox_textAlign.currentIndex(),
      self.window.spinBox_xTextAlign.value(),
      self.window.spinBox_yTextAlign.value(),
      core.Core.RGBFromString(self.window.lineEdit_textColor.text()),
      core.Core.RGBFromString(self.window.lineEdit_visColor.text()),
      self.window.lineEdit_audioFile.text(),
      self.window.lineEdit_outputFile.text())
    

  def progressBarUpdated(self, value):
    self.window.progressBar_createVideo.setValue(value)

  def progressBarSetText(self, value):
    self.window.progressBar_createVideo.setFormat(value)

  def videoCreated(self):
    self.videoThread.quit()
    self.videoThread.wait()

  def updateResolution(self):
    resIndex = int(window.comboBox_resolution.currentIndex())
    res = self.resolutions[resIndex].split('x')
    self.settings.setValue('outputWidth',res[0])
    self.settings.setValue('outputHeight',res[1])
    self.drawPreview

  def drawPreview(self):
    self.settings.setValue('visLayout', self.window.comboBox_visLayout.currentIndex())
    self.newTask.emit(self.window.lineEdit_background.text(),
      self.window.lineEdit_title.text(),
      self.window.fontComboBox_titleFont.currentFont(),
      self.window.spinBox_fontSize.value(),
      self.window.comboBox_textAlign.currentIndex(),
      self.window.spinBox_xTextAlign.value(),
      self.window.spinBox_yTextAlign.value(),
      core.Core.RGBFromString(self.window.lineEdit_textColor.text()),
      core.Core.RGBFromString(self.window.lineEdit_visColor.text()))
    # self.processTask.emit()

  def showPreviewImage(self, image):
    self._scaledPreviewImage = image
    self._previewPixmap = QtGui.QPixmap.fromImage(self._scaledPreviewImage)

    self.window.label_previewContainer.setPixmap(self._previewPixmap)

  def pickColor(self, colorTarget):
    color = QtGui.QColorDialog.getColor()
    if color.isValid():
       RGBstring = '%s,%s,%s' % (str(color.red()), str(color.green()), str(color.blue()))
       btnStyle = "QPushButton { background-color : %s; outline: none; }" % color.name()
       if colorTarget == 'text':
         self.window.lineEdit_textColor.setText(RGBstring)
         window.pushButton_textColor.setStyleSheet(btnStyle)
       elif colorTarget == 'vis':
         self.window.lineEdit_visColor.setText(RGBstring)
         window.pushButton_visColor.setStyleSheet(btnStyle)

def LoadDefaultSettings(self):
  self.resolutions = [
      '1920x1080',
      '1280x720',
      '854x480'
    ]

  default = {
    "outputWidth": 1280,
    "outputHeight": 720,
    "outputFrameRate": 30,
    "outputAudioCodec": "aac",
    "outputAudioBitrate": "192k",
    "outputVideoCodec": "libx264",
    "outputVideoFormat": "yuv420p",
    "outputPreset": "medium",
    "outputFormat": "mp4",
    "visLayout": 0 
  }
  
  for parm, value in default.items():
    if self.settings.value(parm) == None:
      self.settings.setValue(parm,value)

if len(sys.argv) > 1:
  # command line mode
  app = QtGui.QApplication(sys.argv, False)
  command = Command()
  signal.signal(signal.SIGINT, command.cleanUp)
  sys.exit(app.exec_())
else:
  # gui mode
  if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = uic.loadUi("mainwindow.ui")
    # window.adjustSize()
    desc = QtGui.QDesktopWidget()
    dpi = desc.physicalDpiX()
    
    topMargin = 0 if (dpi == 96) else int(10 * (dpi / 96))
    window.resize(window.width() * (dpi / 96), window.height() * (dpi / 96))
    window.verticalLayout_2.setContentsMargins(0, topMargin, 0, 0)
  
    main = Main(window)

    signal.signal(signal.SIGINT, main.cleanUp)
    atexit.register(main.cleanUp)

    sys.exit(app.exec_())
