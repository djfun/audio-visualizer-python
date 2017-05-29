import sys, io, os
from os.path import expanduser
import atexit
from queue import Queue
import signal
from importlib import import_module
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import QSettings, QModelIndex
from PyQt4.QtGui import QDesktopServices

import preview_thread, core, video_thread

# FIXME: commandline functionality broken until we decide how to implement it
'''
class Command(QtCore.QObject):
  
  videoTask = QtCore.pyqtSignal(str, str, str, list)
  
  def __init__(self):
    QtCore.QObject.__init__(self)
    self.modules = []
    self.selectedComponents = []

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
      self.args.output,
      self.selectedComponents)

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
'''
class Main(QtCore.QObject):

  newTask = QtCore.pyqtSignal(str, list)
  processTask = QtCore.pyqtSignal()
  videoTask = QtCore.pyqtSignal(str, str, str, list)

  def __init__(self, window):
    QtCore.QObject.__init__(self)

    # print('main thread id: {}'.format(QtCore.QThread.currentThreadId()))
    self.window = window
    self.core = core.Core()
    self.settings = QSettings('settings.ini', QSettings.IniFormat)
    LoadDefaultSettings(self)

    # create data directory structure if needed
    self.dataDir = QDesktopServices.storageLocation(QDesktopServices.DataLocation)
    if not os.path.exists(self.dataDir):
        os.makedirs(self.dataDir)
    for neededDirectory in ('projects', 'presets'):
        if not os.path.exists(os.path.join(self.dataDir, neededDirectory)):
            os.mkdir(os.path.join(self.dataDir, neededDirectory))

    self.pages = []

    self.previewQueue = Queue()

    self.previewThread = QtCore.QThread(self)
    self.previewWorker = preview_thread.Worker(self, self.previewQueue)

    self.previewWorker.moveToThread(self.previewThread)
    self.previewWorker.imageCreated.connect(self.showPreviewImage)
    
    self.previewThread.start()

    self.timer = QtCore.QTimer(self)
    self.timer.timeout.connect(self.processTask.emit)
    self.timer.start(500)

    # begin decorating the window and connecting events
    window.toolButton_selectAudioFile.clicked.connect(self.openInputFileDialog)
    window.toolButton_selectBackground.clicked.connect(self.openBackgroundFileDialog)
    window.toolButton_selectOutputFile.clicked.connect(self.openOutputFileDialog)
    window.progressBar_createVideo.setValue(0)
    window.pushButton_createVideo.clicked.connect(self.createAudioVisualisation)
    window.setWindowTitle("Audio Visualizer")

    self.modules = self.findComponents()
    for component in self.modules:
        window.comboBox_componentSelection.addItem(component.__doc__)
    window.listWidget_componentList.clicked.connect(lambda _: self.changeComponentWidget())
    self.selectedComponents = []

    self.window.pushButton_addComponent.clicked.connect( \
        lambda _: self.addComponent(self.window.comboBox_componentSelection.currentIndex())
    )
    self.window.pushButton_removeComponent.clicked.connect(lambda _: self.removeComponent())

    currentRes = str(self.settings.value('outputWidth'))+'x'+str(self.settings.value('outputHeight'))
    for i, res in enumerate(self.resolutions):
      window.comboBox_resolution.addItem(res)
      if res == currentRes:
        currentRes = i
    window.comboBox_resolution.setCurrentIndex(currentRes)
    window.comboBox_resolution.currentIndexChanged.connect(self.updateResolution)

    self.window.pushButton_listMoveUp.clicked.connect(self.moveComponentUp)
    self.window.pushButton_listMoveDown.clicked.connect(self.moveComponentDown)

    self.window.pushButton_savePreset.clicked.connect(self.openSavePresetDialog)
    self.window.comboBox_openPreset.currentIndexChanged.connect( \
        lambda _: self.openPreset(self.window.comboBox_openPreset.currentIndex())
    )
    
    self.drawPreview()

    window.show()

  def cleanUp(self):
    self.timer.stop()
    self.previewThread.quit()
    self.previewThread.wait()
    # TODO: replace remembered settings with presets/projects
    '''
    self.settings.setValue("titleFont", self.window.fontComboBox_titleFont.currentFont().toString())
    self.settings.setValue("alignment", str(self.window.comboBox_textAlign.currentIndex()))
    self.settings.setValue("fontSize", str(self.window.spinBox_fontSize.value()))
    self.settings.setValue("xPosition", str(self.window.spinBox_xTextAlign.value()))
    self.settings.setValue("yPosition", str(self.window.spinBox_yTextAlign.value()))
    self.settings.setValue("visColor", self.window.lineEdit_visColor.text())
    self.settings.setValue("textColor", self.window.lineEdit_textColor.text())
    '''

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
    # create output video if mandatory settings are filled in
    if self.window.lineEdit_audioFile.text() and self.window.lineEdit_outputFile.text():
        ffmpeg_cmd = self.settings.value("ffmpeg_cmd", expanduser("~"))

        self.videoThread = QtCore.QThread(self)
        self.videoWorker = video_thread.Worker(self)

        self.videoWorker.moveToThread(self.videoThread)
        self.videoWorker.videoCreated.connect(self.videoCreated)
        self.videoWorker.progressBarUpdate.connect(self.progressBarUpdated)
        self.videoWorker.progressBarSetText.connect(self.progressBarSetText)
        
        self.videoThread.start()
        self.videoTask.emit(self.window.lineEdit_background.text(),
          self.window.lineEdit_audioFile.text(),
          self.window.lineEdit_outputFile.text(),
          self.selectedComponents)
    else:
        # TODO: use QMessageBox or similar to alert user that fields are empty
        pass
    
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
    self.drawPreview()

  def drawPreview(self):
    #self.settings.setValue('visLayout', self.window.comboBox_visLayout.currentIndex())
    self.newTask.emit(self.window.lineEdit_background.text(), self.selectedComponents)
    # self.processTask.emit()

  def showPreviewImage(self, image):
    self._scaledPreviewImage = image
    self._previewPixmap = QtGui.QPixmap.fromImage(self._scaledPreviewImage)

    self.window.label_previewContainer.setPixmap(self._previewPixmap)

  def findComponents(self):
    def findComponents():
        srcPath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'components')
        if os.path.exists(srcPath):
            for f in os.listdir(srcPath):
                name, ext = os.path.splitext(f)
                if name.startswith("__"):
                    continue
                elif ext == '.py':
                    yield name
    return [import_module('components.%s' % name) for name in findComponents()]

  def addComponent(self, moduleIndex):
    index = len(self.pages)
    self.window.listWidget_componentList.addItem(self.modules[moduleIndex].__doc__)
    self.selectedComponents.append(self.modules[moduleIndex].Component())
    self.pages.append(self.selectedComponents[-1].widget(self))
    self.window.listWidget_componentList.setCurrentRow(index)
    self.window.stackedWidget.addWidget(self.pages[-1])
    self.window.stackedWidget.setCurrentIndex(index)
    self.selectedComponents[-1].update()
    self.updateOpenPresetComboBox(self.selectedComponents[-1])

  def removeComponent(self):
    for selected in self.window.listWidget_componentList.selectedItems():
        index = self.window.listWidget_componentList.row(selected)
        self.window.stackedWidget.removeWidget(self.pages[index])
        self.window.listWidget_componentList.takeItem(index)
        self.selectedComponents.pop(index)
        self.pages.pop(index)
    self.drawPreview()

  def changeComponentWidget(self):
    selected = self.window.listWidget_componentList.selectedItems()
    index = self.window.listWidget_componentList.row(selected[0])
    self.window.stackedWidget.setCurrentIndex(index)
    self.updateOpenPresetComboBox(self.selectedComponents[index])

  def moveComponentUp(self):
    row = self.window.listWidget_componentList.currentRow()
    if row > 0:
      module = self.selectedComponents[row]
      self.selectedComponents.pop(row)
      self.selectedComponents.insert(row - 1,module)
      page = self.pages[row]
      self.pages.pop(row)
      self.pages.insert(row - 1, page)
      item = self.window.listWidget_componentList.takeItem(row)
      self.window.listWidget_componentList.insertItem(row - 1, item)
      widget = self.window.stackedWidget.removeWidget(page)
      self.window.stackedWidget.insertWidget(row - 1, page)
      self.window.listWidget_componentList.setCurrentRow(row - 1)
      self.window.stackedWidget.setCurrentIndex(row -1)

  def moveComponentDown(self):
    row = self.window.listWidget_componentList.currentRow()
    if row < len(self.pages) + 1:
      module = self.selectedComponents[row]
      self.selectedComponents.pop(row)
      self.selectedComponents.insert(row + 1,module)
      page = self.pages[row]
      self.pages.pop(row)
      self.pages.insert(row + 1, page)
      item = self.window.listWidget_componentList.takeItem(row)
      self.window.listWidget_componentList.insertItem(row + 1, item)
      widget = self.window.stackedWidget.removeWidget(page)
      self.window.stackedWidget.insertWidget(row + 1, page)
      self.window.listWidget_componentList.setCurrentRow(row + 1)
      self.window.stackedWidget.setCurrentIndex(row + 1)

  def updateOpenPresetComboBox(self, component):
    self.window.comboBox_openPreset.clear()
    self.window.comboBox_openPreset.addItem("Open Preset")
    destination = os.path.join(self.dataDir, 'presets',
        str(component).strip(), str(component.version()))
    if not os.path.exists(destination):
        os.makedirs(destination)
    for f in os.listdir(destination):
            self.window.comboBox_openPreset.addItem(f)

  def openSavePresetDialog(self):
    if self.window.listWidget_componentList.currentRow() == -1:
        return
    newName, OK = QtGui.QInputDialog.getText(QtGui.QWidget(), 'Audio Visualizer', 'New Preset Name:')
    if OK and newName:
        index = self.window.listWidget_componentList.currentRow()
        if index != -1:
            saveValueStore = self.selectedComponents[index].savePreset()
            componentName = str(self.selectedComponents[index]).strip()
            vers = self.selectedComponents[index].version()
            self.createPresetFile(componentName, vers, saveValueStore, newName)

  def createPresetFile(self, componentName, version, saveValueStore, filename):
    dirname = os.path.join(self.dataDir, 'presets', componentName, str(version))
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    with open(os.path.join(dirname, filename), 'w') as f:
        for itemset in saveValueStore.items():
            f.write('%s=%s' % itemset)
    self.window.comboBox_openPreset.addItem(filename)

  def openPreset(self, comboBoxIndex):
      pass


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


''' ####### commandline functionality broken until we decide how to implement it
if len(sys.argv) > 1:
  # command line mode
  app = QtGui.QApplication(sys.argv, False)
  command = Command()
  signal.signal(signal.SIGINT, command.cleanUp)
  sys.exit(app.exec_())
else:
'''
# gui mode
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    app.setApplicationName("audio-visualizer")
    app.setOrganizationName("audio-visualizer")
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
