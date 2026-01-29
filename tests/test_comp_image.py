from avp.command import Command
from pytestqt import qtbot
from pytest import fixture
from . import audioData, command, MockSignal, imageDataSum, getTestDataPath


sampleSize = 1470  # 44100 / 30 = 1470


@fixture
def coreWithImageComp(qtbot, command):
    """Fixture providing a Command object with Image component added"""
    command.settings.setValue("outputHeight", 1080)
    command.settings.setValue("outputWidth", 1920)
    command.core.insertComponent(0, command.core.moduleIndexFor("Image"), command)
    yield command.core


def test_comp_image_set_path(coreWithImageComp):
    "Set imagePath of Image component"
    comp = coreWithImageComp.selectedComponents[0]
    comp.imagePath = getTestDataPath("inputfiles/test.jpg")
    image = comp.previewRender()
    assert imageDataSum(image) == 463711601


def test_comp_image_scale_50_1080p(coreWithImageComp):
    """Image component stretches image to 50% at 1080p"""
    comp = coreWithImageComp.selectedComponents[0]
    comp.imagePath = getTestDataPath("inputfiles/test.jpg")
    image = comp.previewRender()
    sum = imageDataSum(image)
    comp.page.spinBox_scale.setValue(50)
    assert imageDataSum(comp.previewRender()) - sum / 4 < 2000


def test_comp_image_scale_50_720p(coreWithImageComp):
    """Image component stretches image to 50% at 720p"""
    comp = coreWithImageComp.selectedComponents[0]
    comp.imagePath = getTestDataPath("inputfiles/test.jpg")
    comp.page.spinBox_scale.setValue(50)
    image = comp.previewRender()
    sum = imageDataSum(image)
    comp.parent.settings.setValue("outputHeight", 720)
    comp.parent.settings.setValue("outputWidth", 1280)
    newImage = comp.previewRender()
    assert image.width == 1920
    assert newImage.width == 1280
    assert imageDataSum(comp.previewRender()) == sum
