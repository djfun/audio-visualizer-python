from PyQt6.QtCore import pyqtSignal
import numpy
from avp.core import Core
from avp.command import Command
from pytestqt import qtbot
from pytest import fixture
from . import audioData, mockSignal


sampleSize = 1470  # 44100 / 30 = 1470


@fixture
def coreWithClassicComp(qtbot):
    command = Command()
    command.core.insertComponent(
        0, command.core.moduleIndexFor("Classic Visualizer"), command
    )
    yield command.core


def test_comp_classic_added(coreWithClassicComp):
    """Test adding Classic Visualizer to core"""
    assert len(coreWithClassicComp.selectedComponents) == 1


def test_comp_classic_removed(coreWithClassicComp):
    """Test removing Classic Visualizer from core"""
    coreWithClassicComp.removeComponent(0)
    assert len(coreWithClassicComp.selectedComponents) == 0


def test_comp_classic_drawBars(coreWithClassicComp, audioData):
    lastSpectrum = coreWithClassicComp.selectedComponents[0].transformData(
        0, audioData[0], sampleSize, 0.08, 0.8, None
    )
    spectrum = {0: lastSpectrum.copy()}
    spectrum[sampleSize] = (
        coreWithClassicComp.selectedComponents[0]
        .transformData(0, audioData[0], sampleSize, 0.08, 0.8, spectrum[0])
        .copy()
    )
    image = coreWithClassicComp.selectedComponents[0].drawBars(
        1920, 1080, spectrum[0], (0, 0, 0), 0
    )
    data = numpy.asarray(image, dtype="int32")
    assert data.sum() == 14654498


def test_comp_classic_drawBars_using_preFrameRender(coreWithClassicComp, audioData):
    comp = coreWithClassicComp.selectedComponents[0]
    numpy.seterr(divide="ignore")
    comp.preFrameRender(
        completeAudioArray=audioData[0],
        sampleSize=sampleSize,
        progressBarSetText=mockSignal(),
        progressBarUpdate=mockSignal(),
    )
    image = comp.drawBars(
        1920,
        1080,
        coreWithClassicComp.selectedComponents[0].spectrumArray[0],
        (0, 0, 0),
        0,
    )
    data = numpy.asarray(image, dtype="int32")
    assert data.sum() == 14654498
