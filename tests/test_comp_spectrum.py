from avp.command import Command
from pytestqt import qtbot
from pytest import fixture, approx
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

    accept_range = 719 #  Accept images with ±0.001% difference
    expected = 71992628 #  This value was extracted on amd64
    assert imageDataSum(image) == approx(expected, abs=accept_range)


def test_comp_spectrum_renderFrame(coreWithSpectrumComp, audioData):
    comp = coreWithSpectrumComp.selectedComponents[0]
    preFrameRender(audioData, comp)
    image = comp.frameRender(0)
    comp.postFrameRender()
    assert imageDataSum(image) == 117
