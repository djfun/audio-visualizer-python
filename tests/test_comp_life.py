from avp.command import Command
from pytestqt import qtbot
from pytest import fixture
from . import imageDataSum


@fixture
def coreWithLifeComp(qtbot):
    """Fixture providing a Command object with Waveform component added"""
    command = Command()
    command.settings.setValue("outputHeight", 1080)
    command.settings.setValue("outputWidth", 1920)
    command.core.insertComponent(0, command.core.moduleIndexFor("Conway's Game of Life"), command)
    yield command.core


def test_comp_life_previewRender(coreWithLifeComp):
    comp = coreWithLifeComp.selectedComponents[0]
    comp.page.lineEdit_color.setText("111,111,111")
    image = comp.previewRender()
    assert imageDataSum(image) == 339814246
