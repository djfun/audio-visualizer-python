import pytest
import os
import sys
from ..core import Core


def getTestDataPath(filename):
    return os.path.join(Core.wd, "tests", "data", filename)


def run(logFile):
    """Run Pytest, which then imports and runs all tests in this module."""
    os.environ["PYTEST_QT_API"] = "PyQt6"
    with open(logFile, "w") as f:
        # temporarily redirect stdout to a text file so we capture pytest's output
        sys.stdout = f
        try:
            val = pytest.main(
                [
                    os.path.dirname(__file__),
                    "-s",  # disable pytest's internal capturing of stdout etc.
                ]
            )
        finally:
            sys.stdout = sys.__stdout__

        return val
