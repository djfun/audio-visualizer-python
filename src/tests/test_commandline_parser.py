import sys
import pytest
from .__init__ import command


def test_commandline_help(command):
    sys.argv = ['', '--help']
    with pytest.raises(SystemExit):
        command.parseArgs()


def test_commandline_help_if_bad_args(command):
    sys.argv = ['', '--junk']
    with pytest.raises(SystemExit):
        command.parseArgs()


def test_commandline_launches_gui_if_debug(command):
    sys.argv = ['', '--debug']
    mode = command.parseArgs()
    assert mode == "GUI"


def test_commandline_launches_gui_if_debug_with_project(command):
    sys.argv = ['', 'test', '--debug']
    mode = command.parseArgs()
    assert mode == "GUI"


def test_commandline_export_creates_audio_visualization(command):
    didCallFunction = False
    def captureFunction(*args):
        nonlocal didCallFunction
        didCallFunction = True

    sys.argv = ['', '-c', '0', 'classic', '-i', '_', '-o', '_']
    command.createAudioVisualisation = captureFunction
    command.parseArgs()
    assert didCallFunction
