import pytest
from avp.core import Core
from avp.command import Command
from avp.toolkit.ffmpeg import createFfmpegCommand
from . import audioData, getTestDataPath, initCore


def test_readAudioFile_data(audioData):
    assert len(audioData[0]) == 218453


def test_readAudioFile_duration(audioData):
    assert audioData[1] == 3.95


@pytest.mark.parametrize("width, height", ((1920, 1080), (1280, 720)))
def test_createFfmpegCommand(width, height):
    initCore()
    command = Command()
    command.settings.setValue("outputWidth", width)
    command.settings.setValue("outputHeight", height)
    ffmpegCmd = createFfmpegCommand("test.ogg", "/tmp", command.core.selectedComponents)
    assert ffmpegCmd == [
        "ffmpeg",
        "-thread_queue_size",
        "512",
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-s",
        "%sx%s" % (width, height),
        "-pix_fmt",
        "rgba",
        "-r",
        "30",
        "-t",
        "0.100",
        "-an",
        "-i",
        "-",
        "-t",
        "0.100",
        "-i",
        "test.ogg",
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-vcodec",
        "libx264",
        "-acodec",
        "aac",
        "-b:v",
        "2500k",
        "-b:a",
        "192k",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "medium",
        "-f",
        "mp4",
        "/tmp",
    ]
