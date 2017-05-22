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
  
  videoTask = QtCore.pyqtSignal(str, str, QFont, int, int, int, int, str, str)
  
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
    self.parser.add_argument('-x', '--xposition', dest='xposition', help='x position', required=False)
    self.parser.add_argument('-y', '--yposition', dest='yposition', help='y position', required=False)
    self.parser.add_argument('-a', '--alignment', dest='alignment', help='title alignment', required=False, type=int, choices=[0, 1, 2])
    self.args = self.parser.parse_args()

    self.settings = QSettings('settings.ini', QSettings.IniFormat)
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
    sys.exit(0)

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
    sys.exit(0)

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
       "Open Background Image", backgroundDir, "Image Files (*.jpg *.png);; Video Files (*.mp4)");

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
    self.videoWorker.progressBarSetText.connect(self.progressBarSetText)
    
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

  def progressBarSetText(self, value):
    self.window.progressBar_create.setFormat(value)

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
    window = uic.loadUi("main.ui")
  
    main = Main(window)

    signal.signal(signal.SIGINT, main.cleanUp)
    atexit.register(main.cleanUp)

    sys.exit(app.exec_())
