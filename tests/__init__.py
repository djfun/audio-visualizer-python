import os
import numpy

from avp.core import Core
from avp.command import Command
from avp.gui.mainwindow import MainWindow
from avp.toolkit.ffmpeg import readAudioFile
from pytest import fixture


@fixture
def audioData():
    """Fixture that gives a tuple of (completeAudioArray, duration)"""
    # Core.storeSettings() needed to store ffmpeg bin location
    initCore()
    soundFile = getTestDataPath("inputfiles/test.ogg")
    yield readAudioFile(soundFile, MockVideoWorker())


@fixture
def command(qtbot):
    initCore()
    command = Command()
    command.quit = lambda _: None
    yield command


@fixture
def window(qtbot):
    initCore()
    window = MainWindow(None, None)
    window.clear()
    qtbot.addWidget(window)
    window.settings.setValue("outputWidth", 1920)
    window.settings.setValue("outputHeight", 1080)
    yield window


def getTestDataPath(filename=""):
    """Get path to a file in the ./data directory"""
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(tests_dir, "data", filename)


def initCore():
    testDataDir = getTestDataPath("config")
    unwanted = ["autosave.avp", "settings.ini"]
    for file in unwanted:
        filename = os.path.join(testDataDir, "autosave.avp")
        if os.path.exists(filename):
            os.remove(filename)
    Core.storeSettings(testDataDir)


def preFrameRender(audioData, comp):
    """Prepares a component for calls to frameRender()"""
    comp.preFrameRender(
        audioFile=getTestDataPath("inputfiles/test.ogg"),
        completeAudioArray=audioData[0],
        sampleSize=1470,
        progressBarSetText=MockSignal(),
        progressBarUpdate=MockSignal(),
    )


class MockSignal:
    """Pretends to be a pyqtSignal"""

    def emit(self, *args):
        pass


class MockVideoWorker:
    """Pretends to be a video thread worker"""

    progressBarSetText = MockSignal()
    progressBarUpdate = MockSignal()


def imageDataSum(image):
    """Get sum of raw data of a Pillow Image object"""
    return numpy.asarray(image, dtype="int32").sum(dtype="int32")
