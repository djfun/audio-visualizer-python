from os.path import expanduser
from queue import Queue
from collections import OrderedDict
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import QSettings, Qt
from PyQt4.QtGui import QMenu
import sys
import os
import signal
import filecmp
import time

import core
import preview_thread
import video_thread
from presetmanager import PresetManager
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

        self.pages = []  # widgets of component settings
        self.componentRows = []  # (moduleIndex, QListWidgetItem) tuples
        self.lastAutosave = time.time()

        # Create data directory, load/create settings
        self.dataDir = self.core.dataDir
        self.autosavePath = os.path.join(self.dataDir, 'autosave.avp')
        self.settings = QSettings(
            os.path.join(self.dataDir, 'settings.ini'), QSettings.IniFormat)
        LoadDefaultSettings(self)
        self.presetManager = PresetManager(
            uic.loadUi(
                os.path.join(os.path.dirname(os.path.realpath(__file__)),
                'presetmanager.ui')),
            self)
        if not os.path.exists(self.dataDir):
            os.makedirs(self.dataDir)
        for neededDirectory in (
          self.core.presetDir, self.settings.value("projectDir")):
            if not os.path.exists(neededDirectory):
                os.mkdir(neededDirectory)

        # Make queues/timers for the preview thread
        self.previewQueue = Queue()
        self.previewThread = QtCore.QThread(self)
        self.previewWorker = preview_thread.Worker(self, self.previewQueue)
        self.previewWorker.moveToThread(self.previewThread)
        self.previewWorker.imageCreated.connect(self.showPreviewImage)
        self.previewThread.start()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.processTask.emit)
        self.timer.start(500)

        # Begin decorating the window and connecting events
        componentList = self.window.listWidget_componentList

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
                #print(codec)

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

        # Make component buttons
        self.compMenu = QMenu()
        for i, comp in enumerate(self.core.modules):
            action = self.compMenu.addAction(comp.Component.__doc__)
            action.triggered[()].connect(
                lambda item=i: self.insertComponent(item))

        self.window.pushButton_addComponent.setMenu(self.compMenu)

        componentList.dropEvent = self.componentListChanged
        componentList.clicked.connect(
            lambda _: self.changeComponentWidget())

        self.window.pushButton_removeComponent.clicked.connect(
            lambda _: self.removeComponent())

        componentList.setContextMenuPolicy(
            QtCore.Qt.CustomContextMenu)
        componentList.connect(
            componentList,
            QtCore.SIGNAL("customContextMenuRequested(QPoint)"),
            self.componentContextMenu)

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
            lambda: self.moveComponent(-1)
        )
        self.window.pushButton_listMoveDown.clicked.connect(
            lambda: self.moveComponent(1)
        )

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

        # Show the window and load current project
        window.show()
        self.currentProject = self.settings.value("currentProject")
        if self.autosaveExists():
            # delete autosave if it's identical to the project
            os.remove(self.autosavePath)

        if self.currentProject and os.path.exists(self.autosavePath):
            ch = self.showMessage(
                msg="Restore unsaved changes in project '%s'?"
                % os.path.basename(self.currentProject)[:-4],
                showCancel=True)
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

    def updateComponentTitle(self, pos):
        if pos < 0:
            pos = len(self.core.selectedComponents)-1
        title = str(self.core.selectedComponents[pos])
        if self.core.selectedComponents[pos].currentPreset:
            title += ' - %s' % self.core.selectedComponents[pos].currentPreset
        self.window.listWidget_componentList.item(pos).setText(title)

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
        if not self.currentProject:
            if os.path.exists(self.autosavePath):
                os.remove(self.autosavePath)
        elif time.time() - self.lastAutosave >= 2.0:
            self.core.createProjectFile(self.autosavePath)
            self.lastAutosave = time.time()

    def autosaveExists(self):
        if self.currentProject and os.path.exists(self.autosavePath) \
            and filecmp.cmp(self.autosavePath, self.currentProject):
            return True
        else:
            return False

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
                self.core.selectedComponents)
        else:
            self.showMessage(
                msg="You must select an audio file and output filename.")

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
            self.window.pushButton_presets.setEnabled(False)
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
            self.window.pushButton_presets.setEnabled(True)
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
        self.newTask.emit(self.core.selectedComponents)
        # self.processTask.emit()
        self.autosave()

    def showPreviewImage(self, image):
        self.previewWindow.changePixmap(image)

    def insertComponent(self, moduleIndex, compPos=0):
        componentList = self.window.listWidget_componentList
        stackedWidget = self.window.stackedWidget
        if compPos < 0:
            compPos = componentList.count()

        index = self.core.insertComponent(
            compPos, moduleIndex)
        row = componentList.insertItem(
            index,
            self.core.selectedComponents[index].__doc__)
        self.componentRows.insert(compPos, (moduleIndex, row))
        componentList.setCurrentRow(index)

        self.pages.insert(index, self.core.selectedComponents[index].widget(self))
        stackedWidget.insertWidget(index, self.pages[index])
        stackedWidget.setCurrentIndex(index)

        self.core.updateComponent(index)

    def removeComponent(self):
        componentList = self.window.listWidget_componentList

        for selected in componentList.selectedItems():
            index = componentList.row(selected)
            self.window.stackedWidget.removeWidget(self.pages[index])
            componentList.takeItem(index)
            self.componentRows.pop(index)
            self.core.selectedComponents.pop(index)
            self.pages.pop(index)
            self.changeComponentWidget()
        self.drawPreview()

    def moveComponent(self, change):
        '''Moves a component relatively from its current position'''
        componentList = self.window.listWidget_componentList
        stackedWidget = self.window.stackedWidget

        row = componentList.currentRow()
        newRow = row + change
        if newRow > -1 and newRow < componentList.count():
            self.core.moveComponent(row, newRow)

            # update widgets
            page = self.pages.pop(row)
            self.pages.insert(newRow, page)
            item = componentList.takeItem(row)
            newItem = componentList.insertItem(newRow, item)
            widget = stackedWidget.removeWidget(page)
            stackedWidget.insertWidget(newRow, page)
            componentList.setCurrentRow(newRow)
            stackedWidget.setCurrentIndex(newRow)
            self.componentRows.pop(row)
            self.componentRows.insert(newRow, (self.core.moduleIndexFor(row), newItem))
            self.drawPreview()

    def componentListChanged(self, *args):
        '''Update all our tracking variables to match the widget'''
        pass

    def changeComponentWidget(self):
        selected = self.window.listWidget_componentList.selectedItems()
        if selected:
            index = self.window.listWidget_componentList.row(selected[0])
            self.window.stackedWidget.setCurrentIndex(index)

    def openPresetManager(self):
        '''Preset manager for importing, exporting, renaming, deleting'''
        self.presetManager.show()

    def clear(self):
        '''Get a blank slate'''
        self.core.selectedComponents = []
        self.window.listWidget_componentList.clear()
        for widget in self.pages:
            self.window.stackedWidget.removeWidget(widget)
        self.pages = []

    def createNewProject(self):
        if self.autosaveExists():
            ch = self.showMessage(
                msg="You have unsaved changes in project '%s'. "
                "Save before starting a new project?"
                % os.path.basename(self.currentProject)[:-4],
                showCancel=True)
            if ch:
                self.saveCurrentProject()

        self.clear()
        self.currentProject = None
        self.settings.setValue("currentProject", None)
        self.drawPreview()

    def saveCurrentProject(self):
        if self.currentProject:
            self.core.createProjectFile(self.currentProject)
        else:
            self.openSaveProjectDialog()

    def openSaveProjectDialog(self):
        filename = QtGui.QFileDialog.getSaveFileName(
            self.window, "Create Project File",
            self.settings.value("projectDir"),
            "Project Files (*.avp)")
        if not filename:
            return
        self.settings.setValue("projectDir", os.path.dirname(filename))
        self.settings.setValue("currentProject", filename)
        self.currentProject = filename

        self.core.createProjectFile(filename)

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
        compNames = [mod.Component.__doc__ for mod in self.core.modules]
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
                            self.insertComponent(compIndex, -1)
                            i += 1
                        elif i == 1:
                            # version, not used yet
                            i += 1
                        elif i == 2:
                            saveValueStore = dict(eval(line))
                            self.core.selectedComponents[-1].loadPreset(
                                saveValueStore)
                            self.updateComponentTitle(-1)
                            i = 0
        except (IndexError, ValueError, NameError, SyntaxError,
            AttributeError, TypeError) as e:
            self.createNewProject()
            typ, value, _ = sys.exc_info()
            msg = '%s: %s' % (typ.__name__, value)
            self.showMessage(
                msg="Project file '%s' is corrupted." % filepath,
                showCancel=False,
                icon=QtGui.QMessageBox.Warning,
                detail=msg)
        except KeyError as e:
            # probably just an old version, still loadable
            print('project file missing value: %s' % e)

    def showMessage(self, **kwargs):
        parent = kwargs['parent'] if 'parent' in kwargs else self.window
        msg = QtGui.QMessageBox(parent)
        msg.setModal(True)
        msg.setText(kwargs['msg'])
        msg.setIcon(
            kwargs['icon'] if 'icon' in kwargs else QtGui.QMessageBox.Information)
        msg.setDetailedText(kwargs['detail'] if 'detail' in kwargs else None)
        if 'showCancel'in kwargs and kwargs['showCancel']:
            msg.setStandardButtons(
                QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
        else:
            msg.setStandardButtons(QtGui.QMessageBox.Ok)
        ch = msg.exec_()
        if ch == 1024:
            return True
        return False

    def componentContextMenu(self, QPos):
        '''Appears when right-clicking a component in the list'''
        if not self.window.listWidget_componentList.selectedItems():
            return

        self.presetManager.findPresets()
        self.menu = QtGui.QMenu()
        menuItem = self.menu.addAction("Save Preset")
        self.connect(
            menuItem,
            QtCore.SIGNAL("triggered()"),
            self.presetManager.openSavePresetDialog
        )

        # submenu for opening presets
        index = self.window.listWidget_componentList.currentRow()
        try:
            presets = self.presetManager.presets[str(self.core.selectedComponents[index])]
            self.submenu = QtGui.QMenu("Open Preset")
            self.menu.addMenu(self.submenu)

            for version, presetName in presets:
                menuItem = self.submenu.addAction(presetName)
                self.connect(
                    menuItem,
                    QtCore.SIGNAL("triggered()"),
                    lambda presetName=presetName:
                        self.presetManager.openPreset(presetName)
                )
        except KeyError as e:
            print(e)
        parentPosition = self.window.listWidget_componentList.mapToGlobal(QtCore.QPoint(0, 0))
        self.menu.move(parentPosition + QPos)
        self.menu.show()
