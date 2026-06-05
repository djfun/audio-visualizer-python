"""
QUndoCommand class for generic undoable user actions performed to a BaseComponent

See `../life.py` for an example of a component that uses a custom QUndoCommand
"""

from PyQt6 import QtCore
from PyQt6.QtGui import QUndoCommand
from copy import copy
import logging

log = logging.getLogger("AVP.ComponentHandler")


class ComponentTrackedWidgetUpdate(QUndoCommand):
    """
    This QUndoCommand represents value changes in a component's `page` (its UI widget)
    It is used by the BaseComponent class for input widgets tracked by `trackWidgets()`
    """

    def __init__(self, parent, oldWidgetVals, modifiedVals):
        super().__init__("change %s component #%s" % (parent.name, parent.compPos))
        self.undone = False
        self.res = (int(parent.width), int(parent.height))
        self.parent = parent
        self.oldWidgetVals = {
            attr: (
                copy(val)
                if attr not in self.parent._relativeWidgets
                else self.parent.floatValForAttr(attr, val, axis=self.res)
            )
            for attr, val in oldWidgetVals.items()
            if attr in modifiedVals
        }
        self.modifiedVals = {
            attr: (
                val
                if attr not in self.parent._relativeWidgets
                else self.parent.floatValForAttr(attr, val, axis=self.res)
            )
            for attr, val in modifiedVals.items()
        }

        # Because relative widgets change themselves every update based on
        # their previous value, we must store ALL their values in case of undo
        self.relativeWidgetValsAfterUndo = {
            attr: copy(getattr(self.parent, attr))
            for attr in self.parent._relativeWidgets
        }

        # Determine if this update is mergeable
        self.id_ = -1
        if self.parent.mergeUndo:
            if len(self.modifiedVals) == 1:
                attr, val = self.modifiedVals.popitem()
                self.id_ = sum([ord(letter) for letter in attr[-14:]])
                self.modifiedVals[attr] = val
                return
            log.warning(
                "%s component settings changed at once. (%s)",
                len(self.modifiedVals),
                repr(self.modifiedVals),
            )

    def id(self):
        """If 2 consecutive updates have same id, Qt will call mergeWith()"""
        return self.id_

    def mergeWith(self, other):
        self.modifiedVals.update(other.modifiedVals)
        return True

    def setWidgetValues(self, attrDict):
        """
        Mask the component's usual method to handle our
        relative widgets in case the resolution has changed.
        """
        newAttrDict = {
            attr: (
                val
                if attr not in self.parent._relativeWidgets
                else self.parent.pixelValForAttr(attr, val)
            )
            for attr, val in attrDict.items()
        }
        self.parent.setWidgetValues(newAttrDict)

    def redo(self):
        if self.undone:
            log.info("Redoing component update")
        self.parent.oldAttrs = self.relativeWidgetValsAfterUndo
        self.setWidgetValues(self.modifiedVals)
        self.parent.update(auto=True)
        self.parent.oldAttrs = None
        if not self.undone:
            self.relativeWidgetValsAfterRedo = {
                attr: copy(getattr(self.parent, attr))
                for attr in self.parent._relativeWidgets
            }
            self.parent._sendUpdateSignal()

    def undo(self):
        log.info("Undoing component update")
        self.undone = True
        self.parent.oldAttrs = self.relativeWidgetValsAfterRedo
        self.setWidgetValues(self.oldWidgetVals)
        self.parent.update(auto=True)
        self.parent.oldAttrs = None


class ComponentPreviewClick(QUndoCommand):
    """
    This QUndoCommand represents the user clicking the preview window.
    A component that responds to preview click events must define a subclass
    which defines `add()` and `remove()` to respond to left and right mouse buttons.
    This component should then create instances of its subclass and
    add them to the undoStack within a `previewClickEvent` method.
    """

    def __init__(self, comp, pos, size, button):
        super().__init__("click %s component #%s" % (comp.name, comp.compPos))
        self.comp = comp
        self.pos = [pos]
        self.size = size
        if button == QtCore.Qt.MouseButton.RightButton:
            self.button = 2
        else:
            self.button = 1

    def id(self):
        return self.button

    def mergeWith(self, other):
        self.pos.extend(other.pos)
        return True

    def add(self):
        ...

    def remove(self):
        ...

    def redo(self):
        if self.button == 1:  # Left-click
            self.add()
        elif self.button == 2:  # Right-click
            self.remove()

    def undo(self):
        if self.button == 1:  # Left-click
            self.remove()
        elif self.button == 2:  # Right-click
            self.add()