from pytest import fixture
from pytestqt import qtbot
from avp.command import Command
from avp.toolkit import blockSignals, rgbFromString, connectWidget
from . import command


class UnsupportedWidget:
    pass


@fixture
def getLogLevel():
    """Check if a function wrote a log message"""
    import avp.toolkit.common as tk

    logLevel = None

    def gotLogLevel():
        nonlocal logLevel
        return logLevel

    class log:
        def warning(self, *args):
            nonlocal logLevel
            logLevel = "warning"

        def info(self, *args):
            nonlocal logLevel
            logLevel = "info"

        def debug(self, *args):
            nonlocal logLevel
            logLevel = "debug"

    oldLog = tk.log
    tk.log = log()
    try:
        yield gotLogLevel
    finally:
        tk.log = oldLog


def test_blockSignals(qtbot, command):
    command.core.insertComponent(0, 0, command)
    comp = command.core.selectedComponents[0]
    assert comp.page.spinBox_scale.signalsBlocked() == False
    with blockSignals(comp.page.spinBox_scale):
        assert comp.page.spinBox_scale.signalsBlocked() == True
    assert comp.page.spinBox_scale.signalsBlocked() == False


def test_rgbFromString(getLogLevel):
    assert rgbFromString("255,255,255") == (255, 255, 255)
    assert getLogLevel() is None


def test_rgbFromString_log_warning(getLogLevel):
    assert rgbFromString("255,255,256") == (255, 255, 255)
    assert getLogLevel() == "warning"


def test_connectWidget_unsupportedWidget_log_debug(getLogLevel):
    """A known unsupported widget causes a debug message"""

    connectWidget(
        UnsupportedWidget(), lambda: ..., unsupportedWidgets=["UnsupportedWidget"]
    )
    assert getLogLevel() == "debug"


def test_connectWidget_unsupportedWidget_log_info(getLogLevel):
    """An unknown unsupported widget causes an info message"""

    connectWidget(UnsupportedWidget(), lambda: ...)
    assert getLogLevel() == "info"
