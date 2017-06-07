from os.path import expanduser
from queue import Queue
from importlib import import_module
from collections import OrderedDict
from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QSettings, Qt
from PyQt4.QtGui import QDesktopServices, QMenu
import sys
import io
import os
import string
import signal
import filecmp
import time

import core
import preview_thread
import video_thread
from main import LoadDefaultSettings


class PreviewWindow(QtGui.QLabel):
    def __init__(self, parent, img):
        super(PreviewWindow, self).__init__()
        self.parent = parent
        self.setFrameStyle(QtGui.QFrame.StyledPanel)
        self.pixmap = QtGui.QPixmap(img)

    def paintEvent(self, event):
        size = self.size()
        painter = QtGui.QPainter(self)
        point = QtCore.QPoint(0, 0)
        scaledPix = self.pixmap.scaled(
            size, Qt.KeepAspectRatio, transformMode=Qt.SmoothTransformation)

        # start painting the label from left upper corner
        point.setX((size.width() - scaledPix.width())/2)
        point.setY((size.height() - scaledPix.height())/2)
        painter.drawPixmap(point, scaledPix)

    def changePixmap(self, img):
        self.pixmap = QtGui.QPixmap(img)
        self.repaint()


class MainWindow(QtCore.QObject):

    newTask = QtCore.pyqtSignal(list)
    processTask = QtCore.pyqtSignal()
    videoTask = QtCore.pyqtSignal(str, str, list)

    def __init__(self, window):
        QtCore.QObject.__init__(self)

        # print('main thread id: {}'.format(QtCore.QThread.currentThreadId()))
        self.window = window
        self.core = core.Core()
        self.pages = []
        self.selectedComponents = []
        self.lastAutosave = time.time()

        # create data directory, load/create settings
        self.dataDir = QDesktopServices.storageLocation(
            QDesktopServices.DataLocation)
        self.autosavePath = os.path.join(self.dataDir, 'autosave.avp')
        self.presetDir = os.path.join(self.dataDir, 'presets')
        self.settings = QSettings(
            os.path.join(self.dataDir, 'settings.ini'), QSettings.IniFormat)
        LoadDefaultSettings(self)
        if not os.path.exists(self.dataDir):
            os.makedirs(self.dataDir)
        for neededDirectory in (
          self.presetDir, self.settings.value("projectDir")):
            if not os.path.exists(neededDirectory):
                os.mkdir(neededDirectory)

        #
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
        window.toolButton_selectAudioFile.clicked.connect(
            self.openInputFileDialog)

        window.toolButton_selectOutputFile.clicked.connect(
            self.openOutputFileDialog)

        window.progressBar_createVideo.setValue(0)

        window.pushButton_createVideo.clicked.connect(
            self.createAudioVisualisation)

        window.pushButton_Cancel.clicked.connect(self.stopVideo)
        window.setWindowTitle("Audio Visualizer")

        for i, container in enumerate(self.core.encoder_options['containers']):
            window.comboBox_videoContainer.addItem(container['name'])
            if container['name'] == self.settings.value('outputContainer'):
                selectedContainer = i

        window.comboBox_videoContainer.setCurrentIndex(selectedContainer)
        window.comboBox_videoContainer.currentIndexChanged.connect(
            self.updateCodecs
        )

        self.updateCodecs()

        for i in range(window.comboBox_videoCodec.count()):
            codec = window.comboBox_videoCodec.itemText(i)
            if codec == self.settings.value('outputVideoCodec'):
                window.comboBox_videoCodec.setCurrentIndex(i)
                print(codec)

        for i in range(window.comboBox_audioCodec.count()):
            codec = window.comboBox_audioCodec.itemText(i)
            if codec == self.settings.value('outputAudioCodec'):
                window.comboBox_audioCodec.setCurrentIndex(i)

        window.comboBox_videoCodec.currentIndexChanged.connect(
            self.updateCodecSettings
        )

        window.comboBox_audioCodec.currentIndexChanged.connect(
            self.updateCodecSettings
        )

        vBitrate = int(self.settings.value('outputVideoBitrate'))
        aBitrate = int(self.settings.value('outputAudioBitrate'))

        window.spinBox_vBitrate.setValue(vBitrate)
        window.spinBox_aBitrate.setValue(aBitrate)

        window.spinBox_vBitrate.valueChanged.connect(self.updateCodecSettings)
        window.spinBox_aBitrate.valueChanged.connect(self.updateCodecSettings)

        self.previewWindow = PreviewWindow(self, os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "background.png"))
        window.verticalLayout_previewWrapper.addWidget(self.previewWindow)

        self.modules = self.findComponents()
        self.compMenu = QMenu()
        for i, comp in enumerate(self.modules):
            action = self.compMenu.addAction(comp.Component.__doc__)
            action.triggered[()].connect(
                lambda item=i: self.insertComponent(item))

        self.window.pushButton_addComponent.setMenu(self.compMenu)
        window.listWidget_componentList.clicked.connect(
            lambda _: self.changeComponentWidget())

        self.window.pushButton_removeComponent.clicked.connect(
            lambda _: self.removeComponent())

        currentRes = str(self.settings.value('outputWidth'))+'x' + \
            str(self.settings.value('outputHeight'))
        for i, res in enumerate(self.resolutions):
            window.comboBox_resolution.addItem(res)
            if res == currentRes:
                currentRes = i
                window.comboBox_resolution.setCurrentIndex(currentRes)
                window.comboBox_resolution.currentIndexChanged.connect(
                    self.updateResolution)

        self.window.pushButton_listMoveUp.clicked.connect(
            self.moveComponentUp)
        self.window.pushButton_listMoveDown.clicked.connect(
            self.moveComponentDown)

        '''self.window.pushButton_savePreset.clicked.connect(
            self.openSavePresetDialog)
        self.window.comboBox_openPreset.currentIndexChanged.connect(
            self.openPreset)'''

        # Configure the Projects Menu
        self.projectMenu = QMenu()
        action = self.projectMenu.addAction("New Project")
        action.triggered[()].connect(self.createNewProject)

        action = self.projectMenu.addAction("Open Project")
        action.triggered[()].connect(self.openOpenProjectDialog)

        action = self.projectMenu.addAction("Save Project")
        action.triggered[()].connect(self.saveCurrentProject)

        action = self.projectMenu.addAction("Save Project As")
        action.triggered[()].connect(self.openSaveProjectDialog)

        self.window.pushButton_projects.setMenu(self.projectMenu)

        # Configure the Presets Button
        self.window.pushButton_presets.clicked.connect(
            self.openPresetManager
        )

        '''self.window.pushButton_saveAs.clicked.connect(
            self.openSaveProjectDialog)
        self.window.pushButton_saveProject.clicked.connect(
            self.saveCurrentProject)
        self.window.pushButton_openProject.clicked.connect(
            self.openOpenProjectDialog)'''

        # show the window and load current project
        window.show()
        self.currentProject = self.settings.value("currentProject")
        if self.currentProject and os.path.exists(self.autosavePath) \
                and filecmp.cmp(self.autosavePath, self.currentProject):
            # delete autosave if it's identical to the project
            os.remove(self.autosavePath)

        if self.currentProject and os.path.exists(self.autosavePath):
            ch = self.showMessage(
                "Restore unsaved changes in project '%s'?"
                % os.path.basename(self.currentProject)[:-4], True)
            if ch:
                os.remove(self.currentProject)
                os.rename(self.autosavePath, self.currentProject)
            else:
                os.remove(self.autosavePath)

        self.openProject(self.currentProject)
        self.drawPreview()

    def cleanUp(self):
        self.timer.stop()
        self.previewThread.quit()
        self.previewThread.wait()
        self.autosave()

    def updateCodecs(self):
        containerWidget = self.window.comboBox_videoContainer
        vCodecWidget = self.window.comboBox_videoCodec
        aCodecWidget = self.window.comboBox_audioCodec
        index = containerWidget.currentIndex()
        name = containerWidget.itemText(index)
        self.settings.setValue('outputContainer', name)

        vCodecWidget.clear()
        aCodecWidget.clear()

        for container in self.core.encoder_options['containers']:
            if container['name'] == name:
                for vCodec in container['video-codecs']:
                    vCodecWidget.addItem(vCodec)
                for aCodec in container['audio-codecs']:
                    aCodecWidget.addItem(aCodec)

    def updateCodecSettings(self):
        vCodecWidget = self.window.comboBox_videoCodec
        vBitrateWidget = self.window.spinBox_vBitrate
        aBitrateWidget = self.window.spinBox_aBitrate
        aCodecWidget = self.window.comboBox_audioCodec
        currentVideoCodec = vCodecWidget.currentIndex()
        currentVideoCodec = vCodecWidget.itemText(currentVideoCodec)
        currentVideoBitrate = vBitrateWidget.value()
        currentAudioCodec = aCodecWidget.currentIndex()
        currentAudioCodec = aCodecWidget.itemText(currentAudioCodec)
        currentAudioBitrate = aBitrateWidget.value()
        self.settings.setValue('outputVideoCodec', currentVideoCodec)
        self.settings.setValue('outputAudioCodec', currentAudioCodec)
        self.settings.setValue('outputVideoBitrate', currentVideoBitrate)
        self.settings.setValue('outputAudioBitrate', currentAudioBitrate)

    def autosave(self):
        if time.time() - self.lastAutosave >= 1.0:
            if os.path.exists(self.autosavePath):
                os.remove(self.autosavePath)
            self.createProjectFile(self.autosavePath)
            self.lastAutosave = time.time()

    def openInputFileDialog(self):
        inputDir = self.settings.value("inputDir", expanduser("~"))

        fileName = QtGui.QFileDialog.getOpenFileName(
            self.window, "Open Music File",
            inputDir, "Music Files (*.mp3 *.wav *.ogg *.fla *.aac)")

        if not fileName == "":
            self.settings.setValue("inputDir", os.path.dirname(fileName))
            self.window.lineEdit_audioFile.setText(fileName)

    def openOutputFileDialog(self):
        outputDir = self.settings.value("outputDir", expanduser("~"))

        fileName = QtGui.QFileDialog.getSaveFileName(
            self.window, "Set Output Video File",
            outputDir, "Video Files (*.mp4 *.mov *.mkv *.avi *.webm *.flv)")

        if not fileName == "":
            self.settings.setValue("outputDir", os.path.dirname(fileName))
            self.window.lineEdit_outputFile.setText(fileName)

    def stopVideo(self):
        print('stop')
        self.videoWorker.cancel()
        self.canceled = True

    def createAudioVisualisation(self):
        # create output video if mandatory settings are filled in
        if self.window.lineEdit_audioFile.text() and \
          self.window.lineEdit_outputFile.text():
            self.canceled = False
            self.progressBarUpdated(-1)
            ffmpeg_cmd = self.settings.value("ffmpeg_cmd", expanduser("~"))
            self.videoThread = QtCore.QThread(self)
            self.videoWorker = video_thread.Worker(self)
            self.videoWorker.moveToThread(self.videoThread)
            self.videoWorker.videoCreated.connect(self.videoCreated)
            self.videoWorker.progressBarUpdate.connect(self.progressBarUpdated)
            self.videoWorker.progressBarSetText.connect(
                self.progressBarSetText)
            self.videoWorker.imageCreated.connect(self.showPreviewImage)
            self.videoWorker.encoding.connect(self.changeEncodingStatus)
            self.videoThread.start()
            self.videoTask.emit(
                self.window.lineEdit_audioFile.text(),
                self.window.lineEdit_outputFile.text(),
                self.selectedComponents)
        else:
            self.showMessage(
                "You must select an audio file and output filename.")

    def progressBarUpdated(self, value):
        self.window.progressBar_createVideo.setValue(value)

    def changeEncodingStatus(self, status):
        if status:
            self.window.pushButton_createVideo.setEnabled(False)
            self.window.pushButton_Cancel.setEnabled(True)
            self.window.comboBox_resolution.setEnabled(False)
            self.window.stackedWidget.setEnabled(False)
            self.window.tab_encoderSettings.setEnabled(False)
            self.window.label_audioFile.setEnabled(False)
            self.window.toolButton_selectAudioFile.setEnabled(False)
            self.window.label_outputFile.setEnabled(False)
            self.window.toolButton_selectOutputFile.setEnabled(False)
            self.window.lineEdit_audioFile.setEnabled(False)
            self.window.lineEdit_outputFile.setEnabled(False)
            self.window.pushButton_addComponent.setEnabled(False)
            self.window.pushButton_removeComponent.setEnabled(False)
            self.window.pushButton_listMoveDown.setEnabled(False)
            self.window.pushButton_listMoveUp.setEnabled(False)
            self.window.comboBox_Presets.setEnabled(False)
            '''self.window.pushButton_openProject.setEnabled(False)'''
            self.window.listWidget_componentList.setEnabled(False)
        else:
            self.window.pushButton_createVideo.setEnabled(True)
            self.window.pushButton_Cancel.setEnabled(False)
            self.window.comboBox_resolution.setEnabled(True)
            self.window.stackedWidget.setEnabled(True)
            self.window.tab_encoderSettings.setEnabled(True)
            self.window.label_audioFile.setEnabled(True)
            self.window.toolButton_selectAudioFile.setEnabled(True)
            self.window.lineEdit_audioFile.setEnabled(True)
            self.window.label_outputFile.setEnabled(True)
            self.window.toolButton_selectOutputFile.setEnabled(True)
            self.window.lineEdit_outputFile.setEnabled(True)
            self.window.pushButton_addComponent.setEnabled(True)
            self.window.pushButton_removeComponent.setEnabled(True)
            self.window.pushButton_listMoveDown.setEnabled(True)
            self.window.pushButton_listMoveUp.setEnabled(True)
            self.window.comboBox_Presets.setEnabled(True)
            '''self.window.pushButton_openProject.setEnabled(True)'''
            self.window.listWidget_componentList.setEnabled(True)

    def progressBarSetText(self, value):
        self.window.progressBar_createVideo.setFormat(value)

    def videoCreated(self):
        self.videoThread.quit()
        self.videoThread.wait()

    def updateResolution(self):
        resIndex = int(self.window.comboBox_resolution.currentIndex())
        res = self.resolutions[resIndex].split('x')
        self.settings.setValue('outputWidth', res[0])
        self.settings.setValue('outputHeight', res[1])
        self.drawPreview()

    def drawPreview(self):
        self.newTask.emit(self.selectedComponents)
        # self.processTask.emit()
        self.autosave()

    def showPreviewImage(self, image):
        self.previewWindow.changePixmap(image)

    def findComponents(self):
        def findComponents():
            srcPath = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'components')
            if os.path.exists(srcPath):
                for f in sorted(os.listdir(srcPath)):
                    name, ext = os.path.splitext(f)
                    if name.startswith("__"):
                        continue
                    elif ext == '.py':
                        yield name
        return [
            import_module('components.%s' % name)
            for name in findComponents()]

    def addComponent(self, moduleIndex):
        index = len(self.pages)
        self.selectedComponents.append(self.modules[moduleIndex].Component())
        self.window.listWidget_componentList.addItem(
            self.selectedComponents[-1].__doc__)
        self.pages.append(self.selectedComponents[-1].widget(self))
        self.window.listWidget_componentList.setCurrentRow(index)
        self.window.stackedWidget.addWidget(self.pages[-1])
        self.window.stackedWidget.setCurrentIndex(index)
        self.selectedComponents[-1].update()
        '''self.updateOpenPresetComboBox(self.selectedComponents[-1])'''

    def insertComponent(self, moduleIndex):
        self.selectedComponents.insert(
            0, self.modules[moduleIndex].Component())
        self.window.listWidget_componentList.insertItem(
            0, self.selectedComponents[0].__doc__)
        self.pages.insert(0, self.selectedComponents[0].widget(self))
        self.window.listWidget_componentList.setCurrentRow(0)
        self.window.stackedWidget.insertWidget(0, self.pages[0])
        self.window.stackedWidget.setCurrentIndex(0)
        self.selectedComponents[0].update()
        '''self.updateOpenPresetComboBox(self.selectedComponents[0])'''

    def removeComponent(self):
        for selected in self.window.listWidget_componentList.selectedItems():
            index = self.window.listWidget_componentList.row(selected)
            self.window.stackedWidget.removeWidget(self.pages[index])
            self.window.listWidget_componentList.takeItem(index)
            self.selectedComponents.pop(index)
            self.pages.pop(index)
            self.changeComponentWidget()
        self.drawPreview()

    def changeComponentWidget(self):
        selected = self.window.listWidget_componentList.selectedItems()
        if selected:
            index = self.window.listWidget_componentList.row(selected[0])
            self.window.stackedWidget.setCurrentIndex(index)
            '''self.updateOpenPresetComboBox(self.selectedComponents[index])'''

    def moveComponentUp(self):
        row = self.window.listWidget_componentList.currentRow()
        if row > 0:
            module = self.selectedComponents[row]
            self.selectedComponents.pop(row)
            self.selectedComponents.insert(row - 1, module)
            page = self.pages[row]
            self.pages.pop(row)
            self.pages.insert(row - 1, page)
            item = self.window.listWidget_componentList.takeItem(row)
            self.window.listWidget_componentList.insertItem(row - 1, item)
            widget = self.window.stackedWidget.removeWidget(page)
            self.window.stackedWidget.insertWidget(row - 1, page)
            self.window.listWidget_componentList.setCurrentRow(row - 1)
            self.window.stackedWidget.setCurrentIndex(row - 1)
            self.drawPreview()

    def moveComponentDown(self):
        row = self.window.listWidget_componentList.currentRow()
        if row != -1 and row < len(self.pages)+1:
            module = self.selectedComponents[row]
            self.selectedComponents.pop(row)
            self.selectedComponents.insert(row + 1, module)
            page = self.pages[row]
            self.pages.pop(row)
            self.pages.insert(row + 1, page)
            item = self.window.listWidget_componentList.takeItem(row)
            self.window.listWidget_componentList.insertItem(row + 1, item)
            widget = self.window.stackedWidget.removeWidget(page)
            self.window.stackedWidget.insertWidget(row + 1, page)
            self.window.listWidget_componentList.setCurrentRow(row + 1)
            self.window.stackedWidget.setCurrentIndex(row + 1)
            self.drawPreview()

    # Preset manager for importing, exporting, renaming,
    # and deleting presets.
    def openPresetManager(self):
        return

    def updateOpenPresetComboBox(self, component):
        self.window.comboBox_openPreset.clear()
        self.window.comboBox_openPreset.addItem("Component Presets")
        destination = os.path.join(
            self.presetDir, str(component).strip(), str(component.version()))
        if not os.path.exists(destination):
            os.makedirs(destination)
        for f in os.listdir(destination):
            self.window.comboBox_openPreset.addItem(f)

    def openSavePresetDialog(self):
        if self.window.listWidget_componentList.currentRow() == -1:
            return
        while True:
            newName, OK = QtGui.QInputDialog.getText(
                QtGui.QWidget(), 'Audio Visualizer', 'New Preset Name:')
            badName = False
            for letter in newName:
                if letter in string.punctuation:
                    badName = True
            if badName:
                # some filesystems don't like bizarre characters
                self.showMessage("Preset names must contain only letters, \
                    numbers, and spaces.")
                continue
            if OK and newName:
                index = self.window.listWidget_componentList.currentRow()
                if index != -1:
                    saveValueStore = \
                        self.selectedComponents[index].savePreset()
                    componentName = str(self.selectedComponents[index]).strip()
                    vers = self.selectedComponents[index].version()
                    self.createPresetFile(
                        componentName, vers, saveValueStore, newName)
            break

    def createPresetFile(
      self, componentName, version, saveValueStore, filename):
        dirname = os.path.join(self.presetDir, componentName, str(version))
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        filepath = os.path.join(dirname, filename)
        if os.path.exists(filepath):
            ch = self.showMessage(
                "%s already exists! Overwrite it?" % filename,
                True, QtGui.QMessageBox.Warning)
            if not ch:
                return
            # remove old copies of the preset
            for i in range(0, self.window.comboBox_openPreset.count()):
                if self.window.comboBox_openPreset.itemText(i) == filename:
                    self.window.comboBox_openPreset.removeItem(i)
        with open(filepath, 'w') as f:
            f.write(core.Core.stringOrderedDict(saveValueStore))
        self.window.comboBox_openPreset.addItem(filename)
        self.window.comboBox_openPreset.setCurrentIndex(
            self.window.comboBox_openPreset.count()-1)

    def openPreset(self):
        if self.window.comboBox_openPreset.currentIndex() < 1:
            return
        index = self.window.listWidget_componentList.currentRow()
        if index == -1:
            return
        filename = self.window.comboBox_openPreset.itemText(
            self.window.comboBox_openPreset.currentIndex())
        componentName = str(self.selectedComponents[index]).strip()
        version = self.selectedComponents[index].version()
        dirname = os.path.join(self.presetDir, componentName, str(version))
        filepath = os.path.join(dirname, filename)
        if not os.path.exists(filepath):
            self.window.comboBox_openPreset.removeItem(
                self.window.comboBox_openPreset.currentIndex())
            return
        with open(filepath, 'r') as f:
            for line in f:
                saveValueStore = dict(eval(line.strip()))
                break
        self.selectedComponents[index].loadPreset(saveValueStore)
        self.drawPreview()

    def createNewProject(self):
        return

    def saveCurrentProject(self):
        if self.currentProject:
            self.createProjectFile(self.currentProject)
        else:
            self.openSaveProjectDialog()

    def openSaveProjectDialog(self):
        filename = QtGui.QFileDialog.getSaveFileName(
            self.window, "Create Project File",
            self.settings.value("projectDir"),
            "Project Files (*.avp)")
        if not filename:
            return
        self.createProjectFile(filename)

    def createProjectFile(self, filepath):
        if not filepath.endswith(".avp"):
            filepath += '.avp'
        with open(filepath, 'w') as f:
            print('creating %s' % filepath)
            f.write('[Components]\n')
            for comp in self.selectedComponents:
                saveValueStore = comp.savePreset()
                f.write('%s\n' % str(comp))
                f.write('%s\n' % str(comp.version()))
                f.write('%s\n' % core.Core.stringOrderedDict(saveValueStore))
        if filepath != self.autosavePath:
            self.settings.setValue("projectDir", os.path.dirname(filepath))
            self.settings.setValue("currentProject", filepath)
            self.currentProject = filepath

    def openOpenProjectDialog(self):
        filename = QtGui.QFileDialog.getOpenFileName(
            self.window, "Open Project File",
            self.settings.value("projectDir"),
            "Project Files (*.avp)")
        self.openProject(filename)

    def openProject(self, filepath):
        if not filepath or not os.path.exists(filepath) \
          or not filepath.endswith('.avp'):
            return
        self.clear()
        self.currentProject = filepath
        self.settings.setValue("currentProject", filepath)
        self.settings.setValue("projectDir", os.path.dirname(filepath))
        compNames = [mod.Component.__doc__ for mod in self.modules]
        try:
            with open(filepath, 'r') as f:
                validSections = ('Components')
                section = ''

                def parseLine(line):
                    line = line.strip()
                    newSection = ''

                    if line.startswith('[') and line.endswith(']') \
                            and line[1:-1] in validSections:
                        newSection = line[1:-1]

                    return line, newSection

                i = 0
                for line in f:
                    line, newSection = parseLine(line)
                    if newSection:
                        section = str(newSection)
                        continue
                    if line and section == 'Components':
                        if i == 0:
                            compIndex = compNames.index(line)
                            self.addComponent(compIndex)
                            i += 1
                        elif i == 1:
                            # version, not used yet
                            i += 1
                        elif i == 2:
                            saveValueStore = dict(eval(line))
                            self.selectedComponents[-1].loadPreset(
                                saveValueStore)
                            i = 0
        except (IndexError, ValueError, KeyError, NameError,
                SyntaxError, AttributeError, TypeError) as e:
            self.clear()
            typ, value, _ = sys.exc_info()
            msg = '%s: %s' % (typ.__name__, value)
            self.showMessage(
                "Project file '%s' is corrupted." % filepath, False,
                QtGui.QMessageBox.Warning, msg)

    def showMessage(
            self, string, showCancel=False,
            icon=QtGui.QMessageBox.Information, detail=None):
        msg = QtGui.QMessageBox()
        msg.setIcon(icon)
        msg.setText(string)
        msg.setDetailedText(detail)
        if showCancel:
            msg.setStandardButtons(
                QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
        else:
            msg.setStandardButtons(QtGui.QMessageBox.Ok)
        ch = msg.exec_()
        if ch == 1024:
            return True
        return False

    def clear(self):
        ''' empty out all components and fields, get a blank slate '''
        self.selectedComponents = []
        self.window.listWidget_componentList.clear()
        for widget in self.pages:
            self.window.stackedWidget.removeWidget(widget)
        self.pages = []
