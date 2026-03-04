from pytest import fixture
from pytestqt import qtbot
from avp.gui.presetmanager import PresetManager
from . import getTestDataPath, window


@fixture
def presetmanager(window, qtbot):
    pm = PresetManager(window)
    # ensure presetDir contains test data
    # this is needed when settings are stored in /tmp
    pm.presetDir = getTestDataPath("config/presets")
    pm.findPresets()
    qtbot.addWidget(pm)
    yield pm


def test_presetmanager_list(presetmanager):
    assert presetmanager.presets == {
        "Classic Visualizer": [
            (
                1,
                "testPreset",
            ),
        ],
    }
