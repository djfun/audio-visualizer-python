import sys
import os
import tempfile
from ..command import Command
from . import getTestDataPath
from pytestqt import qtbot


def test_commandline_classic_export(qtbot):
    """Run Qt event loop and create a video in the system /tmp or /temp"""
    soundFile = getTestDataPath("test.ogg")
    outputDir = tempfile.mkdtemp(prefix="avp-test-")
    outputFilename = os.path.join(outputDir, "output.mp4")
    sys.argv = [
        "",
        "-c",
        "0",
        "classic",
        "-i",
        soundFile,
        "-o",
        outputFilename,
    ]

    command = Command()
    command.quit = lambda _: None
    command.parseArgs()
    # Command object now has a video_thread Worker which is exporting the video

    with qtbot.waitSignal(command.worker.videoCreated, timeout=10000):
        """
        Wait until videoCreated is emitted by the video_thread Worker
        or until 10 second timeout has passed
        """
        print(f"Test Video created at {outputFilename}")

    assert os.path.exists(outputFilename)
    # output video should be at least 200kb
    assert os.path.getsize(outputFilename) > 200000
