"""Tests of `actions.py` - MainWindow component list manipulation via undoable actions"""

from PyQt6 import QtCore
import os
from pytest import fixture
from pytestqt import qtbot
from . import getTestDataPath, window


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
