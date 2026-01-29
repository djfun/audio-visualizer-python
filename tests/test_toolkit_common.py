from pytest import fixture
from pytestqt import qtbot
from avp.command import Command
from avp.toolkit import blockSignals, rgbFromString
from . import command


@fixture
def gotWarning():
    """Check if a function called log.warning"""
    import avp.toolkit.common as tk

    warning = False

    def gotWarning():
        nonlocal warning
        return warning

    class log:
        def warning(self, *args):
            nonlocal warning
            warning = True

    oldLog = tk.log
    tk.log = log()
    try:
        yield gotWarning
    finally:
        tk.log = oldLog


def test_blockSignals(qtbot, command):
    command.core.insertComponent(0, 0, command)
    comp = command.core.selectedComponents[0]
    assert comp.page.spinBox_scale.signalsBlocked() == False
    with blockSignals(comp.page.spinBox_scale):
        assert comp.page.spinBox_scale.signalsBlocked() == True
    assert comp.page.spinBox_scale.signalsBlocked() == False


def test_rgbFromString(gotWarning):
    assert rgbFromString("255,255,255") == (255, 255, 255)
    assert not gotWarning()


def test_rgbFromString_error(gotWarning):
    assert rgbFromString("255,255,256") == (255, 255, 255)
    assert gotWarning()
