"""Tests of MainWindow undoing certain ComponentActions (changes to component settings)"""

from pytest import fixture
from pytestqt import qtbot
from avp.gui.mainwindow import MainWindow
from . import getTestDataPath, window


def test_undo_classic_visualizer_sensitivity(window, qtbot):
    """Undo Classic Visualizer component sensitivity setting
    should undo multiple merged actions."""
    window.core.insertComponent(
        0, window.core.moduleIndexFor("Classic Visualizer"), window
    )
    comp = window.core.selectedComponents[0]
    comp.imagePath = getTestDataPath("inputfiles/test.jpg")
    for i in range(1, 100):
        comp.page.spinBox_scale.setValue(i)
    assert comp.scale == 99
    window.undoStack.undo()
    assert comp.scale == 20


def test_undo_image_scale(window, qtbot):
    """Undo Image component scale setting should undo multiple merged actions."""
    window.core.insertComponent(0, window.core.moduleIndexFor("Image"), window)
    comp = window.core.selectedComponents[0]
    comp.imagePath = getTestDataPath("inputfiles/test.jpg")
    comp.page.spinBox_scale.setValue(100)
    for i in range(10, 401):
        comp.page.spinBox_scale.setValue(i)
    assert comp.scale == 400
    window.undoStack.undo()
    assert comp.scale == 10
    window.undoStack.undo()
    assert comp.scale == 100


def test_undo_image_resizeMode(window, qtbot):
    window.core.insertComponent(0, window.core.moduleIndexFor("Image"), window)
    comp = window.core.selectedComponents[0]
    comp.page.comboBox_resizeMode.setCurrentIndex(1)
    assert not comp.page.spinBox_scale.isEnabled()
    window.undoStack.undo()
    assert comp.page.spinBox_scale.isEnabled()


def test_undo_title_text_merged(window, qtbot):
    """Undoing title text change should undo all recent changes."""
    window.core.insertComponent(0, window.core.moduleIndexFor("Title Text"), window)
    comp = window.core.selectedComponents[0]
    comp.page.lineEdit_title.setText("avp")
    comp.page.lineEdit_title.setText("test")
    window.undoStack.undo()
    assert comp.title == "Text"


def test_undo_title_text_not_merged(window, qtbot):
    """Undoing title text change should undo up to previous different action"""
    window.core.insertComponent(0, window.core.moduleIndexFor("Title Text"), window)
    comp = window.core.selectedComponents[0]
    comp.page.lineEdit_title.setText("avp")
    comp.page.spinBox_xTextAlign.setValue(0)
    comp.page.lineEdit_title.setText("test")
    window.undoStack.undo()
    assert comp.title == "avp"
