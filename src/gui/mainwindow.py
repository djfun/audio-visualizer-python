'''
    When using GUI mode, this module's object (the main window) takes
    user input to construct a program state (stored in the Core object).
    This shows a preview of the video being created and allows for saving
    projects and exporting the video at a later time.
'''
from PyQt5 import QtCore, QtGui, uic, QtWidgets
from PyQt5.QtWidgets import QMenu, QShortcut
from PIL import Image
from queue import Queue
import sys
import os
import signal
import filecmp
import time
import logging

from core import Core
import gui.preview_thread as preview_thread
from gui.preview_win import PreviewWindow
from gui.presetmanager import PresetManager
from gui.actions import *
from toolkit import disableWhenEncoding, disableWhenOpeningProject, checkOutput


log = logging.getLogger('AVP.MainWindow')


class MainWindow(QtWidgets.QMainWindow):
    '''
        The MainWindow wraps many Core methods in order to update the GUI
        accordingly. E.g., instead of self.core.openProject(), it will use
        self.openProject() and update the window titlebar within the wrapper.

        MainWindow manages the autosave feature, although Core has the
        primary functions for opening and creating project files.
    '''

    createVideo = QtCore.pyqtSignal()
    newTask = QtCore.pyqtSignal(list)  # for the preview window
    processTask = QtCore.pyqtSignal()

    def __init__(self, window, project):
        QtWidgets.QMainWindow.__init__(self)
        log.debug(
            'Main thread id: {}'.format(int(QtCore.QThread.currentThreadId())))
        self.window = window
        self.core = Core()
        Core.mode = 'GUI'

        # Find settings created by Core object
        self.dataDir = Core.dataDir
        self.presetDir = Core.presetDir
        self.autosavePath = os.path.join(self.dataDir, 'autosave.avp')
        self.settings = Core.settings

        # Create stack of undoable user actions
        self.undoStack = QtWidgets.QUndoStack(self)
        undoLimit = self.settings.value("pref_undoLimit")
        self.undoStack.setUndoLimit(undoLimit)

        # widgets of component settings
        self.pages = []
        self.lastAutosave = time.time()
        # list of previous five autosave times, used to reduce update spam
        self.autosaveTimes = []
        self.autosaveCooldown = 0.2
        self.encoding = False

        self.presetManager = PresetManager(
            uic.loadUi(
                os.path.join(Core.wd, 'gui', 'presetmanager.ui')), self)

        # Create the preview window and its thread, queues, and timers
        log.debug('Creating preview window')
        self.previewWindow = PreviewWindow(self, os.path.join(
            Core.wd, "background.png"))
        window.verticalLayout_previewWrapper.addWidget(self.previewWindow)

        log.debug('Starting preview thread')
        self.previewQueue = Queue()
        self.previewThread = QtCore.QThread(self)
        self.previewWorker = preview_thread.Worker(self, self.previewQueue)
        self.previewWorker.error.connect(self.previewWindow.threadError)
        self.previewWorker.moveToThread(self.previewThread)
        self.previewWorker.imageCreated.connect(self.showPreviewImage)
        self.previewThread.start()

        log.debug('Starting preview timer')
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.processTask.emit)
        self.timer.start(500)

        # Begin decorating the window and connecting events
        self.window.installEventFilter(self)
        componentList = self.window.listWidget_componentList

        if sys.platform == 'darwin':
            log.debug(
                'Darwin detected: showing progress label below progress bar')
            window.progressBar_createVideo.setTextVisible(False)
        else:
            window.progressLabel.setHidden(True)

        window.toolButton_selectAudioFile.clicked.connect(
            self.openInputFileDialog)

        window.toolButton_selectOutputFile.clicked.connect(
            self.openOutputFileDialog)

        def changedField():
            self.autosave()
            self.updateWindowTitle()

        window.lineEdit_audioFile.textChanged.connect(changedField)
        window.lineEdit_outputFile.textChanged.connect(changedField)

        window.progressBar_createVideo.setValue(0)

        window.pushButton_createVideo.clicked.connect(
            self.createAudioVisualisation)

        window.pushButton_Cancel.clicked.connect(self.stopVideo)

        for i, container in enumerate(Core.encoderOptions['containers']):
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

        # Make component buttons
        self.compMenu = QMenu()
        for i, comp in enumerate(self.core.modules):
            action = self.compMenu.addAction(comp.Component.name)
            action.triggered.connect(
                lambda _, item=i: self.core.insertComponent(0, item, self)
            )

        self.window.pushButton_addComponent.setMenu(self.compMenu)

        componentList.dropEvent = self.dragComponent
        componentList.itemSelectionChanged.connect(
            self.changeComponentWidget
        )
        componentList.itemSelectionChanged.connect(
            self.presetManager.clearPresetListSelection
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
        for i, res in enumerate(Core.resolutions):
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
        log.debug('Showing main window')
        window.show()

        if project and project != self.autosavePath:
            if not project.endswith('.avp'):
                project += '.avp'
            # open a project from the commandline
            if not os.path.dirname(project):
                project = os.path.join(
                    self.settings.value("projectDir"), project
                )
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

        # verify Pillow version
        if not self.settings.value("pilMsgShown") \
                and 'post' not in Image.PILLOW_VERSION:
            self.showMessage(
                msg="You are using the standard version of the "
                "Python imaging library (Pillow %s). Upgrade "
                "to the Pillow-SIMD fork to enable hardware accelerations "
                "and export videos faster." % Image.PILLOW_VERSION
            )
            self.settings.setValue("pilMsgShown", True)

        # verify Ffmpeg version
        if not self.settings.value("ffmpegMsgShown"):
            try:
                with open(os.devnull, "w") as f:
                    ffmpegVers = checkOutput(
                        ['ffmpeg', '-version'], stderr=f
                    )
                goodVersion = str(ffmpegVers).split()[2].startswith('3')
            except Exception:
                goodVersion = False
        else:
            goodVersion = True

        if not goodVersion:
            self.showMessage(
                msg="You're using an old version of Ffmpeg. "
                "Some features may not work as expected."
            )
        self.settings.setValue("ffmpegMsgShown", True)

        # Hotkeys for projects
        QtWidgets.QShortcut("Ctrl+S", self.window, self.saveCurrentProject)
        QtWidgets.QShortcut("Ctrl+A", self.window, self.openSaveProjectDialog)
        QtWidgets.QShortcut("Ctrl+O", self.window, self.openOpenProjectDialog)
        QtWidgets.QShortcut("Ctrl+N", self.window, self.createNewProject)

        QtWidgets.QShortcut("Ctrl+Z", self.window, self.undoStack.undo)
        QtWidgets.QShortcut("Ctrl+Y", self.window, self.undoStack.redo)
        QtWidgets.QShortcut("Ctrl+Shift+Z", self.window, self.undoStack.redo)

        # Hotkeys for component list
        for inskey in ("Ctrl+T", QtCore.Qt.Key_Insert):
            QtWidgets.QShortcut(
                inskey, self.window,
                activated=lambda: self.window.pushButton_addComponent.click()
            )
        for delkey in ("Ctrl+R", QtCore.Qt.Key_Delete):
            QtWidgets.QShortcut(
                delkey, self.window.listWidget_componentList,
                self.removeComponent
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
            "Ctrl+Up", self.window.listWidget_componentList,
            activated=lambda: self.moveComponent(-1)
        )
        QtWidgets.QShortcut(
            "Ctrl+Down", self.window.listWidget_componentList,
            activated=lambda: self.moveComponent(1)
        )
        QtWidgets.QShortcut(
            "Ctrl+Home", self.window.listWidget_componentList,
            activated=lambda: self.moveComponent('top')
        )
        QtWidgets.QShortcut(
            "Ctrl+End", self.window.listWidget_componentList,
            activated=lambda: self.moveComponent('bottom')
        )

        # Debug Hotkeys
        QtWidgets.QShortcut(
            "Ctrl+Alt+Shift+R", self.window, self.drawPreview
        )
        QtWidgets.QShortcut(
            "Ctrl+Alt+Shift+F", self.window, self.showFfmpegCommand
        )
        QtWidgets.QShortcut(
            "Ctrl+Alt+Shift+U", self.window, self.showUndoStack
        )

    @QtCore.pyqtSlot()
    def cleanUp(self, *args):
        log.info('Ending the preview thread')
        self.timer.stop()
        self.previewThread.quit()
        self.previewThread.wait()

    @disableWhenOpeningProject
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
        log.debug('Setting window title to %s' % appName)
        self.window.setWindowTitle(appName)

    @QtCore.pyqtSlot(int, dict)
    def updateComponentTitle(self, pos, presetStore=False):
        if type(presetStore) is dict:
            name = presetStore['preset']
            if name is None or name not in self.core.savedPresets:
                modified = False
            else:
                modified = (presetStore != self.core.savedPresets[name])
        else:
            modified = bool(presetStore)
        if pos < 0:
            pos = len(self.core.selectedComponents)-1
        name = str(self.core.selectedComponents[pos])
        title = str(name)
        if self.core.selectedComponents[pos].currentPreset:
            title += ' - %s' % self.core.selectedComponents[pos].currentPreset
            if modified:
                title += '*'
        if type(presetStore) is bool:
            log.debug('Forcing %s #%s\'s modified status to %s: %s' % (
                name, pos, modified, title
            ))
        else:
            log.debug('Setting %s #%s\'s title: %s' % (
                name, pos, title
            ))
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

        for container in Core.encoderOptions['containers']:
            if container['name'] == name:
                for vCodec in container['video-codecs']:
                    vCodecWidget.addItem(vCodec)
                for aCodec in container['audio-codecs']:
                    aCodecWidget.addItem(aCodec)

    def updateCodecSettings(self):
        '''Updates settings.ini to match encoder option widgets'''
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

    @disableWhenOpeningProject
    def autosave(self, force=False):
        if not self.currentProject:
            if os.path.exists(self.autosavePath):
                os.remove(self.autosavePath)
        elif force or time.time() - self.lastAutosave >= self.autosaveCooldown:
            self.core.createProjectFile(self.autosavePath, self.window)
            self.lastAutosave = time.time()
            if len(self.autosaveTimes) >= 5:
                # Do some math to reduce autosave spam. This gives a smooth
                # curve up to 5 seconds cooldown and maintains that for 30 secs
                # if a component is continuously updated
                timeDiff = self.lastAutosave - self.autosaveTimes.pop()
                if not force and timeDiff >= 1.0 \
                        and timeDiff <= 10.0:
                    if self.autosaveCooldown / 4.0 < 0.5:
                        self.autosaveCooldown += 1.0
                    self.autosaveCooldown = (
                            5.0 * (self.autosaveCooldown / 5.0)
                        ) + (self.autosaveCooldown / 5.0) * 2
                elif force or timeDiff >= self.autosaveCooldown * 5:
                    self.autosaveCooldown = 0.2
            self.autosaveTimes.insert(0, self.lastAutosave)
        else:
            log.debug('Autosave rejected by cooldown')

    def autosaveExists(self, identical=True):
        '''Determines if creating the autosave should be blocked.'''
        try:
            if self.currentProject and os.path.exists(self.autosavePath) \
                and filecmp.cmp(
                    self.autosavePath, self.currentProject) == identical:
                log.debug(
                    'Autosave found %s to be identical'
                    % 'not' if not identical else ''
                )
                return True
        except FileNotFoundError:
            log.error(
                'Project file couldn\'t be located:', self.currentProject)
            return identical
        return False

    def saveProjectChanges(self):
        '''Overwrites project file with autosave file'''
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
            inputDir, "Audio Files (%s)" % " ".join(Core.audioFormats))

        if fileName:
            self.settings.setValue("inputDir", os.path.dirname(fileName))
            self.window.lineEdit_audioFile.setText(fileName)

    def openOutputFileDialog(self):
        outputDir = self.settings.value("outputDir", os.path.expanduser("~"))

        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.window, "Set Output Video File",
            outputDir,
            "Video Files (%s);; All Files (*)" % " ".join(
                Core.videoFormats))

        if fileName:
            self.settings.setValue("outputDir", os.path.dirname(fileName))
            self.window.lineEdit_outputFile.setText(fileName)

    def stopVideo(self):
        log.info('Export cancelled')
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
                        'filename or move the directory.',
                    icon='Warning',
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
        self.videoWorker = self.core.newVideoWorker(
            self, audioFile, outputPath
        )
        self.videoWorker.progressBarUpdate.connect(self.progressBarUpdated)
        self.videoWorker.progressBarSetText.connect(
            self.progressBarSetText)
        self.videoWorker.imageCreated.connect(self.showPreviewImage)
        self.videoWorker.encoding.connect(self.changeEncodingStatus)
        self.createVideo.emit()

    @QtCore.pyqtSlot(str, str)
    def videoThreadError(self, msg, detail):
        try:
            self.stopVideo()
        except AttributeError as e:
            if 'videoWorker' not in str(e):
                raise
        self.showMessage(
            msg=msg,
            detail=detail,
            icon='Critical',
        )

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
            self.window.menuButton_newProject.setEnabled(False)
            self.window.menuButton_openProject.setEnabled(False)
            if sys.platform == 'darwin':
                self.window.progressLabel.setHidden(False)
            else:
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
            self.window.menuButton_newProject.setEnabled(True)
            self.window.menuButton_openProject.setEnabled(True)
            self.window.listWidget_componentList.setEnabled(True)
            self.window.progressLabel.setHidden(True)
            self.drawPreview(True)

    @QtCore.pyqtSlot(int)
    def progressBarUpdated(self, value):
        self.window.progressBar_createVideo.setValue(value)

    @QtCore.pyqtSlot(str)
    def progressBarSetText(self, value):
        if sys.platform == 'darwin':
            self.window.progressLabel.setText(value)
        else:
            self.window.progressBar_createVideo.setFormat(value)

    def updateResolution(self):
        resIndex = int(self.window.comboBox_resolution.currentIndex())
        res = Core.resolutions[resIndex].split('x')
        changed = res[0] != self.settings.value("outputWidth")
        self.settings.setValue('outputWidth', res[0])
        self.settings.setValue('outputHeight', res[1])
        if changed:
            for i in range(len(self.core.selectedComponents)):
                self.core.updateComponent(i)

    def drawPreview(self, force=False, **kwargs):
        '''Use autosave keyword arg to force saving or not saving if needed'''
        self.newTask.emit(self.core.selectedComponents)
        # self.processTask.emit()
        if force or 'autosave' in kwargs:
            if force or kwargs['autosave']:
                self.autosave(True)
        else:
            self.autosave()
        self.updateWindowTitle()

    @QtCore.pyqtSlot(QtGui.QImage)
    def showPreviewImage(self, image):
        self.previewWindow.changePixmap(image)

    def showUndoStack(self):
        dialog = QtWidgets.QDialog(self.window)
        undoView = QtWidgets.QUndoView(self.undoStack)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(undoView)
        dialog.setLayout(layout)
        dialog.show()

    def showFfmpegCommand(self):
        from textwrap import wrap
        from toolkit.ffmpeg import createFfmpegCommand
        command = createFfmpegCommand(
            self.window.lineEdit_audioFile.text(),
            self.window.lineEdit_outputFile.text(),
            self.core.selectedComponents
        )
        lines = wrap(" ".join(command), 49)
        self.showMessage(
            msg="Current FFmpeg command:\n\n %s" % " ".join(lines)
        )

    def insertComponent(self, index):
        componentList = self.window.listWidget_componentList
        stackedWidget = self.window.stackedWidget

        componentList.insertItem(
            index,
            self.core.selectedComponents[index].name)
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
        selected = componentList.selectedItems()
        if selected:
            action = RemoveComponent(self, selected)
            self.undoStack.push(action)

    @disableWhenEncoding
    def moveComponent(self, change):
        '''Moves a component relatively from its current position'''
        componentList = self.window.listWidget_componentList
        tag = change
        if change == 'top':
            change = -componentList.currentRow()
        elif change == 'bottom':
            change = len(componentList)-componentList.currentRow()-1
        else:
            tag = 'down' if change == 1 else 'up'

        row = componentList.currentRow()
        newRow = row + change
        if newRow > -1 and newRow < componentList.count():
            action = MoveComponent(self, row, newRow, tag)
            self.undoStack.push(action)

    def getComponentListMousePos(self, position):
        '''
        Given a QPos, returns the component index under the mouse cursor
        or -1 if no component is there.
        '''
        componentList = self.window.listWidget_componentList

        modelIndexes = [
            componentList.model().index(i)
            for i in range(componentList.count())
        ]
        rects = [
            componentList.visualRect(modelIndex)
            for modelIndex in modelIndexes
        ]
        mousePos = [rect.contains(position) for rect in rects]
        if not any(mousePos):
            # Not clicking a component
            mousePos = -1
        else:
            mousePos = mousePos.index(True)
        log.debug('Click component list row %s' % mousePos)
        return mousePos

    @disableWhenEncoding
    def dragComponent(self, event):
        '''Used as Qt drop event for the component listwidget'''
        componentList = self.window.listWidget_componentList
        mousePos = self.getComponentListMousePos(event.pos())
        if mousePos > -1:
            change = (componentList.currentRow() - mousePos) * -1
        else:
            change = (componentList.count() - componentList.currentRow() - 1)
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
        for field in (
                self.window.lineEdit_audioFile,
                self.window.lineEdit_outputFile
                ):
            field.blockSignals(True)
            field.setText('')
            field.blockSignals(False)
        self.progressBarUpdated(0)
        self.progressBarSetText('')
        self.undoStack.clear()

    @disableWhenEncoding
    def createNewProject(self, prompt=True):
        if prompt:
            self.openSaveChangesDialog('starting a new project')

        self.clear()
        self.currentProject = None
        self.settings.setValue("currentProject", None)
        self.drawPreview(True)

    def saveCurrentProject(self):
        if self.currentProject:
            self.core.createProjectFile(self.currentProject, self.window)
            try:
                os.remove(self.autosavePath)
            except FileNotFoundError:
                pass
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
        self.core.createProjectFile(filename, self.window)
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
        self.drawPreview(autosave=False)
        self.updateWindowTitle()

    def showMessage(self, **kwargs):
        parent = kwargs['parent'] if 'parent' in kwargs else self.window
        msg = QtWidgets.QMessageBox(parent)
        msg.setModal(True)
        msg.setText(kwargs['msg'])
        msg.setIcon(
            eval('QtWidgets.QMessageBox.%s' % kwargs['icon'])
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

    @disableWhenEncoding
    def componentContextMenu(self, QPos):
        '''Appears when right-clicking the component list'''
        componentList = self.window.listWidget_componentList
        self.menu = QMenu()
        parentPosition = componentList.mapToGlobal(QtCore.QPoint(0, 0))

        index = self.getComponentListMousePos(QPos)
        if index > -1:
            # Show preset menu if clicking a component
            self.presetManager.findPresets()
            menuItem = self.menu.addAction("Save Preset")
            menuItem.triggered.connect(
                self.presetManager.openSavePresetDialog
            )

            # submenu for opening presets
            try:
                presets = self.presetManager.presets[
                    str(self.core.selectedComponents[index])
                ]
                self.presetSubmenu = QMenu("Open Preset")
                self.menu.addMenu(self.presetSubmenu)

                for version, presetName in presets:
                    menuItem = self.presetSubmenu.addAction(presetName)
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
            self.menu.addSeparator()

        # "Add Component" submenu
        self.submenu = QMenu("Add")
        self.menu.addMenu(self.submenu)
        insertCompAtTop = self.settings.value("pref_insertCompAtTop")
        for i, comp in enumerate(self.core.modules):
            menuItem = self.submenu.addAction(comp.Component.name)
            menuItem.triggered.connect(
                lambda _, item=i: self.core.insertComponent(
                    0 if insertCompAtTop else index, item, self
                )
            )

        self.menu.move(parentPosition + QPos)
        self.menu.show()

    def eventFilter(self, object, event):
        if event.type() == QtCore.QEvent.WindowActivate \
                or event.type() == QtCore.QEvent.FocusIn:
            Core.windowHasFocus = True
        elif event.type() == QtCore.QEvent.WindowDeactivate \
                or event.type() == QtCore.QEvent.FocusOut:
                    Core.windowHasFocus = False
        return False
