from pytestqt import qtbot
from pytest import fixture
from avp.toolkit.ffmpeg import checkFfmpegVersion
from . import command, imageDataSum, audioData, preFrameRender


@fixture
def coreWithWaveformComp(qtbot, command):
    """Fixture providing a Command object with Waveform component added"""
    command.settings.setValue("outputWidth", 1920)
    command.settings.setValue("outputHeight", 1080)
    command.core.insertComponent(0, command.core.moduleIndexFor("Waveform"), command)
    yield command.core


def test_comp_waveform_setColor(coreWithWaveformComp):
    comp = coreWithWaveformComp.selectedComponents[0]
    comp.page.lineEdit_color.setText("255,255,255")
    assert comp.color == (255, 255, 255)


def test_comp_waveform_previewRender(coreWithWaveformComp):
    comp = coreWithWaveformComp.selectedComponents[0]
    comp.page.lineEdit_color.setText("255,255,255")
    _, version = checkFfmpegVersion()
    if version > 6:
        # FFmpeg 8 has different colors from 6
        # TODO check version 7
        assert imageDataSum(comp.previewRender()) == 36114120
    else:
        assert imageDataSum(comp.previewRender()) == 37210620


def test_comp_waveform_renderFrame(coreWithWaveformComp, audioData):
    comp = coreWithWaveformComp.selectedComponents[0]
    comp.page.lineEdit_color.setText("255,255,255")
    preFrameRender(audioData, comp)
    image = comp.frameRender(0)
    comp.postFrameRender()
    assert imageDataSum(image) == 8331360
