import pytest
import os
import sys
from ..core import Core
from ..command import Command


@pytest.fixture
def core():
    return Core()


@pytest.fixture
def command():
    """Like a MainWindow for commandline mode, this owns the Core"""
    return Command()


def run(logFile):
    """Run Pytest, which then imports and runs all tests in this module."""
    with open(logFile, "w") as f:
        # temporarily redirect stdout to a text file so we capture pytest's output
        sys.stdout = f
        try:
            val = pytest.main([
                os.path.dirname(__file__),
                "-s", # disable pytest's internal capturing of stdout etc.
            ])
        finally:
            sys.stdout = sys.__stdout__

        return val
