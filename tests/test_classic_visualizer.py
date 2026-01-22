from avp.command import Command
from pytestqt import qtbot
from pytest import fixture
from . import audioData, MockSignal, imageDataSum


sampleSize = 1470  # 44100 / 30 = 1470


@fixture
def coreWithClassicComp(qtbot):
    """Fixture providing a Command object with Classic Visualizer component added"""
    command = Command()
    command.core.insertComponent(
        0, command.core.moduleIndexFor("Classic Visualizer"), command
    )
    yield command.core


def test_comp_classic_added(coreWithClassicComp):
    """Add Classic Visualizer to core"""
    assert len(coreWithClassicComp.selectedComponents) == 1


def test_comp_classic_removed(coreWithClassicComp):
    """Remove Classic Visualizer from core"""
    coreWithClassicComp.removeComponent(0)
    assert len(coreWithClassicComp.selectedComponents) == 0


def test_comp_classic_drawBars(coreWithClassicComp, audioData):
    """Call drawBars after creating audio spectrum data manually."""

    spectrumArray = {
        0: coreWithClassicComp.selectedComponents[0].transformData(
            0, audioData[0], sampleSize, 0.08, 0.8, None, 20
        )
    }
    for i in range(sampleSize, len(audioData[0]), sampleSize):
        spectrumArray[i] = coreWithClassicComp.selectedComponents[0].transformData(
            i,
            audioData[0],
            sampleSize,
            0.08,
            0.8,
            spectrumArray[i - sampleSize].copy(),
            20,
        )
    image = coreWithClassicComp.selectedComponents[0].drawBars(
        1920, 1080, spectrumArray[sampleSize * 4], (0, 0, 0), 0
    )
    assert imageDataSum(image) == 37872316


def test_comp_classic_drawBars_using_preFrameRender(coreWithClassicComp, audioData):
    """Call drawBars after creating audio spectrum data using preFrameRender."""
    comp = coreWithClassicComp.selectedComponents[0]
    comp.preFrameRender(
        completeAudioArray=audioData[0],
        sampleSize=sampleSize,
        progressBarSetText=MockSignal(),
        progressBarUpdate=MockSignal(),
    )
    image = comp.drawBars(
        1920,
        1080,
        coreWithClassicComp.selectedComponents[0].spectrumArray[sampleSize * 4],
        (0, 0, 0),
        0,
    )
    assert imageDataSum(image) == 37872316
