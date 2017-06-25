from queue import Queue
from PyQt5 import QtCore, QtGui, uic, QtWidgets
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import QMenu, QShortcut
import sys
import os
import signal
import filecmp
import time

import core
import preview_thread
import video_thread
from presetmanager import PresetManager
from main import LoadDefaultSettings, disableWhenEncoding


class PreviewWindow(QtWidgets.QLabel):
    def __init__(self, parent, img):
        super(PreviewWindow, self).__init__()
        self.parent = parent
        self.setFrameStyle(QtWidgets.QFrame.StyledPanel)
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


class MainWindow(QtWidgets.QMainWindow):

    newTask = QtCore.pyqtSignal(list)
    processTask = QtCore.pyqtSignal()
    videoTask = QtCore.pyqtSignal(str, str, list)

    def __init__(self, window, project):
        QtWidgets.QMainWindow.__init__(self)

        # print('main thread id: {}'.format(QtCore.QThread.currentThreadId()))
        self.window = window
        self.core = core.Core()

        self.pages = []  # widgets of component settings
        self.lastAutosave = time.time()
        self.encoding = False

        # Create data directory, load/create settings
        self.dataDir = self.core.dataDir
        self.autosavePath = os.path.join(self.dataDir, 'autosave.avp')
        self.settings = QSettings(
            os.path.join(self.dataDir, 'settings.ini'), QSettings.IniFormat)
        LoadDefaultSettings(self)
        self.presetManager = PresetManager(
            uic.loadUi(
                os.path.join(self.core.wd, 'presetmanager.ui')), self)

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
            self.core.wd, "background.png"))
        window.verticalLayout_previewWrapper.addWidget(self.previewWindow)

        # Make component buttons
        self.compMenu = QMenu()
        self.compActions = []
        for i, comp in enumerate(self.core.modules):
            action = self.compMenu.addAction(comp.Component.__doc__)
            action.triggered.connect(
                lambda _, item=i: self.core.insertComponent(0, item, self)
            )

        self.window.pushButton_addComponent.setMenu(self.compMenu)

        componentList.dropEvent = self.dragComponent
        componentList.itemSelectionChanged.connect(
            self.changeComponentWidget
        )
        self.window.pushButton_removeComponent.clicked.connect(
            lambda: self.removeComponent()
        )

        componentList.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        componentList.customContextMenuRequested.connect(
            self.componentContextMenu
        )

        currentRes = str(self.settings.value('outputWidth'))+'x' + \
            str(self.settings.value('outputHeight'))
        for i, res in enumerate(self.resolutions):
            window.comboBox_resolution.addItem(res)
            if res == currentRes:
                currentRes = i
                window.comboBox_resolution.setCurrentIndex(currentRes)
                window.comboBox_resolution.currentIndexChanged.connect(
                    self.updateResolution
                )

        self.window.pushButton_listMoveUp.clicked.connect(
            lambda: self.moveComponent(-1)
        )
        self.window.pushButton_listMoveDown.clicked.connect(
            lambda: self.moveComponent(1)
        )

        # Configure the Projects Menu
        self.projectMenu = QMenu()
        self.window.menuButton_newProject = self.projectMenu.addAction(
            "New Project"
        )
        self.window.menuButton_newProject.triggered.connect(
            lambda: self.createNewProject()
        )
        self.window.menuButton_openProject = self.projectMenu.addAction(
            "Open Project"
        )
        self.window.menuButton_openProject.triggered.connect(
            lambda: self.openOpenProjectDialog()
        )

        action = self.projectMenu.addAction("Save Project")
        action.triggered.connect(self.saveCurrentProject)

        action = self.projectMenu.addAction("Save Project As")
        action.triggered.connect(self.openSaveProjectDialog)

        self.window.pushButton_projects.setMenu(self.projectMenu)

        # Configure the Presets Button
        self.window.pushButton_presets.clicked.connect(
            self.openPresetManager
        )

        self.updateWindowTitle()
        window.show()

        if project and project != self.autosavePath:
            if not project.endswith('.avp'):
                project += '.avp'
            # open a project from the commandline
            if not os.path.dirname(project):
                project = os.path.join(os.path.expanduser('~'), project)
            self.currentProject = project
            self.settings.setValue("currentProject", project)
            if os.path.exists(self.autosavePath):
                os.remove(self.autosavePath)
        else:
            # open the last currentProject from settings
            self.currentProject = self.settings.value("currentProject")

            # delete autosave if it's identical to this project
            if self.autosaveExists(identical=True):
                os.remove(self.autosavePath)

            if self.currentProject and os.path.exists(self.autosavePath):
                ch = self.showMessage(
                    msg="Restore unsaved changes in project '%s'?"
                    % os.path.basename(self.currentProject)[:-4],
                    showCancel=True)
                if ch:
                    self.saveProjectChanges()
                else:
                    os.remove(self.autosavePath)

        self.openProject(self.currentProject, prompt=False)
        self.drawPreview(True)

        # Setup Hotkeys
        QtWidgets.QShortcut("Ctrl+S", self.window, self.saveCurrentProject)
        QtWidgets.QShortcut("Ctrl+A", self.window, self.openSaveProjectDialog)
        QtWidgets.QShortcut("Ctrl+O", self.window, self.openOpenProjectDialog)
        QtWidgets.QShortcut("Ctrl+N", self.window, self.createNewProject)

        QtWidgets.QShortcut(
            "Ctrl+T", self.window,
            activated=lambda: self.window.pushButton_addComponent.click()
        )
        QtWidgets.QShortcut(
            "Ctrl+Space", self.window,
            activated=lambda: self.window.listWidget_componentList.setFocus()
        )
        QtWidgets.QShortcut(
            "Ctrl+Shift+S", self.window,
            self.presetManager.openSavePresetDialog
        )
        QtWidgets.QShortcut(
            "Ctrl+Shift+C", self.window, self.presetManager.clearPreset
        )

        QtWidgets.QShortcut(
            "Ctrl+Up", self.window,
            activated=lambda: self.moveComponent(-1)
        )
        QtWidgets.QShortcut(
            "Ctrl+Down", self.window,
            activated=lambda: self.moveComponent(1)
        )
        QtWidgets.QShortcut("Ctrl+Home", self.window, self.moveComponentTop)
        QtWidgets.QShortcut("Ctrl+End", self.window, self.moveComponentBottom)
        QtWidgets.QShortcut("Ctrl+r", self.window, self.removeComponent)

    def cleanUp(self):
        self.timer.stop()
        self.previewThread.quit()
        self.previewThread.wait()
        self.autosave()

    def updateWindowTitle(self):
        appName = 'Audio Visualizer'
        try:
            if self.currentProject:
                appName += ' - %s' % \
                    os.path.splitext(
                        os.path.basename(self.currentProject))[0]
            if self.autosaveExists(identical=False):
                appName += '*'
        except AttributeError:
            pass
        self.window.setWindowTitle(appName)

    @QtCore.pyqtSlot(int, dict)
    def updateComponentTitle(self, pos, presetStore=False):
        if type(presetStore) == dict:
            name = presetStore['preset']
            if name is None or name not in self.core.savedPresets:
                modified = False
            else:
                modified = (presetStore != self.core.savedPresets[name])
        else:
            modified = bool(presetStore)
        if pos < 0:
            pos = len(self.core.selectedComponents)-1
        title = str(self.core.selectedComponents[pos])
        if self.core.selectedComponents[pos].currentPreset:
            title += ' - %s' % self.core.selectedComponents[pos].currentPreset
            if modified:
                title += '*'
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

    def autosave(self, force=False):
        if not self.currentProject:
            if os.path.exists(self.autosavePath):
                os.remove(self.autosavePath)
        elif force or time.time() - self.lastAutosave >= 0.1:
            self.core.createProjectFile(self.autosavePath)
            self.lastAutosave = time.time()

    def autosaveExists(self, identical=True):
        try:
            if self.currentProject and os.path.exists(self.autosavePath) \
                and filecmp.cmp(
                    self.autosavePath, self.currentProject) == identical:
                return True
        except FileNotFoundError:
            print('project file couldn\'t be located:', self.currentProject)
            return identical
        return False

    def saveProjectChanges(self):
        try:
            os.remove(self.currentProject)
            os.rename(self.autosavePath, self.currentProject)
            return True
        except (FileNotFoundError, IsADirectoryError) as e:
            self.showMessage(
                msg='Project file couldn\'t be saved.',
                detail=str(e))
            return False

    def openInputFileDialog(self):
        inputDir = self.settings.value("inputDir", os.path.expanduser("~"))

        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.window, "Open Audio File",
            inputDir, "Audio Files (%s)" % " ".join(self.core.audioFormats))

        if fileName:
            self.settings.setValue("inputDir", os.path.dirname(fileName))
            self.window.lineEdit_audioFile.setText(fileName)

    def openOutputFileDialog(self):
        outputDir = self.settings.value("outputDir", os.path.expanduser("~"))

        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.window, "Set Output Video File",
            outputDir,
            "Video Files (%s);; All Files (*)" % " ".join(
                self.core.videoFormats))

        if fileName:
            self.settings.setValue("outputDir", os.path.dirname(fileName))
            self.window.lineEdit_outputFile.setText(fileName)

    def stopVideo(self):
        print('stop')
        self.videoWorker.cancel()
        self.canceled = True

    def createAudioVisualisation(self):
        # create output video if mandatory settings are filled in
        audioFile = self.window.lineEdit_audioFile.text()
        outputPath = self.window.lineEdit_outputFile.text()

        if audioFile and outputPath and self.core.selectedComponents:
            if not os.path.dirname(outputPath):
                outputPath = os.path.join(
                    os.path.expanduser("~"), outputPath)
            if outputPath and os.path.isdir(outputPath):
                self.showMessage(
                    msg='Chosen filename matches a directory, which '
                        'cannot be overwritten. Please choose a different '
                        'filename or move the directory.'
                )
                return
        else:
            if not audioFile or not outputPath:
                self.showMessage(
                    msg="You must select an audio file and output filename."
                )
            elif not self.core.selectedComponents:
                self.showMessage(
                    msg="Not enough components."
                )
            return

        self.canceled = False
        self.progressBarUpdated(-1)
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
            audioFile,
            outputPath,
            self.core.selectedComponents)

    def changeEncodingStatus(self, status):
        self.encoding = status
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
            self.window.listWidget_componentList.setEnabled(False)
            self.window.menuButton_newProject.setEnabled(False)
            self.window.menuButton_openProject.setEnabled(False)
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
            self.window.listWidget_componentList.setEnabled(True)
            self.window.menuButton_newProject.setEnabled(True)
            self.window.menuButton_openProject.setEnabled(True)
            self.drawPreview(True)

    def progressBarUpdated(self, value):
        self.window.progressBar_createVideo.setValue(value)

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

    def drawPreview(self, force=False):
        self.newTask.emit(self.core.selectedComponents)
        # self.processTask.emit()
        self.autosave(force)
        self.updateWindowTitle()

    def showPreviewImage(self, image):
        self.previewWindow.changePixmap(image)

    def insertComponent(self, index):
        componentList = self.window.listWidget_componentList
        stackedWidget = self.window.stackedWidget

        componentList.insertItem(
            index,
            self.core.selectedComponents[index].__doc__)
        componentList.setCurrentRow(index)

        # connect to signal that adds an asterisk when modified
        self.core.selectedComponents[index].modified.connect(
            self.updateComponentTitle)

        self.pages.insert(index, self.core.selectedComponents[index].page)
        stackedWidget.insertWidget(index, self.pages[index])
        stackedWidget.setCurrentIndex(index)

        return index

    def removeComponent(self):
        componentList = self.window.listWidget_componentList

        for selected in componentList.selectedItems():
            index = componentList.row(selected)
            self.window.stackedWidget.removeWidget(self.pages[index])
            componentList.takeItem(index)
            self.core.removeComponent(index)
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
            self.drawPreview()

    def moveComponentTop(self):
        componentList = self.window.listWidget_componentList
        row = -componentList.currentRow()
        self.moveComponent(row)

    def moveComponentBottom(self):
        componentList = self.window.listWidget_componentList
        row = len(componentList)-componentList.currentRow()-1
        self.moveComponent(row)

    def dragComponent(self, event):
        '''Drop event for the component listwidget'''
        componentList = self.window.listWidget_componentList

        modelIndexes = [
            componentList.model().index(i)
            for i in range(componentList.count())
        ]
        rects = [
            componentList.visualRect(modelIndex)
            for modelIndex in modelIndexes
        ]

        rowPos = [rect.contains(event.pos()) for rect in rects]
        if not any(rowPos):
            return

        i = rowPos.index(True)
        change = (componentList.currentRow() - i) * -1
        self.moveComponent(change)

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
        self.core.clearComponents()
        self.window.listWidget_componentList.clear()
        for widget in self.pages:
            self.window.stackedWidget.removeWidget(widget)
        self.pages = []

    @disableWhenEncoding
    def createNewProject(self):
        self.openSaveChangesDialog('starting a new project')

        self.clear()
        self.currentProject = None
        self.settings.setValue("currentProject", None)
        self.drawPreview(True)

    def saveCurrentProject(self):
        if self.currentProject:
            self.core.createProjectFile(self.currentProject)
            self.updateWindowTitle()
        else:
            self.openSaveProjectDialog()

    def openSaveChangesDialog(self, phrase):
        success = True
        if self.autosaveExists(identical=False):
            ch = self.showMessage(
                msg="You have unsaved changes in project '%s'. "
                "Save before %s?" % (
                    os.path.basename(self.currentProject)[:-4],
                    phrase
                ),
                showCancel=True)
            if ch:
                success = self.saveProjectChanges()

        if success and os.path.exists(self.autosavePath):
            os.remove(self.autosavePath)

    def openSaveProjectDialog(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.window, "Create Project File",
            self.settings.value("projectDir"),
            "Project Files (*.avp)")
        if not filename:
            return
        if not filename.endswith(".avp"):
            filename += '.avp'
        self.settings.setValue("projectDir", os.path.dirname(filename))
        self.settings.setValue("currentProject", filename)
        self.currentProject = filename
        self.core.createProjectFile(filename)
        self.updateWindowTitle()

    @disableWhenEncoding
    def openOpenProjectDialog(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.window, "Open Project File",
            self.settings.value("projectDir"),
            "Project Files (*.avp)")
        self.openProject(filename)

    def openProject(self, filepath, prompt=True):
        if not filepath or not os.path.exists(filepath) \
          or not filepath.endswith('.avp'):
            return

        self.clear()
        # ask to save any changes that are about to get deleted
        if prompt:
            self.openSaveChangesDialog('opening another project')

        self.currentProject = filepath
        self.settings.setValue("currentProject", filepath)
        self.settings.setValue("projectDir", os.path.dirname(filepath))
        # actually load the project using core method
        self.core.openProject(self, filepath)
        if self.window.listWidget_componentList.count() == 0:
            self.drawPreview()
        self.autosave(True)
        self.updateWindowTitle()

    def showMessage(self, **kwargs):
        parent = kwargs['parent'] if 'parent' in kwargs else self.window
        msg = QtWidgets.QMessageBox(parent)
        msg.setModal(True)
        msg.setText(kwargs['msg'])
        msg.setIcon(
            kwargs['icon']
            if 'icon' in kwargs else QtWidgets.QMessageBox.Information
        )
        msg.setDetailedText(kwargs['detail'] if 'detail' in kwargs else None)
        if 'showCancel'in kwargs and kwargs['showCancel']:
            msg.setStandardButtons(
                QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        else:
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        ch = msg.exec_()
        if ch == 1024:
            return True
        return False

    def componentContextMenu(self, QPos):
        '''Appears when right-clicking a component in the list'''
        componentList = self.window.listWidget_componentList
        if not componentList.selectedItems():
            return

        # don't show menu if clicking empty space
        parentPosition = componentList.mapToGlobal(QtCore.QPoint(0, 0))
        index = componentList.currentRow()
        modelIndex = componentList.model().index(index)
        if not componentList.visualRect(modelIndex).contains(QPos):
            return

        self.presetManager.findPresets()
        self.menu = QMenu()
        menuItem = self.menu.addAction("Save Preset")
        menuItem.triggered.connect(
            self.presetManager.openSavePresetDialog
        )

        # submenu for opening presets
        try:
            presets = self.presetManager.presets[
                str(self.core.selectedComponents[index])
            ]
            self.submenu = QMenu("Open Preset")
            self.menu.addMenu(self.submenu)

            for version, presetName in presets:
                menuItem = self.submenu.addAction(presetName)
                menuItem.triggered.connect(
                    lambda _, presetName=presetName:
                        self.presetManager.openPreset(presetName)
                )
        except KeyError:
            pass

        if self.core.selectedComponents[index].currentPreset:
            menuItem = self.menu.addAction("Clear Preset")
            menuItem.triggered.connect(
                self.presetManager.clearPreset
            )

        self.menu.move(parentPosition + QPos)
        self.menu.show()
