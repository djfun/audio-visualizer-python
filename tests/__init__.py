import os
import tempfile
import numpy

from avp.core import Core
from avp.command import Command
from avp.gui.mainwindow import MainWindow
from avp.toolkit.ffmpeg import readAudioFile
from pytest import fixture


PYTEST_XDIST_WORKER_COUNT = os.environ.get("PYTEST_XDIST_WORKER_COUNT", 0)


@fixture
def settings():
    """Doesn't instantiate core: just calls a static method to store `settings.ini`"""
    initCore()
    yield None


@fixture
def audioData():
    """Fixture that gives a tuple of (completeAudioArray, duration)"""
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
    # patch out any modal dialog that might happen
    MainWindow.showMessage = lambda self, msg, **kwargs: print(msg)
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
    """
    Initializes the Core by creating `settings.ini`
    Returns the temp directory path where settings.ini was created
    or None if multiple pytest workers are not enabled.
    """
    try:
        numWorkers = int(PYTEST_XDIST_WORKER_COUNT)
    except ValueError:
        numWorkers = 0
    if numWorkers > 0:
        # use temporary directories for multiple workers
        # so they don't interfere with each other
        configDir = tempfile.mkdtemp(prefix="avp-config-")
    else:
        # use test data path so we can easily see it after
        # a failed test, and help us understand the config
        configDir = getTestDataPath("config")
    unwanted = ["autosave.avp", "settings.ini"]
    for file in unwanted:
        filename = os.path.join(configDir, "autosave.avp")
        if os.path.exists(filename):
            os.remove(filename)
    Core.storeSettings(configDir)
    return configDir if numWorkers > 0 else None


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
