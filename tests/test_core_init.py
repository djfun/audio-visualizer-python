import os
from avp.core import Core
from . import getTestDataPath, settings


def test_component_names(settings):
    core = Core()
    assert core.compNames == [
        "Classic Visualizer",
        "Color",
        "Conway's Game of Life",
        "Image",
        "Sound",
        "Spectrum",
        "Title Text",
        "Video",
        "Waveform",
    ]


def test_moduleindex(settings):
    core = Core()
    assert core.moduleIndexFor("Classic Visualizer") == 0


def test_configPath_default():
    configPath = Core.getConfigPath(None)
    assert os.path.basename(configPath) == "audio-visualizer"


def test_configPath_nonstandard():
    assert Core.getConfigPath(getTestDataPath("config")) == getTestDataPath("config")
