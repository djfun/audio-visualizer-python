'''
    QCommand classes for every undoable user action performed in the MainWindow
'''
from PyQt5.QtWidgets import QUndoCommand


class AddComponent(QUndoCommand):
    def __init__(self, parent, compI, moduleI):
        super().__init__(
            "New %s component" %
            parent.core.modules[moduleI].Component.name
        )
        self.parent = parent
        self.moduleI = moduleI
        self.compI = compI

    def redo(self):
        self.parent.core.insertComponent(self.compI, self.moduleI, self.parent)

    def undo(self):
        self.parent._removeComponent(self.compI)


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
        self.parent._removeComponent(self.selectedRows[0])

    def undo(self):
        componentList = self.parent.window.listWidget_componentList
        for index, comp in zip(self.selectedRows, self.components):
            self.parent.core.insertComponent(
                index, comp, self.parent
            )
        self.parent.drawPreview()


class MoveComponent(QUndoCommand):
    def __init__(self, parent, row, newRow, tag):
        super().__init__("Move component %s" % tag)
        self.parent = parent
        self.row = row
        self.newRow = newRow
        self.id_ = ord(tag[0])

    def id(self):
        '''If 2 consecutive updates have same id, Qt will call mergeWith()'''
        return self.id_

    def mergeWith(self, other):
        self.newRow = other.newRow
        return True

    def do(self, rowa, rowb):
        componentList = self.parent.window.listWidget_componentList

        page = self.parent.pages.pop(rowa)
        self.parent.pages.insert(rowb, page)

        item = componentList.takeItem(rowa)
        componentList.insertItem(rowb, item)

        stackedWidget = self.parent.window.stackedWidget
        widget = stackedWidget.removeWidget(page)
        stackedWidget.insertWidget(rowb, page)
        componentList.setCurrentRow(rowb)
        stackedWidget.setCurrentIndex(rowb)
        self.parent.core.moveComponent(rowa, rowb)
        self.parent.drawPreview(True)

    def redo(self):
        self.do(self.row, self.newRow)

    def undo(self):
        self.do(self.newRow, self.row)


class ClearPreset(QUndoCommand):
    def __init__(self, parent, compI):
        super().__init__("Clear preset")
        self.parent = parent
        self.compI = compI
        self.component = self.parent.core.selectedComponents[compI]
        self.store = self.component.savePreset()
        self.store['preset'] = self.component.currentPreset

    def redo(self):
        self.parent.core.clearPreset(self.compI)
        self.parent.updateComponentTitle(self.compI, False)

    def undo(self):
        self.parent.core.selectedComponents[self.compI].loadPreset(self.store)
        self.parent.updateComponentTitle(self.compI, self.store)
