import os
import numpy

# core always has to be imported first
import avp.core
from avp.toolkit.ffmpeg import readAudioFile
from pytest import fixture


@fixture
def audioData():
    """Fixture that gives a tuple of (completeAudioArray, duration)"""
    soundFile = getTestDataPath("test.ogg")
    yield readAudioFile(soundFile, MockVideoWorker())


def getTestDataPath(filename):
    """Get path to a file in the ./data directory"""
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(tests_dir, "data", filename)


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
    return numpy.asarray(image, dtype="int32").sum()
