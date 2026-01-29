from pytestqt import qtbot
from pytest import fixture
from . import command


@fixture
def coreWithWaveformComp(qtbot, command):
    """Fixture providing a Command object with Waveform component added"""
    command.core.insertComponent(0, command.core.moduleIndexFor("Waveform"), command)
    yield command.core


def test_comp_waveform_setColor(coreWithWaveformComp):
    comp = coreWithWaveformComp.selectedComponents[0]
    comp.page.lineEdit_color.setText("255,255,255")
    assert comp.color == (255, 255, 255)
