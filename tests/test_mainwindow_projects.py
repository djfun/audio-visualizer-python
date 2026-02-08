from PyQt6 import QtCore
import os
from pytest import fixture
from pytestqt import qtbot
from avp.gui.mainwindow import MainWindow
from . import getTestDataPath, window, settings


def test_mainwindow_init_with_project(qtbot, settings):
    window = MainWindow(getTestDataPath("config/projects/testproject.avp"), None)
    qtbot.addWidget(window)
    assert window.core.selectedComponents[0].name == "Classic Visualizer"
    assert window.core.selectedComponents[1].name == "Color"


def test_mainwindow_clear(qtbot, window):
    """MainWindow.clear() gives us a clean slate"""
    assert len(window.core.selectedComponents) == 0


def test_mainwindow_presetDir_in_tests(qtbot, window):
    """`presetDir` is the filepath on which "Import Preset" file picker opens"""
    assert os.path.basename(window.core.settings.value("presetDir")) == "presets"


def test_mainwindow_openProject(qtbot, window):
    """Open testproject.avp using MainWindow.openProject()"""
    window.openProject(getTestDataPath("config/projects/testproject.avp"), prompt=False)
    assert len(window.core.selectedComponents) == 2


def test_mainwindow_newProject_without_unsaved_changes(qtbot, window):
    """Starting new project without unsaved changes"""
    didCallFunction = False

    def captureFunction(*args, **kwargs):
        nonlocal didCallFunction
        didCallFunction = True

    window.createNewProject(prompt=False)
    assert not didCallFunction
    assert len(window.core.selectedComponents) == 0


def test_mainwindow_newProject_with_unsaved_changes(qtbot, window):
    """Starting new project with unsaved changes"""
    didCallFunction = False

    def captureFunction(*args, **kwargs):
        nonlocal didCallFunction
        didCallFunction = True

    window.openSaveChangesDialog = captureFunction
    window.createNewProject(prompt=True)
    assert didCallFunction
