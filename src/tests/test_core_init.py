from .__init__ import core


def test_component_names(core):
    assert core.compNames == [
        'Classic Visualizer',
        'Color',
        "Conway's Game of Life",
        'Image',
        'Sound',
        'Spectrum',
        'Title Text',
        'Video',
        'Waveform',
    ]


def test_moduleindex(core):
    assert core.moduleIndexFor("Classic Visualizer") == 0
