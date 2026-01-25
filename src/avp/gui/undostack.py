from PyQt6.QtGui import QUndoStack
from ..toolkit.common import disableWhenEncoding


class UndoStack(QUndoStack):
    @property
    def encoding(self):
        return self.parent().encoding

    @disableWhenEncoding
    def undo(self, *args, **kwargs):
        super().undo(*args, **kwargs)

    @disableWhenEncoding
    def redo(self, *args, **kwargs):
        super().redo(*args, **kwargs)
