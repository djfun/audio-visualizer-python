from ..core import Core


def test_component_names():
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


def test_moduleindex():
    core = Core()
    assert core.moduleIndexFor("Classic Visualizer") == 0
