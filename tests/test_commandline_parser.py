import sys
import pytest
from avp.command import Command


def test_commandline_help():
    command = Command()
    sys.argv = ["", "--help"]
    with pytest.raises(SystemExit):
        command.parseArgs()


def test_commandline_help_if_bad_args():
    command = Command()
    sys.argv = ["", "--junk"]
    with pytest.raises(SystemExit):
        command.parseArgs()


def test_commandline_launches_gui_if_debug():
    command = Command()
    sys.argv = ["", "--debug"]
    mode = command.parseArgs()
    assert mode == "GUI"


def test_commandline_launches_gui_if_debug_with_project():
    command = Command()
    sys.argv = ["", "test", "--debug"]
    mode = command.parseArgs()
    assert mode == "GUI"


def test_commandline_tries_to_export():
    command = Command()
    didCallFunction = False

    def captureFunction(*args):
        nonlocal didCallFunction
        didCallFunction = True

    sys.argv = ["", "-c", "0", "classic", "-i", "_", "-o", "_"]
    command.createAudioVisualization = captureFunction
    command.parseArgs()
    assert didCallFunction
