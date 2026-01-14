import pytest
import os
import sys


def getTestDataPath(filename):
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(tests_dir, "data", filename)


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
