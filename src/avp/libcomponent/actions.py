"""
QUndoCommand classes for undoable user actions performed to a component
"""

from PyQt6 import QtCore
from PyQt6.QtGui import QUndoCommand
from copy import copy
import logging

from ..toolkit.common import blockSignals

log = logging.getLogger(__name__)


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
            attr: (copy(val))
            for attr, val in oldWidgetVals.items()
            if attr in modifiedVals
        }
        self.modifiedVals = {attr: (val) for attr, val in modifiedVals.items()}

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

    def do(self, widgetValues):
        self.parent.setWidgetValues(widgetValues)
        self.parent.update(auto=True, origin="tracked widget update")

    def redo(self):
        if self.undone:
            log.info(
                "Redoing %s #%s tracked widget update",
                self.parent.name,
                self.parent.compPos,
            )
        self.do(self.modifiedVals)

    def undo(self):
        log.info(
            "Undoing %s #%s tracked widget update",
            self.parent.name,
            self.parent.compPos,
        )
        self.undone = True
        self.do(self.oldWidgetVals)


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

    def add(self): ...

    def remove(self): ...


class ComponentSettingsUpdate(QUndoCommand):
    """
    This QUndoCommand represents any change to a component's settings
    not already covered by another action type above.
    A component should define a subclass to define `redo()` and `undo()`,
    manually create instances, and add them to the undoStack when needed.
    """

    def __init__(self, comp):
        super().__init__("change %s component #%s" % (comp.name, comp.compPos))
        self.comp = comp
        self.res = (int(comp.width), int(comp.height))

    def id(self):
        return -1

    def mergeWith(self):
        return True

    def redo(self): ...

    def undo(self): ...


class ComponentPreviewXYClick(ComponentPreviewClick):
    def __init__(self, *args):
        super().__init__(*args)
        self.res = (self.comp.width, self.comp.height)
        self.oldXY = (
            self.comp.floatValForAttr("xPosition", axis=self.res),
            self.comp.floatValForAttr("yPosition", axis=self.res),
        )

    def add(self):
        for pos in self.pos[:]:
            with blockSignals(self.comp):
                self.comp.setRelativeWidget("xPosition", pos[0] / self.size[0])
                self.comp.setRelativeWidget("yPosition", pos[1] / self.size[1])
        self.comp.update(auto=True, origin="ClickPreviewAction")

    def remove(self):
        self.comp.setWidgetValues(
            {
                "xPosition": self.comp.pixelValForAttr(
                    "xPosition", self.oldXY[0], self.res
                ),
                "yPosition": self.comp.pixelValForAttr(
                    "yPosition", self.oldXY[1], self.res
                ),
            }
        )
        self.comp.update(auto=True, origin="ClickPreviewXYAction")


class ComponentCenterXYAction(ComponentSettingsUpdate):
    def __init__(self, comp):
        super().__init__(comp)
        self.oldXY = (
            self.comp.floatValForAttr("xPosition", axis=self.res),
            self.comp.floatValForAttr("yPosition", axis=self.res),
        )

    def redo(self):
        self.comp.centerXY()

    def undo(self):
        self.comp.setWidgetValues(
            {
                "xPosition": self.comp.pixelValForAttr(
                    "xPosition", self.oldXY[0], self.res
                ),
                "yPosition": self.comp.pixelValForAttr(
                    "yPosition", self.oldXY[1], self.res
                ),
            }
        )
        self.comp.update(auto=True, origin="ComponentCenterXYAction")
