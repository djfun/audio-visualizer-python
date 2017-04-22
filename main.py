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

import preview_thread, core, video_thread

class Main(QtCore.QObject):

  newTask = QtCore.pyqtSignal(str, str, QFont, int, int, int, int)
  processTask = QtCore.pyqtSignal()
  videoTask = QtCore.pyqtSignal(str, str, QFont, int, int, int, int, str, str)

  def __init__(self, window):

    QtCore.QObject.__init__(self)

    # print('main thread id: {}'.format(QtCore.QThread.currentThreadId()))
    self.window = window
    self.core = core.Core()

    self.settings = QSettings('settings.ini', QSettings.IniFormat)

    self.previewQueue = Queue()

    self.previewThread = QtCore.QThread(self)
    self.previewWorker = preview_thread.Worker(self, self.previewQueue)

    self.previewWorker.moveToThread(self.previewThread)
    self.previewWorker.imageCreated.connect(self.showPreviewImage)
    
    self.previewThread.start()

    self.timer = QtCore.QTimer(self)
    self.timer.timeout.connect(self.processTask.emit)
    self.timer.start(500)
    
    window.pushButton_selectInput.clicked.connect(self.openInputFileDialog)
    window.pushButton_selectOutput.clicked.connect(self.openOutputFileDialog)
    window.pushButton_createVideo.clicked.connect(self.createAudioVisualisation)
    window.pushButton_selectBackground.clicked.connect(self.openBackgroundFileDialog)

    window.progressBar_create.setValue(0)
    window.setWindowTitle("Audio Visualizer")
    window.pushButton_selectInput.setText("Select Input Music File")
    window.pushButton_selectOutput.setText("Select Output Video File")
    window.pushButton_selectBackground.setText("Select Background Image")
    window.label_font.setText("Title Font")
    window.label_alignment.setText("Title Options")
    window.label_fontsize.setText("Fontsize")
    window.label_title.setText("Title Text")
    window.pushButton_createVideo.setText("Create Video")
    window.groupBox_create.setTitle("Create")
    window.groupBox_settings.setTitle("Settings")
    window.groupBox_preview.setTitle("Preview")

    window.alignmentComboBox.addItem("Left")
    window.alignmentComboBox.addItem("Middle")
    window.alignmentComboBox.addItem("Right")
    window.fontsizeSpinBox.setValue(35)
    window.textXSpinBox.setValue(70)
    window.textYSpinBox.setValue(375)

    titleFont = self.settings.value("titleFont")
    if not titleFont == None: 
      window.fontComboBox.setCurrentFont(QFont(titleFont))

    alignment = self.settings.value("alignment")
    if not alignment == None:
      window.alignmentComboBox.setCurrentIndex(int(alignment))
    fontSize = self.settings.value("fontSize")
    if not fontSize == None:
      window.fontsizeSpinBox.setValue(int(fontSize))
    xPosition = self.settings.value("xPosition")
    if not xPosition == None:
      window.textXSpinBox.setValue(int(xPosition))
    yPosition = self.settings.value("yPosition")
    if not yPosition == None:
      window.textYSpinBox.setValue(int(yPosition))

    window.fontComboBox.currentFontChanged.connect(self.drawPreview)
    window.lineEdit_title.textChanged.connect(self.drawPreview)
    window.alignmentComboBox.currentIndexChanged.connect(self.drawPreview)
    window.textXSpinBox.valueChanged.connect(self.drawPreview)
    window.textYSpinBox.valueChanged.connect(self.drawPreview)
    window.fontsizeSpinBox.valueChanged.connect(self.drawPreview)

    self.drawPreview()

    window.show()

  def cleanUp(self):
    self.timer.stop()
    self.previewThread.quit()
    self.previewThread.wait()

    self.settings.setValue("titleFont", self.window.fontComboBox.currentFont().toString())
    self.settings.setValue("alignment", str(self.window.alignmentComboBox.currentIndex()))
    self.settings.setValue("fontSize", str(self.window.fontsizeSpinBox.value()))
    self.settings.setValue("xPosition", str(self.window.textXSpinBox.value()))
    self.settings.setValue("yPosition", str(self.window.textYSpinBox.value()))

  def openInputFileDialog(self):
    inputDir = self.settings.value("inputDir", expanduser("~"))

    fileName = QtGui.QFileDialog.getOpenFileName(self.window,
       "Open Music File", inputDir, "Music Files (*.mp3 *.wav *.ogg *.flac)");

    if not fileName == "": 
      self.settings.setValue("inputDir", os.path.dirname(fileName))
      self.window.label_input.setText(fileName)

  def openOutputFileDialog(self):
    outputDir = self.settings.value("outputDir", expanduser("~"))

    fileName = QtGui.QFileDialog.getSaveFileName(self.window,
       "Set Output Video File", outputDir, "Video Files (*.mkv)");

    if not fileName == "": 
      self.settings.setValue("outputDir", os.path.dirname(fileName))
      self.window.label_output.setText(fileName)

  def openBackgroundFileDialog(self):
    backgroundDir = self.settings.value("backgroundDir", expanduser("~"))

    fileName = QtGui.QFileDialog.getOpenFileName(self.window,
       "Open Background Image", backgroundDir, "Image Files (*.jpg *.png)");

    if not fileName == "": 
      self.settings.setValue("backgroundDir", os.path.dirname(fileName))
      self.window.label_background.setText(fileName)
    self.drawPreview()

  def createAudioVisualisation(self):
    ffmpeg_cmd = self.settings.value("ffmpeg_cmd", expanduser("~"))

    self.videoThread = QtCore.QThread(self)
    self.videoWorker = video_thread.Worker(self)

    self.videoWorker.moveToThread(self.videoThread)
    self.videoWorker.videoCreated.connect(self.videoCreated)
    self.videoWorker.progressBarUpdate.connect(self.progressBarUpdated)
    
    self.videoThread.start()
    self.videoTask.emit(self.window.label_background.text(),
      self.window.lineEdit_title.text(),
      self.window.fontComboBox.currentFont(),
      self.window.fontsizeSpinBox.value(),
      self.window.alignmentComboBox.currentIndex(),
      self.window.textXSpinBox.value(),
      self.window.textYSpinBox.value(),
      self.window.label_input.text(),
      self.window.label_output.text())
    

  def progressBarUpdated(self, value):
    self.window.progressBar_create.setValue(value)

  def videoCreated(self):
    self.videoThread.quit()
    self.videoThread.wait()

  def drawPreview(self):
    self.newTask.emit(self.window.label_background.text(),
      self.window.lineEdit_title.text(),
      self.window.fontComboBox.currentFont(),
      self.window.fontsizeSpinBox.value(),
      self.window.alignmentComboBox.currentIndex(),
      self.window.textXSpinBox.value(),
      self.window.textYSpinBox.value())
    # self.processTask.emit()

  def showPreviewImage(self, image):
    self._scaledPreviewImage = image
    self._previewPixmap = QtGui.QPixmap.fromImage(self._scaledPreviewImage)

    self.window.label_preview.setPixmap(self._previewPixmap)

if __name__ == "__main__":
  app = QtGui.QApplication(sys.argv)
  window = uic.loadUi("main.ui")
  
  main = Main(window)

  atexit.register(main.cleanUp)

  sys.exit(app.exec_())
