"""
When using GUI mode, this module's object (the main window) takes
user input to construct a program state (stored in the Core object).
This shows a preview of the video being created and allows for saving
projects and exporting the video at a later time.
"""

from PyQt6 import QtCore, QtWidgets, uic
import PyQt6.QtWidgets as QtWidgets
from PyQt6.QtGui import QShortcut
from PIL import Image
from queue import Queue
import sys
import os
import signal
import filecmp
import time
import logging
from textwrap import wrap

from ..__init__ import __version__
from ..core import Core, appName
from .undostack import UndoStack
from . import preview_thread
from .preview_win import PreviewWindow
from .presetmanager import PresetManager
from .actions import *
from ..toolkit.ffmpeg import createFfmpegCommand
from ..toolkit import (
    disableWhenEncoding,
    disableWhenOpeningProject,
    checkOutput,
    blockSignals,
)


log = logging.getLogger("AVP.Gui.MainWindow")


class MainWindow(QtWidgets.QMainWindow):
    """
    The MainWindow wraps many Core methods in order to update the GUI
    accordingly. E.g., instead of self.core.openProject(), it will use
    self.openProject() and update the window titlebar within the wrapper.

    MainWindow manages the autosave feature, although Core has the
    primary functions for opening and creating project files.
    """

    createVideo = QtCore.pyqtSignal()
    newTask = QtCore.pyqtSignal(list)  # for the preview window
    processTask = QtCore.pyqtSignal()

    def __init__(self, project, dpi):
        super().__init__()
        log.debug("Main thread id: {}".format(int(QtCore.QThread.currentThreadId())))
        uic.loadUi(os.path.join(Core.wd, "gui", "mainwindow.ui"), self)

        if dpi:
            self.resize(
                int(self.width() * (dpi / 144)),
                int(self.height() * (dpi / 144)),
            )

        self.core = Core()
        Core.mode = "GUI"
        # widgets of component settings
        self.pages = []
        self.lastAutosave = time.time()
        # list of previous five autosave times, used to reduce update spam
        self.autosaveTimes = []
        self.autosaveCooldown = 0.2
        self.encoding = False

        # Find settings created by Core object
        self.dataDir = Core.dataDir
        self.presetDir = Core.presetDir
        self.autosavePath = os.path.join(self.dataDir, "autosave.avp")
        self.settings = Core.settings

        # Create stack of undoable user actions
        self.undoStack = UndoStack(self)
        undoLimit = self.settings.value("pref_undoLimit")
        self.undoStack.setUndoLimit(undoLimit)

        # Create Undo Dialog - A standard QUndoView on a standard QDialog
        self.undoDialog = QtWidgets.QDialog(self)
        self.undoDialog.setWindowTitle("Undo History")
        undoView = QtWidgets.QUndoView(self.undoStack)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(undoView)
        self.undoDialog.setLayout(layout)
        self.undoDialog.setMinimumWidth(int(self.width() / 2))

        # Create Preset Manager
        self.presetManager = PresetManager(self)

        # Create the preview window and its thread, queues, and timers
        log.debug("Creating preview window")
        self.previewWindow = PreviewWindow(
            self, os.path.join(Core.wd, "gui", "background.png")
        )
        self.verticalLayout_previewWrapper.addWidget(self.previewWindow)

        log.debug("Starting preview thread")
        self.previewQueue = Queue()
        self.previewThread = QtCore.QThread(self)
        self.previewWorker = preview_thread.Worker(
            self.core, self.settings, self.previewQueue
        )
        self.previewWorker.moveToThread(self.previewThread)
        self.newTask.connect(self.previewWorker.createPreviewImage)
        self.processTask.connect(self.previewWorker.process)
        self.previewWorker.error.connect(self.previewWindow.threadError)
        self.previewWorker.imageCreated.connect(self.showPreviewImage)
        self.previewThread.start()
        self.previewThread.finished.connect(
            lambda: log.info("Preview thread finished.")
        )

        timeout = 500
        log.debug("Preview timer set to trigger when idle for %sms" % str(timeout))
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.processTask.emit)
        self.timer.start(timeout)

        # Begin decorating the window and connecting events
        componentList = self.listWidget_componentList

        # Undo Feature
        def toggleUndoButtonEnabled(*_):
            """Enable/disable undo button depending on whether UndoStack contains Actions"""
            try:
                undoButton.setEnabled(self.undoStack.count())
            except RuntimeError:
                # program is probably in midst of exiting
                pass

        style = self.pushButton_undo.style()
        undoButton = self.pushButton_undo
        undoButton.setIcon(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogBack)
        )
        undoButton.clicked.connect(self.undoStack.undo)
        undoButton.setEnabled(False)
        self.undoStack.cleanChanged.connect(toggleUndoButtonEnabled)
        self.undoMenu = QtWidgets.QMenu()
        self.undoMenu.addAction(self.undoStack.createUndoAction(self))
        self.undoMenu.addAction(self.undoStack.createRedoAction(self))
        action = self.undoMenu.addAction("Show History...")
        action.triggered.connect(lambda _: self.showUndoStack())
        undoButton.setMenu(self.undoMenu)
        # end of Undo Feature

        style = self.pushButton_listMoveUp.style()
        self.pushButton_listMoveUp.setIcon(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowUp)
        )
        style = self.pushButton_listMoveDown.style()
        self.pushButton_listMoveDown.setIcon(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowDown)
        )
        style = self.pushButton_removeComponent.style()
        self.pushButton_removeComponent.setIcon(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogDiscardButton)
        )

        if sys.platform == "darwin":
            log.debug("Darwin detected: showing progress label below progress bar")
            self.progressBar_createVideo.setTextVisible(False)
        else:
            self.progressLabel.setHidden(True)

        self.toolButton_selectAudioFile.clicked.connect(self.openInputFileDialog)

        self.toolButton_selectOutputFile.clicked.connect(self.openOutputFileDialog)

        def changedField():
            self.autosave()
            self.updateWindowTitle()

        self.lineEdit_audioFile.textChanged.connect(changedField)
        self.lineEdit_outputFile.textChanged.connect(changedField)

        self.progressBar_createVideo.setValue(0)

        self.pushButton_createVideo.clicked.connect(self.createAudioVisualization)

        self.pushButton_Cancel.clicked.connect(self.stopVideo)

        for i, container in enumerate(Core.encoderOptions["containers"]):
            self.comboBox_videoContainer.addItem(container["name"])
            if container["name"] == self.settings.value("outputContainer"):
                selectedContainer = i

        self.comboBox_videoContainer.setCurrentIndex(selectedContainer)
        self.comboBox_videoContainer.currentIndexChanged.connect(self.updateCodecs)

        self.updateCodecs()

        for i in range(self.comboBox_videoCodec.count()):
            codec = self.comboBox_videoCodec.itemText(i)
            if codec == self.settings.value("outputVideoCodec"):
                self.comboBox_videoCodec.setCurrentIndex(i)

        for i in range(self.comboBox_audioCodec.count()):
            codec = self.comboBox_audioCodec.itemText(i)
            if codec == self.settings.value("outputAudioCodec"):
                self.comboBox_audioCodec.setCurrentIndex(i)

        self.comboBox_videoCodec.currentIndexChanged.connect(self.updateCodecSettings)

        self.comboBox_audioCodec.currentIndexChanged.connect(self.updateCodecSettings)

        vBitrate = int(self.settings.value("outputVideoBitrate"))
        aBitrate = int(self.settings.value("outputAudioBitrate"))

        self.spinBox_vBitrate.setValue(vBitrate)
        self.spinBox_aBitrate.setValue(aBitrate)
        self.spinBox_vBitrate.valueChanged.connect(self.updateCodecSettings)
        self.spinBox_aBitrate.valueChanged.connect(self.updateCodecSettings)

        # Make component buttons
        self.compMenu = QtWidgets.QMenu()
        for i, comp in enumerate(self.core.modules):
            action = self.compMenu.addAction(comp.Component.name)
            action.triggered.connect(lambda _, item=i: self.addComponent(0, item))

        self.pushButton_addComponent.setMenu(self.compMenu)

        componentList.dropEvent = self.dragComponent
        componentList.itemSelectionChanged.connect(self.changeComponentWidget)
        componentList.itemSelectionChanged.connect(
            self.presetManager.clearPresetListSelection
        )
        self.pushButton_removeComponent.clicked.connect(lambda: self.removeComponent())

        componentList.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        componentList.customContextMenuRequested.connect(self.componentContextMenu)

        currentRes = (
            str(self.settings.value("outputWidth"))
            + "x"
            + str(self.settings.value("outputHeight"))
        )
        for i, res in enumerate(Core.resolutions):
            self.comboBox_resolution.addItem(res)
            if res == currentRes:
                currentRes = i
                self.comboBox_resolution.setCurrentIndex(currentRes)
                self.comboBox_resolution.currentIndexChanged.connect(
                    self.updateResolution
                )

        self.pushButton_listMoveUp.clicked.connect(lambda: self.moveComponent(-1))
        self.pushButton_listMoveDown.clicked.connect(lambda: self.moveComponent(1))

        # Configure the Projects Menu
        self.projectMenu = QtWidgets.QMenu()
        self.menuButton_newProject = self.projectMenu.addAction("New Project")
        self.menuButton_newProject.triggered.connect(lambda: self.createNewProject())
        self.menuButton_openProject = self.projectMenu.addAction("Open Project")
        self.menuButton_openProject.triggered.connect(
            lambda: self.openOpenProjectDialog()
        )

        action = self.projectMenu.addAction("Save Project")
        action.triggered.connect(self.saveCurrentProject)

        action = self.projectMenu.addAction("Save Project As")
        action.triggered.connect(self.openSaveProjectDialog)

        self.pushButton_projects.setMenu(self.projectMenu)

        # Configure the Presets Button
        self.pushButton_presets.clicked.connect(self.openPresetManager)

        self.updateWindowTitle()
        log.debug("Showing main window")
        self.show()

        if project and project != self.autosavePath:
            if not project.endswith(".avp"):
                project += ".avp"
            # open a project from the commandline
            if not os.path.dirname(project):
                project = os.path.join(self.settings.value("projectDir"), project)
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
                    showCancel=True,
                )
                if ch:
                    self.saveProjectChanges()
                else:
                    os.remove(self.autosavePath)

        self.openProject(self.currentProject, prompt=False)
        self.drawPreview(True)

        log.info("Pillow version %s", Image.__version__)
        log.info(
            "PyQt version %s (Qt version %s)",
            QtCore.PYQT_VERSION_STR,
            QtCore.QT_VERSION_STR,
        )

        # verify Ffmpeg version
        if not self.core.FFMPEG_BIN:
            self.showMessage(
                msg="FFmpeg could not be found. This is a critical error. "
                "Install FFmpeg, or download it and place the program executable "
                "in the same folder as this program.",
                icon="Critical",
            )
        else:
            if not self.settings.value("ffmpegMsgShown"):
                try:
                    with open(os.devnull, "w") as f:
                        ffmpegVers = checkOutput(
                            [self.core.FFMPEG_BIN, "-version"], stderr=f
                        )
                    ffmpegVers = str(ffmpegVers).split()[2].split(".", 1)[0]
                    if ffmpegVers.startswith("n"):
                        ffmpegVers = ffmpegVers[1:]
                    goodVersion = int(ffmpegVers) > 3
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

        QShortcut("Ctrl+S", self, self.saveCurrentProject)
        QShortcut("Ctrl+A", self, self.openSaveProjectDialog)
        QShortcut("Ctrl+O", self, self.openOpenProjectDialog)
        QShortcut("Ctrl+N", self, self.createNewProject)

        # Hotkeys for undo/redo
        QShortcut("Ctrl+Z", self, self.undoStack.undo)
        QShortcut("Ctrl+Y", self, self.undoStack.redo)
        QShortcut("Ctrl+Shift+Z", self, self.undoStack.redo)

        # Hotkeys for component list
        for inskey in ("Ctrl+T", QtCore.Qt.Key.Key_Insert):
            QShortcut(
                inskey,
                self,
                activated=lambda: self.pushButton_addComponent.click(),
            )
        for delkey in ("Ctrl+R", QtCore.Qt.Key.Key_Delete):
            QShortcut(delkey, self.listWidget_componentList, self.removeComponent)
        QShortcut(
            "Ctrl+Space",
            self,
            activated=lambda: self.listWidget_componentList.setFocus(),
        )
        QShortcut("Ctrl+Shift+S", self, self.presetManager.openSavePresetDialog)
        QShortcut("Ctrl+Shift+C", self, self.presetManager.clearPreset)

        QShortcut(
            "Ctrl+Up",
            self.listWidget_componentList,
            activated=lambda: self.moveComponent(-1),
        )
        QShortcut(
            "Ctrl+Down",
            self.listWidget_componentList,
            activated=lambda: self.moveComponent(1),
        )
        QShortcut(
            "Ctrl+Home",
            self.listWidget_componentList,
            activated=lambda: self.moveComponent("top"),
        )
        QShortcut(
            "Ctrl+End",
            self.listWidget_componentList,
            activated=lambda: self.moveComponent("bottom"),
        )

        QShortcut("F1", self, self.showHelpWindow)
        QShortcut("Ctrl+Shift+F", self, self.showFfmpegCommand)
        QShortcut("Ctrl+Shift+U", self, self.showUndoStack)

        if log.isEnabledFor(logging.DEBUG):
            QShortcut("Ctrl+Alt+Shift+R", self, self.drawPreview)
            QShortcut("Ctrl+Alt+Shift+A", self, lambda: log.debug(repr(self)))

        # Close MainWindow when receiving Ctrl+C from terminal
        signal.signal(signal.SIGINT, lambda *args: self.close())

        # Add initial components if none are in the list
        if not self.core.selectedComponents:
            self.core.insertComponent(0, 0, self)
            self.core.insertComponent(1, 1, self)

    def __repr__(self):
        return (
            "%s\n"
            "\n%s\n"
            "#####\n"
            "Preview thread is %s\n"
            % (
                super().__repr__(),
                (
                    "core not initialized"
                    if not hasattr(self, "core")
                    else repr(self.core)
                ),
                (
                    "live"
                    if hasattr(self, "previewThread") and self.previewThread.isRunning()
                    else "dead"
                ),
            )
        )

    def closeEvent(self, event):
        log.info("Ending the preview thread")
        self.timer.stop()
        self.previewThread.quit()
        self.previewThread.wait()
        return super().closeEvent(event)

    @disableWhenOpeningProject
    def updateWindowTitle(self):
        log.debug("Setting main window's title")
        windowTitle = appName
        try:
            if self.currentProject:
                windowTitle += (
                    " - %s" % os.path.splitext(os.path.basename(self.currentProject))[0]
                )
            if self.autosaveExists(identical=False):
                windowTitle += "*"
        except AttributeError:
            pass
        log.verbose(f'Window title is "{windowTitle}"')
        self.setWindowTitle(windowTitle)

    @QtCore.pyqtSlot(int, dict)
    def updateComponentTitle(self, pos, presetStore=False):
        """
        Sets component title to modified or unmodified when given boolean.
        If given a preset dict, compares it against the component to
        determine if it is modified.
        A component with no preset is always unmodified.
        """
        if type(presetStore) is dict:
            name = presetStore["preset"]
            if name is None or name not in self.core.savedPresets:
                modified = False
            else:
                modified = presetStore != self.core.savedPresets[name]

        modified = bool(presetStore)
        if pos < 0:
            pos = len(self.core.selectedComponents) - 1
        name = self.core.selectedComponents[pos].name
        title = str(name)
        if self.core.selectedComponents[pos].currentPreset:
            title += " - %s" % self.core.selectedComponents[pos].currentPreset
            if modified:
                title += "*"
        if type(presetStore) is bool:
            log.debug(
                "Forcing %s #%s's modified status to %s: %s",
                name,
                pos,
                modified,
                title,
            )
        else:
            log.debug("Setting %s #%s's title: %s", name, pos, title)
        self.listWidget_componentList.item(pos).setText(title)

    def updateCodecs(self):
        containerWidget = self.comboBox_videoContainer
        vCodecWidget = self.comboBox_videoCodec
        aCodecWidget = self.comboBox_audioCodec
        index = containerWidget.currentIndex()
        name = containerWidget.itemText(index)
        self.settings.setValue("outputContainer", name)

        vCodecWidget.clear()
        aCodecWidget.clear()

        for container in Core.encoderOptions["containers"]:
            if container["name"] == name:
                for vCodec in container["video-codecs"]:
                    vCodecWidget.addItem(vCodec)
                for aCodec in container["audio-codecs"]:
                    aCodecWidget.addItem(aCodec)

    def updateCodecSettings(self):
        """Updates settings.ini to match encoder option widgets"""
        vCodecWidget = self.comboBox_videoCodec
        vBitrateWidget = self.spinBox_vBitrate
        aBitrateWidget = self.spinBox_aBitrate
        aCodecWidget = self.comboBox_audioCodec
        currentVideoCodec = vCodecWidget.currentIndex()
        currentVideoCodec = vCodecWidget.itemText(currentVideoCodec)
        currentVideoBitrate = vBitrateWidget.value()
        currentAudioCodec = aCodecWidget.currentIndex()
        currentAudioCodec = aCodecWidget.itemText(currentAudioCodec)
        currentAudioBitrate = aBitrateWidget.value()
        self.settings.setValue("outputVideoCodec", currentVideoCodec)
        self.settings.setValue("outputAudioCodec", currentAudioCodec)
        self.settings.setValue("outputVideoBitrate", currentVideoBitrate)
        self.settings.setValue("outputAudioBitrate", currentAudioBitrate)

    @disableWhenOpeningProject
    def autosave(self, force=False):
        if not self.currentProject:
            if os.path.exists(self.autosavePath):
                os.remove(self.autosavePath)
        elif force or time.time() - self.lastAutosave >= self.autosaveCooldown:
            self.core.createProjectFile(self.autosavePath, self)
            self.lastAutosave = time.time()
            if len(self.autosaveTimes) >= 5:
                # Do some math to reduce autosave spam. This gives a smooth
                # curve up to 5 seconds cooldown and maintains that for 30 secs
                # if a component is continuously updated
                timeDiff = self.lastAutosave - self.autosaveTimes.pop()
                if not force and timeDiff >= 1.0 and timeDiff <= 10.0:
                    if self.autosaveCooldown / 4.0 < 0.5:
                        self.autosaveCooldown += 1.0
                    self.autosaveCooldown = (5.0 * (self.autosaveCooldown / 5.0)) + (
                        self.autosaveCooldown / 5.0
                    ) * 2
                elif force or timeDiff >= self.autosaveCooldown * 5:
                    self.autosaveCooldown = 0.2
            self.autosaveTimes.insert(0, self.lastAutosave)
        else:
            log.debug("Autosave rejected by cooldown")

    def autosaveExists(self, identical=True):
        """Determines if creating the autosave should be blocked."""
        try:
            if (
                self.currentProject
                and os.path.exists(self.autosavePath)
                and filecmp.cmp(self.autosavePath, self.currentProject) == identical
            ):
                log.debug(
                    "Autosave found %s to be identical" % "not" if not identical else ""
                )
                return True
        except FileNotFoundError:
            log.error("Project file couldn't be located: %s", self.currentProject)
            return identical
        return False

    def saveProjectChanges(self):
        """Overwrites project file with autosave file"""
        try:
            os.remove(self.currentProject)
            os.rename(self.autosavePath, self.currentProject)
            return True
        except (FileNotFoundError, IsADirectoryError) as e:
            self.showMessage(msg="Project file couldn't be saved.", detail=str(e))
            return False

    def openInputFileDialog(self):
        inputDir = self.settings.value("inputDir", os.path.expanduser("~"))

        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Audio File",
            inputDir,
            "Audio Files (%s)" % " ".join(Core.audioFormats),
        )

        if fileName:
            self.settings.setValue("inputDir", os.path.dirname(fileName))
            self.lineEdit_audioFile.setText(fileName)

    def openOutputFileDialog(self):
        outputDir = self.settings.value("outputDir", os.path.expanduser("~"))

        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Set Output Video File",
            outputDir,
            "Video Files (%s);; All Files (*)" % " ".join(Core.videoFormats),
        )

        if fileName:
            self.settings.setValue("outputDir", os.path.dirname(fileName))
            self.lineEdit_outputFile.setText(fileName)

    def stopVideo(self):
        log.info("Export cancelled")
        self.videoWorker.cancel()
        self.canceled = True

    def createAudioVisualization(self):
        # create output video if mandatory settings are filled in
        audioFile = self.lineEdit_audioFile.text()
        outputPath = self.lineEdit_outputFile.text()

        if audioFile and outputPath and self.core.selectedComponents:
            if not os.path.dirname(outputPath):
                outputPath = os.path.join(os.path.expanduser("~"), outputPath)
            if outputPath and os.path.isdir(outputPath):
                self.showMessage(
                    msg="Chosen filename matches a directory, which "
                    "cannot be overwritten. Please choose a different "
                    "filename or move the directory.",
                    icon="Warning",
                )
                return
        else:
            if not audioFile or not outputPath:
                self.showMessage(
                    msg="You must select an audio file and output filename."
                )
            elif not self.core.selectedComponents:
                self.showMessage(msg="Not enough components.")
            return

        self.canceled = False
        self.progressBarUpdated(-1)
        self.videoWorker = self.core.newVideoWorker(self, audioFile, outputPath)
        self.videoWorker.progressBarUpdate.connect(self.progressBarUpdated)
        self.videoWorker.progressBarSetText.connect(self.progressBarSetText)
        self.videoWorker.imageCreated.connect(self.showPreviewImage)
        self.videoWorker.encoding.connect(self.changeEncodingStatus)
        self.createVideo.emit()

    @QtCore.pyqtSlot(str, str)
    def videoThreadError(self, msg, detail):
        try:
            self.stopVideo()
        except AttributeError as e:
            if "videoWorker" not in str(e):
                raise
        self.showMessage(
            msg=msg,
            detail=detail,
            icon="Critical",
        )
        log.info("%s", repr(self))

    def changeEncodingStatus(self, status):
        self.encoding = status
        if status:
            # Disable many widgets when starting to export
            self.pushButton_createVideo.setEnabled(False)
            self.pushButton_Cancel.setEnabled(True)
            self.comboBox_resolution.setEnabled(False)
            self.stackedWidget.setEnabled(False)
            self.tab_encoderSettings.setEnabled(False)
            self.label_audioFile.setEnabled(False)
            self.toolButton_selectAudioFile.setEnabled(False)
            self.label_outputFile.setEnabled(False)
            self.toolButton_selectOutputFile.setEnabled(False)
            self.lineEdit_audioFile.setEnabled(False)
            self.lineEdit_outputFile.setEnabled(False)
            self.listWidget_componentList.setEnabled(False)
            self.pushButton_addComponent.setEnabled(False)
            self.pushButton_removeComponent.setEnabled(False)
            self.pushButton_listMoveDown.setEnabled(False)
            self.pushButton_listMoveUp.setEnabled(False)
            self.pushButton_undo.setEnabled(False)
            self.menuButton_newProject.setEnabled(False)
            self.menuButton_openProject.setEnabled(False)
            # Close undo history dialog if open
            self.undoDialog.close()
            # Show label under progress bar on macOS
            if sys.platform == "darwin":
                self.progressLabel.setHidden(False)
        else:
            self.pushButton_createVideo.setEnabled(True)
            self.pushButton_Cancel.setEnabled(False)
            self.comboBox_resolution.setEnabled(True)
            self.stackedWidget.setEnabled(True)
            self.tab_encoderSettings.setEnabled(True)
            self.label_audioFile.setEnabled(True)
            self.toolButton_selectAudioFile.setEnabled(True)
            self.lineEdit_audioFile.setEnabled(True)
            self.label_outputFile.setEnabled(True)
            self.toolButton_selectOutputFile.setEnabled(True)
            self.lineEdit_outputFile.setEnabled(True)
            self.pushButton_addComponent.setEnabled(True)
            self.pushButton_removeComponent.setEnabled(True)
            self.pushButton_listMoveDown.setEnabled(True)
            self.pushButton_listMoveUp.setEnabled(True)
            self.pushButton_undo.setEnabled(True)
            self.menuButton_newProject.setEnabled(True)
            self.menuButton_openProject.setEnabled(True)
            self.listWidget_componentList.setEnabled(True)
            self.progressLabel.setHidden(True)
            self.drawPreview(True)

    @QtCore.pyqtSlot(int)
    def progressBarUpdated(self, value):
        self.progressBar_createVideo.setValue(value)

    @QtCore.pyqtSlot(str)
    def progressBarSetText(self, value):
        if sys.platform == "darwin":
            self.progressLabel.setText(value)
        else:
            self.progressBar_createVideo.setFormat(value)

    def updateResolution(self):
        resIndex = int(self.comboBox_resolution.currentIndex())
        res = Core.resolutions[resIndex].split("x")
        changed = res[0] != self.settings.value("outputWidth")
        self.settings.setValue("outputWidth", res[0])
        self.settings.setValue("outputHeight", res[1])
        if changed:
            for i in range(len(self.core.selectedComponents)):
                self.core.updateComponent(i)

    def drawPreview(self, force=False, **kwargs):
        """Use autosave keyword arg to force saving or not saving if needed"""
        self.newTask.emit(self.core.selectedComponents)
        # self.processTask.emit()
        if force or "autosave" in kwargs:
            if force or kwargs["autosave"]:
                self.autosave(True)
        else:
            self.autosave()
        self.updateWindowTitle()

    @QtCore.pyqtSlot("QImage")
    def showPreviewImage(self, image):
        self.previewWindow.changePixmap(image)

    @disableWhenEncoding
    def showUndoStack(self):
        self.undoDialog.show()

    def showHelpWindow(self):
        self.showMessage(msg=f"{appName} v{__version__}")

    def showFfmpegCommand(self):
        command = createFfmpegCommand(
            self.lineEdit_audioFile.text(),
            self.lineEdit_outputFile.text(),
            self.core.selectedComponents,
        )
        command = " ".join(command)
        log.info(f"FFmpeg command: {command}")
        lines = wrap(command, 49)
        self.showMessage(msg=f"Current FFmpeg command:\n\n{' '.join(lines)}")

    def addComponent(self, compPos, moduleIndex):
        """Creates an undoable action that adds a new component."""
        action = AddComponent(self, compPos, moduleIndex)
        self.undoStack.push(action)

    def insertComponent(self, index):
        """Triggered by Core to finish initializing a new component."""
        if not hasattr(self.core.selectedComponents[index], "page"):
            log.error("Component failed to initialize")
            return
        componentList = self.listWidget_componentList
        stackedWidget = self.stackedWidget

        componentList.insertItem(index, self.core.selectedComponents[index].name)
        componentList.setCurrentRow(index)

        # connect to signal that adds an asterisk when modified
        self.core.selectedComponents[index].modified.connect(self.updateComponentTitle)

        self.pages.insert(index, self.core.selectedComponents[index].page)
        stackedWidget.insertWidget(index, self.pages[index])
        stackedWidget.setCurrentIndex(index)

        return index

    def removeComponent(self):
        componentList = self.listWidget_componentList
        selected = componentList.selectedItems()
        if selected:
            action = RemoveComponent(self, selected)
            self.undoStack.push(action)

    def _removeComponent(self, index):
        stackedWidget = self.stackedWidget
        componentList = self.listWidget_componentList
        stackedWidget.removeWidget(self.pages[index])
        componentList.takeItem(index)
        self.core.removeComponent(index)
        self.pages.pop(index)
        self.changeComponentWidget()
        self.drawPreview()

    @disableWhenEncoding
    def moveComponent(self, change):
        """Moves a component relatively from its current position"""
        componentList = self.listWidget_componentList
        tag = change
        if change == "top":
            change = -componentList.currentRow()
        elif change == "bottom":
            change = len(componentList) - componentList.currentRow() - 1
        else:
            tag = "down" if change == 1 else "up"

        row = componentList.currentRow()
        newRow = row + change
        if newRow > -1 and newRow < componentList.count():
            action = MoveComponent(self, row, newRow, tag)
            self.undoStack.push(action)

    def getComponentListMousePos(self, position):
        """
        Given a QPos, returns the component index under the mouse cursor
        or -1 if no component is there.
        """
        componentList = self.listWidget_componentList

        if hasattr(position, "toPointF"):
            position = position.toPointF()
        position = position.toPoint()

        modelIndexes = [
            componentList.model().index(i) for i in range(componentList.count())
        ]
        rects = [componentList.visualRect(modelIndex) for modelIndex in modelIndexes]
        mousePos = [rect.contains(position) for rect in rects]
        if not any(mousePos):
            # Not clicking a component
            mousePos = -1
        else:
            mousePos = mousePos.index(True)
        log.debug("Click component list row %s" % mousePos)
        return mousePos

    @disableWhenEncoding
    def dragComponent(self, event):
        """Used as Qt drop event for the component listwidget"""
        componentList = self.listWidget_componentList
        mousePos = self.getComponentListMousePos(event.position())

        if mousePos > -1:
            change = (componentList.currentRow() - mousePos) * -1
        else:
            change = componentList.count() - componentList.currentRow() - 1
        self.moveComponent(change)

    def changeComponentWidget(self):
        selected = self.listWidget_componentList.selectedItems()
        if selected:
            index = self.listWidget_componentList.row(selected[0])
            self.stackedWidget.setCurrentIndex(index)

    def openPresetManager(self):
        """Preset manager for importing, exporting, renaming, deleting"""
        self.presetManager.show_()

    def clear(self):
        """Get a blank slate"""
        self.core.clearComponents()
        self.listWidget_componentList.clear()
        for widget in self.pages:
            self.stackedWidget.removeWidget(widget)
        self.pages = []
        for field in (self.lineEdit_audioFile, self.lineEdit_outputFile):
            with blockSignals(field):
                field.setText("")
        self.progressBarUpdated(0)
        self.progressBarSetText("")
        self.undoStack.clear()

    @disableWhenEncoding
    def createNewProject(self, prompt=True):
        if prompt:
            self.openSaveChangesDialog("starting a new project")

        self.clear()
        self.currentProject = None
        self.settings.setValue("currentProject", None)
        self.drawPreview(True)

    def saveCurrentProject(self):
        if self.currentProject:
            self.core.createProjectFile(self.currentProject, self)
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
                "Save before %s?"
                % (os.path.basename(self.currentProject)[:-4], phrase),
                showCancel=True,
            )
            if ch:
                success = self.saveProjectChanges()

        if success and os.path.exists(self.autosavePath):
            os.remove(self.autosavePath)

    def openSaveProjectDialog(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Create Project File",
            self.settings.value("projectDir"),
            "Project Files (*.avp)",
        )
        if not filename:
            return
        if not filename.endswith(".avp"):
            filename += ".avp"
        self.settings.setValue("projectDir", os.path.dirname(filename))
        self.settings.setValue("currentProject", filename)
        self.currentProject = filename
        self.core.createProjectFile(filename, self)
        self.updateWindowTitle()

    @disableWhenEncoding
    def openOpenProjectDialog(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Project File",
            self.settings.value("projectDir"),
            "Project Files (*.avp)",
        )
        self.openProject(filename)

    def openProject(self, filepath, prompt=True):
        if (
            not filepath
            or not os.path.exists(filepath)
            or not filepath.endswith(".avp")
        ):
            return

        self.clear()
        # ask to save any changes that are about to get deleted
        if prompt:
            self.openSaveChangesDialog("opening another project")

        self.currentProject = filepath
        self.settings.setValue("currentProject", filepath)
        self.settings.setValue("projectDir", os.path.dirname(filepath))
        # actually load the project using core method
        self.core.openProject(self, filepath)
        self.drawPreview(autosave=False)
        self.updateWindowTitle()

    def showMessage(self, **kwargs):
        parent = kwargs["parent"] if "parent" in kwargs else self
        msg = QtWidgets.QMessageBox(parent)
        msg.setWindowTitle(appName)
        msg.setModal(True)
        msg.setText(kwargs["msg"])
        msg.setIcon(
            eval("QtWidgets.QMessageBox.Icon.%s" % kwargs["icon"])
            if "icon" in kwargs
            else QtWidgets.QMessageBox.Icon.Information
        )
        msg.setDetailedText(kwargs["detail"] if "detail" in kwargs else None)
        if "showCancel" in kwargs and kwargs["showCancel"]:
            msg.setStandardButtons(
                QtWidgets.QMessageBox.StandardButton.Ok
                | QtWidgets.QMessageBox.StandardButton.Cancel
            )
        else:
            msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        ch = msg.exec()
        if ch == 1024:
            return True
        return False

    @disableWhenEncoding
    def componentContextMenu(self, QPos):
        """Appears when right-clicking the component list"""
        componentList = self.listWidget_componentList
        self.menu = QtWidgets.QMenu()
        parentPosition = componentList.mapToGlobal(QtCore.QPoint(0, 0))

        index = self.getComponentListMousePos(QPos)
        if index > -1:
            # Show preset menu if clicking a component
            self.presetManager.findPresets()
            menuItem = self.menu.addAction("Save Preset")
            menuItem.triggered.connect(self.presetManager.openSavePresetDialog)

            # submenu for opening presets
            try:
                presets = self.presetManager.presets[
                    str(self.core.selectedComponents[index])
                ]
                self.presetSubmenu = QtWidgets.QMenu("Open Preset")
                self.menu.addMenu(self.presetSubmenu)

                for version, presetName in presets:
                    menuItem = self.presetSubmenu.addAction(presetName)
                    menuItem.triggered.connect(
                        lambda _, presetName=presetName: self.presetManager.openPreset(
                            presetName
                        )
                    )
            except KeyError:
                pass

            if self.core.selectedComponents[index].currentPreset:
                menuItem = self.menu.addAction("Clear Preset")
                menuItem.triggered.connect(self.presetManager.clearPreset)
            self.menu.addSeparator()

        # "Add Component" submenu
        self.submenu = QtWidgets.QMenu("Add")
        self.menu.addMenu(self.submenu)
        insertCompAtTop = self.settings.value("pref_insertCompAtTop")
        for i, comp in enumerate(self.core.modules):
            menuItem = self.submenu.addAction(comp.Component.name)
            menuItem.triggered.connect(
                lambda _, item=i: self.addComponent(
                    0 if insertCompAtTop else index, item
                )
            )

        self.menu.move(parentPosition + QPos)
        self.menu.show()
