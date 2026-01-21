from pytestqt import qtbot
from avp.gui.mainwindow import MainWindow
from . import getTestDataPath


def test_undo_image_scale(qtbot):
    """Undo Image component scale setting should undo multiple merged actions."""
    qtbot.addWidget(window := MainWindow(None, None))
    window.settings.setValue("outputWidth", 1920)
    window.settings.setValue("outputHeight", 1080)
    window.core.insertComponent(0, window.core.moduleIndexFor("Image"), window)
    comp = window.core.selectedComponents[0]
    comp.imagePath = getTestDataPath("test.jpg")
    comp.page.spinBox_scale.setValue(100)
    for i in range(10, 401):
        comp.page.spinBox_scale.setValue(i)
    assert comp.scale == 400
    window.undoStack.undo()
    assert comp.scale == 10
    window.undoStack.undo()
    assert comp.scale == 100


def test_undo_classic_visualizer_sensitivity(qtbot):
    """Undo Classic Visualizer component sensitivity setting
    should undo multiple merged actions."""
    qtbot.addWidget(window := MainWindow(None, None))
    window.core.insertComponent(
        0, window.core.moduleIndexFor("Classic Visualizer"), window
    )
    comp = window.core.selectedComponents[0]
    comp.imagePath = getTestDataPath("test.jpg")
    for i in range(1, 100):
        comp.page.spinBox_scale.setValue(i)
    assert comp.scale == 99
    window.undoStack.undo()
    assert comp.scale == 20
