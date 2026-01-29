from avp.command import Command
from PyQt6.QtGui import QFont
from pytestqt import qtbot
from pytest import fixture, mark
from . import audioData, command, MockSignal, imageDataSum


@fixture
def coreWithTextComp(qtbot, command):
    """Fixture providing a Command object with Title Text component added"""
    command.core.insertComponent(0, command.core.moduleIndexFor("Title Text"), command)
    yield command.core


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
