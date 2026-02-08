from avp.command import Command
from pytestqt import qtbot
from pytest import fixture
from . import (
    imageDataSum,
    command,
    preFrameRender,
    audioData,
)


@fixture
def coreWithSpectrumComp(qtbot, command):
    """Fixture providing a Command object with Spectrum component added"""
    command.settings.setValue("outputHeight", 1080)
    command.settings.setValue("outputWidth", 1920)
    command.core.insertComponent(0, command.core.moduleIndexFor("Spectrum"), command)
    yield command.core


def test_comp_spectrum_previewRender(coreWithSpectrumComp):
    comp = coreWithSpectrumComp.selectedComponents[0]
    image = comp.previewRender()
    assert imageDataSum(image) == 71992628


def test_comp_spectrum_renderFrame(coreWithSpectrumComp, audioData):
    comp = coreWithSpectrumComp.selectedComponents[0]
    preFrameRender(audioData, comp)
    image = comp.frameRender(0)
    comp.postFrameRender()
    assert imageDataSum(image) == 117
