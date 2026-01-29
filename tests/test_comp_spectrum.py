from avp.command import Command
from pytestqt import qtbot
from pytest import fixture
from . import imageDataSum, command


@fixture
def coreWithSpectrumComp(qtbot, command):
    """Fixture providing a Command object with Spectrum component added"""
    command.settings.setValue("outputHeight", 1080)
    command.settings.setValue("outputWidth", 1920)
    command.core.insertComponent(0, command.core.moduleIndexFor("Spectrum"), command)
    yield command.core


def test_comp_waveform_previewRender(coreWithSpectrumComp):
    comp = coreWithSpectrumComp.selectedComponents[0]
    image = comp.previewRender()
    assert imageDataSum(image) == 71992628
