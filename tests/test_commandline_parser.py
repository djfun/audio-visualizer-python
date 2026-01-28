import sys
import pytest
from avp.command import Command
from pytestqt import qtbot


def test_commandline_help(qtbot):
    command = Command()
    sys.argv = ["", "--help"]
    with pytest.raises(SystemExit):
        command.parseArgs()


def test_commandline_help_if_bad_args(qtbot):
    command = Command()
    sys.argv = ["", "--junk"]
    with pytest.raises(SystemExit):
        command.parseArgs()


def test_commandline_launches_gui_if_verbose(qtbot):
    command = Command()
    sys.argv = ["", "--verbose"]
    mode = command.parseArgs()
    assert mode == "GUI"


def test_commandline_launches_gui_if_verbose_with_project(qtbot):
    command = Command()
    sys.argv = ["", "test", "--verbose"]
    mode = command.parseArgs()
    assert mode == "GUI"


def test_commandline_tries_to_export(qtbot):
    command = Command()
    didCallFunction = False

    def captureFunction(*args):
        nonlocal didCallFunction
        didCallFunction = True

    sys.argv = ["", "-c", "0", "classic", "-i", "_", "-o", "_"]
    command.createAudioVisualization = captureFunction
    command.parseArgs()
    assert didCallFunction


def test_commandline_parses_classic_by_alias(qtbot):
    command = Command()
    assert command.parseCompName("original") == "Classic Visualizer"


def test_commandline_parses_conway_by_short_name(qtbot):
    command = Command()
    assert command.parseCompName("conway") == "Conway's Game of Life"


def test_commandline_parses_image_by_name(qtbot):
    command = Command()
    assert command.parseCompName("image") == "Image"
