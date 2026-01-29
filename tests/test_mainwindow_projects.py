from pytest import fixture
from pytestqt import qtbot
from . import getTestDataPath, window


def test_mainwindow_clear(qtbot, window):
    """MainWindow.clear() gives us a clean slate"""
    assert len(window.core.selectedComponents) == 0


def test_mainwindow_openProject(qtbot, window):
    """Open testproject.avp using MainWindow.openProject()"""
    window.openProject(getTestDataPath("projects/testproject.avp"), prompt=False)
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
