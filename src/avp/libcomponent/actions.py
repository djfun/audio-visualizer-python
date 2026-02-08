"""
QUndoCommand class for generic undoable user actions performed to a BaseComponent

See `../life.py` for an example of a component that uses a custom QUndoCommand
"""

from PyQt6.QtGui import QUndoCommand
from copy import copy
import logging

log = logging.getLogger("AVP.ComponentHandler")


class ComponentUpdate(QUndoCommand):
    """Command object for making a component action undoable"""

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
