from avp.command import Command
from PyQt6.QtGui import QFont
from pytestqt import qtbot
from pytest import fixture
from . import audioData, MockSignal, imageDataSum


@fixture
def coreWithTextComp(qtbot):
    """Fixture providing a Command object with Title Text component added"""
    command = Command()
    command.core.insertComponent(0, command.core.moduleIndexFor("Title Text"), command)
    yield command.core


def test_comp_text_renderFrame_resize(coreWithTextComp):
    """Call renderFrame of Title Text component added to Command object."""
    comp = coreWithTextComp.selectedComponents[0]
    comp.parent.settings.setValue("outputWidth", 1920)
    comp.parent.settings.setValue("outputHeight", 1080)
    comp.titleFont = QFont("Noto Sans")
    comp.parent.core.updateComponent(0)
    comp.page.lineEdit_textColor.setText("255,255,255")
    image = comp.frameRender(0)
    assert imageDataSum(image) == 2957069


def test_comp_text_renderFrame(coreWithTextComp):
    """Call renderFrame of Title Text component added to Command object."""
    comp = coreWithTextComp.selectedComponents[0]
    comp.parent.settings.setValue("outputWidth", 1280)
    comp.parent.settings.setValue("outputHeight", 720)
    comp.parent.core.updateComponent(0)
    image = comp.frameRender(0)
    assert imageDataSum(image) == 1412293 or 1379298
