import sys
import pytest
from pytestqt import qtbot
from . import command


def test_commandline_help(qtbot, command):
    sys.argv = ["", "--help"]
    with pytest.raises(SystemExit):
        command.parseArgs()


def test_commandline_help_if_bad_args(qtbot, command):
    sys.argv = ["", "--junk"]
    with pytest.raises(SystemExit):
        command.parseArgs()


def test_commandline_launches_gui_if_verbose(qtbot, command):
    sys.argv = ["", "--verbose"]
    mode = command.parseArgs()
    assert mode == "GUI"


def test_commandline_launches_gui_if_verbose_with_project(qtbot, command):
    sys.argv = ["", "test", "--verbose"]
    mode = command.parseArgs()
    assert mode == "GUI"


def test_commandline_tries_to_export(qtbot, command):
    didCallFunction = False

    def captureFunction(*args):
        nonlocal didCallFunction
        didCallFunction = True

    sys.argv = ["", "-c", "0", "classic", "-i", "_", "-o", "_"]
    command.createAudioVisualization = captureFunction
    command.parseArgs()
    assert didCallFunction


def test_commandline_parses_classic_by_alias(qtbot, command):
    assert command.parseCompName("original") == "Classic Visualizer"


def test_commandline_parses_conway_by_short_name(qtbot, command):
    assert command.parseCompName("conway") == "Conway's Game of Life"


def test_commandline_parses_image_by_name(qtbot, command):
    assert command.parseCompName("image") == "Image"
