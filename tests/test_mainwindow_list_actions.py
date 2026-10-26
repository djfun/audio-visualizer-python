"""Tests of `actions.py` - MainWindow component list manipulation via undoable actions"""

from PyQt6 import QtCore
import pytest
from pytestqt import qtbot
from . import window


def test_mainwindow_addComponent(qtbot, window):
    window.compMenu.actions()[0].trigger()
    assert len(window.core.selectedComponents) == 1


def test_mainwindow_removeComponent(qtbot, window):
    window.compMenu.actions()[0].trigger()  # add component
    window.pushButton_removeComponent.click()  # remove it
    assert len(window.core.selectedComponents) == 0


def test_mainwindow_moveComponent(qtbot, window):
    # add first two components from menu
    window.compMenu.actions()[0].trigger()
    window.compMenu.actions()[1].trigger()
    comp0 = window.core.selectedComponents[0].ui
    window.pushButton_listMoveDown.click()
    # check if 0 is now 1
    assert window.core.selectedComponents[1].ui == comp0


def test_mainwindow_addComponent_undo(qtbot, window):
    window.compMenu.actions()[0].trigger()
    window.undoStack.undo()
    assert len(window.core.selectedComponents) == 0


def test_mainwindow_removeComponent_undo(qtbot, window):
    window.compMenu.actions()[0].trigger()  # add component
    window.pushButton_removeComponent.click()  # remove it
    window.undoStack.undo()
    assert len(window.core.selectedComponents) == 1


def test_mainwindow_moveComponent_undo(qtbot, window):
    # add first two components from menu
    window.compMenu.actions()[0].trigger()
    window.compMenu.actions()[1].trigger()
    comp0 = window.core.selectedComponents[0].ui
    window.pushButton_listMoveDown.click()
    window.undoStack.undo()
    # check if 0 is still 0 after undo
    assert window.core.selectedComponents[1].ui != comp0


def test_mainwindow_componentList_qrect_sizes(qtbot, window):
    """Add two components to MainWindow's componentList and test QRect sizes"""
    window.compMenu.actions()[0].trigger()
    window.compMenu.actions()[1].trigger()
    componentListItem0 = window.listWidget_componentList.model().index(0)
    componentListItem1 = window.listWidget_componentList.model().index(1)
    rect0x, rect0y, rect0w, rect0h = window.listWidget_componentList.visualRect(
        componentListItem0
    ).getRect()
    rect1x, rect1y, rect1w, rect1h = window.listWidget_componentList.visualRect(
        componentListItem1
    ).getRect()

    # only the y coordinate should be different between items in the component list
    assert rect0x == rect1x
    assert rect0y != rect1y
    assert rect0w == rect1w
    assert rect0h == rect1h


@pytest.mark.parametrize("row, movement", ((0, 1), (1, 0)))
def test_mainwindow_dragDropComponent(qtbot, window, row, movement):
    """Add two components to MainWindow's componentList,
    then call dragComponent with a fake QMouseEvent to simulate
    drag-and-drop reordering components in the list"""
    window.compMenu.actions()[0].trigger()
    window.compMenu.actions()[1].trigger()
    comp0 = window.core.selectedComponents[0].ui
    rect0x, rect0y, rect0w, rect0h = window.listWidget_componentList.visualRect(
        window.listWidget_componentList.model().index(0)
    ).getRect()

    class FakeEvent:
        def position(self):
            return QtCore.QPoint(rect0x, rect0y + (rect0h * movement))

    window.listWidget_componentList.setCurrentRow(row)
    assert window.core.selectedComponents[0].ui == comp0
    window.dragComponent(FakeEvent())
    assert window.core.selectedComponents[1].ui == comp0
