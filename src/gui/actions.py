'''
    QCommand classes for every undoable user action performed in the MainWindow
'''
from PyQt5.QtWidgets import QUndoCommand


class RemoveComponent(QUndoCommand):
    def __init__(self, parent, selectedRows):
        super().__init__('Remove component')
        self.parent = parent
        componentList = self.parent.window.listWidget_componentList
        self.selectedRows = [
            componentList.row(selected) for selected in selectedRows
        ]
        self.components = [
            parent.core.selectedComponents[i] for i in self.selectedRows
        ]

    def redo(self):
        stackedWidget = self.parent.window.stackedWidget
        componentList = self.parent.window.listWidget_componentList
        for index in self.selectedRows:
            stackedWidget.removeWidget(self.parent.pages[index])
            componentList.takeItem(index)
            self.parent.core.removeComponent(index)
            self.parent.pages.pop(index)
            self.parent.changeComponentWidget()
        self.parent.drawPreview()

    def undo(self):
        componentList = self.parent.window.listWidget_componentList
        for index, comp in zip(self.selectedRows, self.components):
            self.parent.core.insertComponent(
                index, comp, self.parent
            )
        self.parent.drawPreview()

