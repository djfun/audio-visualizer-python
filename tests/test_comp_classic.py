from avp.toolkit.visualizer import transformData
from pytestqt import qtbot
from pytest import fixture, mark
from . import audioData, command, imageDataSum, preFrameRender


sampleSize = 1470  # 44100 / 30 = 1470


def createSpectrumArray(audioData):
    """Creates enough `spectrumArray` for one call to Component.drawBars()"""
    spectrumArray = {0: transformData(0, audioData[0], sampleSize, 0.08, 0.8, None, 20)}
    for i in range(sampleSize, len(audioData[0]), sampleSize):
        spectrumArray[i] = transformData(
            i,
            audioData[0],
            sampleSize,
            0.08,
            0.8,
            spectrumArray[i - sampleSize].copy(),
            20,
        )
    return spectrumArray


@fixture
def coreWithClassicComp(qtbot, command):
    """Fixture providing a Command object with Classic Visualizer component added"""
    command.core.insertComponent(
        0, command.core.moduleIndexFor("Classic Visualizer"), command
    )
    yield command.core


def test_comp_classic_added(coreWithClassicComp):
    """Add Classic Visualizer to core"""
    assert len(coreWithClassicComp.selectedComponents) == 1


def test_comp_classic_removed(coreWithClassicComp):
    """Remove Classic Visualizer from core"""
    coreWithClassicComp.removeComponent(0)
    assert len(coreWithClassicComp.selectedComponents) == 0


@mark.parametrize("layout", (0, 1, 2, 3))
def test_comp_classic_drawBars(coreWithClassicComp, audioData, layout):
    """Call drawBars after creating audio spectrum data manually."""
    spectrumArray = createSpectrumArray(audioData)
    comp = coreWithClassicComp.selectedComponents[0]
    image = comp.drawBars(
        1920, 1080, spectrumArray[sampleSize * 4], (0, 0, 0), layout, None
    )
    imageSize = 37872316
    assert imageDataSum(image) == imageSize if layout < 2 else imageSize / 2


def test_comp_classic_drawBars_using_preFrameRender(coreWithClassicComp, audioData):
    """Call drawBars after creating audio spectrum data using preFrameRender."""
    comp = coreWithClassicComp.selectedComponents[0]
    preFrameRender(audioData, comp)
    image = comp.drawBars(
        1920,
        1080,
        coreWithClassicComp.selectedComponents[0].spectrumArray[sampleSize * 4],
        (0, 0, 0),
        0,
        None,
    )
    assert imageDataSum(image) == 37872316


def test_comp_classic_command_layout(coreWithClassicComp):
    comp = coreWithClassicComp.selectedComponents[0]
    comp.command("layout=top")
    assert comp.layout == 3


def test_comp_classic_command_color(coreWithClassicComp):
    comp = coreWithClassicComp.selectedComponents[0]
    comp.command("color=111,111,111")
    assert comp.visColor == (111, 111, 111)


def test_comp_classic_command_preset(coreWithClassicComp):
    comp = coreWithClassicComp.selectedComponents[0]
    saveValueStore = comp.savePreset()
    saveValueStore["preset"] = "testPreset"
    coreWithClassicComp.createPresetFile(
        comp.name, comp.version, "testPreset", saveValueStore
    )
    comp.command("preset=testPreset")
    assert comp.currentPreset == "testPreset"


def test_comp_classic_loadPreset(coreWithClassicComp):
    comp = coreWithClassicComp.selectedComponents[0]
    comp.scale = 99
    saveValueStore = comp.savePreset()
    saveValueStore["preset"] = "testPreset"
    comp.scale = 20
    comp.loadPreset(saveValueStore, "testPreset")
    assert comp.scale == 99
