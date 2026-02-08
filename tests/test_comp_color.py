from avp.command import Command
from pytestqt import qtbot
from pytest import fixture
from . import imageDataSum, command


@fixture
def coreWithColorComp(qtbot, command):
    """Fixture providing a Command object with Color component added"""
    command.settings.setValue("outputHeight", 1080)
    command.settings.setValue("outputWidth", 1920)
    command.core.insertComponent(0, command.core.moduleIndexFor("Color"), command)
    yield command.core


def test_comp_color_set_color(coreWithColorComp):
    """Set imagePath of Image component"""
    comp = coreWithColorComp.selectedComponents[0]
    comp.page.lineEdit_color1.setText("111,111,111")
    image = comp.previewRender()
    assert imageDataSum(image) == 1219276800


def test_comp_color_gradient(coreWithColorComp):
    """Test changing fill type to a gradient"""
    comp = coreWithColorComp.selectedComponents[0]
    comp.page.comboBox_fill.setCurrentIndex(1)
    comp.page.lineEdit_color1.setText("0,0,0")
    comp.page.lineEdit_color2.setText("255,255,255")
    image = comp.previewRender()
    assert imageDataSum(image) == 1849285965
