import os
import shutil
from pytest import fixture
from pytestqt import qtbot
from avp.gui.presetmanager import PresetManager
from avp.gui.actions import RenamePreset
from . import getTestDataPath, window


@fixture
def presetmanager(window, qtbot):
    window.core.insertComponent(
        0, window.core.moduleIndexFor("Classic Visualizer"), window
    )
    comp = window.core.selectedComponents[0]
    saveValueStore = comp.savePreset()
    saveValueStore["preset"] = "testPreset"
    window.core.createPresetFile(comp.name, comp.version, "testPreset", saveValueStore)
    window.presetDir = os.path.join(
        os.path.basename(window.core.settings.value("projectDir")), "presets"
    )
    window.presetManager.findPresets()
    qtbot.addWidget(window.presetManager)
    yield window.presetManager


def test_presetmanager_list(presetmanager, qtbot):
    # Must use findPresets() because the preset provided by our setup function
    # wasn't created using the presetmanager's createNewPreset method
    presetmanager.findPresets()
    assert presetmanager.presets == {
        "Classic Visualizer": [
            (
                1,
                "testPreset",
            ),
        ],
    }


def test_presetmanager_rename_preset(presetmanager, qtbot):
    vers = presetmanager.presets["Classic Visualizer"][0][0]
    path = os.path.join(presetmanager.presetDir, "Classic Visualizer", str(vers))
    try:
        presetmanager.renamePreset(path, "testPreset", "testPresetNew")
        assert presetmanager.presets["Classic Visualizer"][0][1] == "testPresetNew"
    finally:
        os.remove(os.path.join(path, "testPresetNew"))


def test_presetmanager_undo_redo_rename_preset(presetmanager, qtbot):
    vers = presetmanager.presets["Classic Visualizer"][0][0]
    path = os.path.join(presetmanager.presetDir, "Classic Visualizer", str(vers))
    action = RenamePreset(presetmanager, path, "testPreset", "testPresetNew")
    presetmanager.parent.undoStack.push(action)
    assert presetmanager.presets["Classic Visualizer"][0][1] == "testPresetNew"
    presetmanager.parent.undoStack.undo()
    assert presetmanager.presets["Classic Visualizer"][0][1] == "testPreset"
    presetmanager.parent.undoStack.redo()
    assert presetmanager.presets["Classic Visualizer"][0][1] == "testPresetNew"
    presetmanager.parent.undoStack.undo()
