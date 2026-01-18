from avp.command import Command
from pytestqt import qtbot
from pytest import fixture
from . import audioData, MockSignal, imageDataSum, getTestDataPath


sampleSize = 1470  # 44100 / 30 = 1470


@fixture
def coreWithImageComp(qtbot):
    """Fixture providing a Command object with Image component added"""
    command = Command()
    command.core.insertComponent(0, command.core.moduleIndexFor("Image"), command)
    yield command.core


def test_comp_image_set_path(coreWithImageComp):
    "Set imagePath of Image component"
    comp = coreWithImageComp.selectedComponents[0]
    comp.imagePath = getTestDataPath("test.jpg")
    image = comp.previewRender()
    assert imageDataSum(image) == 463711601


def test_comp_image_stretch_scale_120(coreWithImageComp):
    """Image component stretches image to 120%"""
    comp = coreWithImageComp.selectedComponents[0]
    comp.imagePath = getTestDataPath("test.jpg")
    comp.stretched = True
    comp.stretchScale = 120
    image = comp.previewRender()
    assert imageDataSum(image) == 474484783


def test_comp_image_stretch_scale_undo_redo(coreWithImageComp):
    """Image component rapidly changes scale. This test segfaults currently."""
    comp = coreWithImageComp.selectedComponents[0]
    comp.imagePath = getTestDataPath("test.jpg")
    for i in range(100):
        comp.scale = i
        comp.previewRender()
    assert True
