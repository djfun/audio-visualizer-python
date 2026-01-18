import os
from pytest import fixture


def getTestDataPath(filename):
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(tests_dir, "data", filename)


@fixture
def audioData():
    from avp.toolkit.ffmpeg import readAudioFile

    soundFile = getTestDataPath("test.ogg")
    yield readAudioFile(soundFile, None)


class mockSignal:
    def emit(self, *args):
        pass
