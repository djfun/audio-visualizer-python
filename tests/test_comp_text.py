from avp.command import Command
from PyQt6 import QtCore
from PyQt6.QtGui import QFont
from pytestqt import qtbot
from pytest import fixture, mark
from . import audioData, command, window, MockSignal, imageDataSum


@fixture
def coreWithTextComp(qtbot, command):
    """Fixture providing a Command object with Title Text component added"""
    command.core.insertComponent(0, command.core.moduleIndexFor("Title Text"), command)
    yield command.core


@fixture
def windowWithTextComp(qtbot, window):
    window.core.insertComponent(0, window.core.moduleIndexFor("Title Text"), window)
    yield window


def setTextSettings(comp):
    comp.page.spinBox_fontSize.setValue(40)
    comp.page.checkBox_shadow.setChecked(True)
    comp.page.spinBox_shadBlur.setValue(0)
    comp.page.spinBox_shadX.setValue(2)
    comp.page.spinBox_shadY.setValue(-2)
    comp.page.fontComboBox_titleFont.setCurrentFont(QFont("Noto Sans"))
    comp.page.lineEdit_textColor.setText("255,255,255")


@mark.parametrize(
    "width, height",
    ((1920, 1080), (1280, 720)),
)
def test_comp_text_renderFrame(coreWithTextComp, width, height):
    """Call renderFrame of Title Text component added to Command object."""
    comp = coreWithTextComp.selectedComponents[0]
    comp.parent.settings.setValue("outputWidth", width)
    comp.parent.settings.setValue("outputHeight", height)
    setTextSettings(comp)
    comp.centerXY()
    image = comp.frameRender(0)
    assert comp.titleFont.family() == "Noto Sans"
    assert comp.xPosition == width / 2
    assert image.width == width
    assert comp.fontSize == 40
    assert comp.shadX == 2
    assert comp.shadY == -2
    assert comp.shadBlur == 0
    assert imageDataSum(image) == 727403 or 738586


@mark.parametrize("alignment", (0, 1, 2))
def test_comp_text_alignment(coreWithTextComp, alignment):
    comp = coreWithTextComp.selectedComponents[0]
    comp.page.comboBox_textAlign.setCurrentIndex(alignment)
    assert comp.alignment == alignment


@mark.parametrize("pos", ((0, 0), (23, 37), (900, 900)))
def test_comp_text_previewClickEvent_dynamic_assertion(windowWithTextComp, pos):
    comp = windowWithTextComp.core.selectedComponents[0]
    comp.previewClickEvent(pos, (555, 333), QtCore.Qt.MouseButton.LeftButton)
    assert comp.xPosition == comp.pixelValForAttr("xPosition")
    assert comp.yPosition == comp.pixelValForAttr("yPosition")


def test_comp_text_previewClickEvent_static_assertion(windowWithTextComp):
    """Test without using pixelValForAttr method"""
    comp = windowWithTextComp.core.selectedComponents[0]
    comp.previewClickEvent((192, 108), (1920, 1080), QtCore.Qt.MouseButton.LeftButton)
    assert comp.xPosition == 192
    assert comp.yPosition == 108


def test_comp_text_previewClickEvent_undo_redo(windowWithTextComp):
    comp = windowWithTextComp.core.selectedComponents[0]
    oldValue = comp.xPosition
    comp.previewClickEvent((192, 108), (1920, 1080), QtCore.Qt.MouseButton.LeftButton)
    windowWithTextComp.undoStack.undo()
    assert comp.xPosition == oldValue
    windowWithTextComp.undoStack.redo()
    assert comp.xPosition == 192


def test_comp_text_centerText_undo_redo(windowWithTextComp):
    comp = windowWithTextComp.core.selectedComponents[0]
    comp.page.spinBox_xTextAlign.setValue(0)
    comp.page.pushButton_center.click()
    windowWithTextComp.undoStack.undo()
    assert comp.xPosition == 0
    windowWithTextComp.undoStack.redo()
    assert comp.xPosition == comp.pixelValForAttr("xPosition", 0.5)
