from pytestqt import qtbot
from avp.command import Command
from avp.toolkit import blockSignals


def test_blockSignals(qtbot):
    command = Command()
    command.core.insertComponent(0, 0, command)
    comp = command.core.selectedComponents[0]
    assert comp.page.spinBox_scale.signalsBlocked() == False
    with blockSignals(comp.page.spinBox_scale):
        assert comp.page.spinBox_scale.signalsBlocked() == True
    assert comp.page.spinBox_scale.signalsBlocked() == False
