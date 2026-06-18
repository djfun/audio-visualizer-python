"""
Tests of MainWindow undoing certain ComponentTrackedWidgetUpdates
"""

from PyQt6 import QtCore
from avp.toolkit.common import isVerticalWord
from pytest import fixture, mark
from pytestqt import qtbot
from avp.gui.mainwindow import MainWindow
from . import getTestDataPath, window


def test_undo_stack_size_after_3_trackedWidgetUpdates(window, qtbot):
    window.core.insertComponent(
        0, window.core.moduleIndexFor("Classic Visualizer"), window
    )
    comp = window.core.selectedComponents[0]
    comp.page.spinBox_scale.setValue(99)
    comp.page.spinBox_y.setValue(100)
    comp.page.spinBox_scale.setValue(50)
    assert window.undoStack.count() == 3


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


def test_undo_randomColor_is_saved(window, qtbot):
    window.addComponent(0, window.core.moduleIndexFor("Color"))
    comp = window.core.selectedComponents[0]
    randomText = comp.page.lineEdit_color1.text()
    randomTuple = comp.color1
    window.undoStack.undo()
    window.undoStack.redo()
    comp = window.core.selectedComponents[0]
    assert comp.page.lineEdit_color1.text() == randomText
    assert comp.color1 == randomTuple


@mark.parametrize("compName", ("Title Text", "Image"))
def test_comp_undo_centerXYAction_through_resolution_change(window, qtbot, compName):
    """Test if CenterTextAction works properly with changes to resolution"""
    window.core.insertComponent(0, window.core.moduleIndexFor(compName), window)
    comp = window.core.selectedComponents[0]
    if compName == "Image":
        comp.imageSize = (1, 1)
    widget = comp._trackedWidgets["xPosition"]
    widget.setValue(450)
    window.updateResolution(1)
    resizedX = comp.xPosition
    comp.addCenterAction()
    centeredX = comp.xPosition
    widget.setValue(333)
    window.undoStack.undo()
    assert comp.xPosition == centeredX
    # undo centering
    window.undoStack.undo()
    assert comp.xPosition == resizedX
    # undo change of resolution
    window.undoStack.undo()
    assert comp.xPosition == 450


@mark.parametrize("compName", ("Title Text", "Image"))
@mark.parametrize("attr", ("xPosition", "yPosition"))
def test_comp_undo_previewXYClick_through_resolution_change(
    window, qtbot, compName, attr
):
    """Test if PreviewClickAction works properly with changes to resolution"""
    window.core.insertComponent(0, window.core.moduleIndexFor(compName), window)
    comp = window.core.selectedComponents[0]
    widget = comp._trackedWidgets[attr]
    valueAt1080 = 450

    # value from which x, y would be offset (for components not anchored at x, y)
    offset = (100, 100)
    if compName == "Image":
        comp.imageSize = offset
    useOffset = compName in ("Image")

    # Set widget value at 1920x1080
    widget.setValue(valueAt1080)
    # Change resolution to 1280x720
    window.updateResolution(1)
    # Remember resized widget value
    valueAt720 = getattr(comp, attr)
    # Send previewClickEvent at 1/10th of resolution
    comp.previewClickEvent((128, 72), (1280, 720), QtCore.Qt.MouseButton.LeftButton)
    assert getattr(comp, attr) == (72 if isVerticalWord(attr) else 128) - (
        (int(offset[1 if isVerticalWord(attr) else 0] / 2) if useOffset else 0)
    )

    # Undo previewClickEvent
    window.undoStack.undo()
    assert getattr(comp, attr) == valueAt720

    # Undo resolution change, returning to 1920x1080
    window.undoStack.undo()
    assert getattr(comp, attr) == valueAt1080
