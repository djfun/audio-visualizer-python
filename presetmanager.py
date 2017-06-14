from PyQt4 import QtGui, QtCore
import string
import os

import core


class PresetManager(QtGui.QDialog):
    def __init__(self, window, parent):
        super().__init__(parent.window)
        self.parent = parent
        self.core = parent.core
        self.settings = parent.settings
        self.presetDir = self.core.presetDir
        self.findPresets()

        # window
        self.lastFilter = '*'
        self.presetRows = [] # list of (comp, vers, name) tuples
        self.window = window
        self.window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # connect button signals
        self.window.pushButton_delete.clicked.connect(self.openDeletePresetDialog)
        self.window.pushButton_rename.clicked.connect(self.openRenamePresetDialog)
        self.window.pushButton_import.clicked.connect(self.openImportDialog)
        self.window.pushButton_export.clicked.connect(self.openExportDialog)
        self.window.pushButton_close.clicked.connect(self.window.close)

        # create filter box and preset list
        self.drawFilterList()
        self.window.comboBox_filter.currentIndexChanged.connect(
            lambda: self.drawPresetList(
                self.window.comboBox_filter.currentText(), self.window.lineEdit_search.text()
            )
        )

        # make auto-completion for search bar
        self.autocomplete = QtGui.QStringListModel()
        completer = QtGui.QCompleter()
        completer.setModel(self.autocomplete)
        self.window.lineEdit_search.setCompleter(completer)
        self.window.lineEdit_search.textChanged.connect(
            lambda: self.drawPresetList(
                self.window.comboBox_filter.currentText(), self.window.lineEdit_search.text()
            )
        )
        self.drawPresetList('*')

    def show(self):
        '''Open a new preset manager window from the mainwindow'''
        self.findPresets()
        self.drawFilterList()
        self.drawPresetList('*')
        self.window.show()

    def findPresets(self):
        parseList = []
        for dirpath, dirnames, filenames in os.walk(self.presetDir):
            # anything without a subdirectory must be a preset folder
            if dirnames:
                continue
            for preset in filenames:
                compName = os.path.basename(os.path.dirname(dirpath))
                compVers = os.path.basename(dirpath)
                try:
                    parseList.append((compName, int(compVers), preset))
                except ValueError:
                    continue
        self.presets =\
            {
            compName : \
                [
                (vers, preset) \
                    for name, vers, preset in parseList \
                    if name == compName \
                ] \
            for compName, _, __ in parseList \
            }

    def drawPresetList(self, compFilter=None, presetFilter=''):
        self.window.listWidget_presets.clear()
        if compFilter:
            self.lastFilter = str(compFilter)
        else:
            compFilter = str(self.lastFilter)
        self.presetRows = []
        presetNames = []
        for component, presets in self.presets.items():
            if compFilter != '*' and component != compFilter:
                continue
            for vers, preset in presets:
                if not presetFilter or presetFilter in preset:
                    self.window.listWidget_presets.addItem('%s: %s' % (component, preset))
                    self.presetRows.append((component, vers, preset))
                if preset not in presetNames:
                    presetNames.append(preset)
        self.autocomplete.setStringList(presetNames)

    def drawFilterList(self):
        self.window.comboBox_filter.clear()
        self.window.comboBox_filter.addItem('*')
        for component in self.presets:
            self.window.comboBox_filter.addItem(component)

    def openSavePresetDialog(self):
        '''Functions on mainwindow level from the context menu'''
        window = self.parent.window
        selectedComponents = self.parent.core.selectedComponents
        componentList = self.parent.window.listWidget_componentList

        if componentList.currentRow() == -1:
            return
        while True:
            index = componentList.currentRow()
            currentPreset = selectedComponents[index].currentPreset
            newName, OK = QtGui.QInputDialog.getText(
                self.parent.window,
                'Audio Visualizer',
                'New Preset Name:',
                QtGui.QLineEdit.Normal,
                currentPreset
            )
            if OK:
                if core.Core.badName(newName):
                    self.warnMessage(self.parent.window)
                    continue
                if newName:
                    if index != -1:
                        selectedComponents[index].currentPreset = newName
                        saveValueStore = \
                            selectedComponents[index].savePreset()
                        componentName = str(selectedComponents[index]).strip()
                        vers = selectedComponents[index].version()
                        self.createNewPreset(
                            componentName, vers, newName,
                            saveValueStore, window=self.parent.window)
                        self.openPreset(newName)
            break

    def createNewPreset(
        self, compName, vers, filename, saveValueStore, **kwargs):
        path = os.path.join(self.presetDir, compName, str(vers), filename)
        if self.presetExists(path, **kwargs):
            return
        self.core.createPresetFile(compName, vers, filename, saveValueStore)

    def presetExists(self, path, **kwargs):
        if os.path.exists(path):
            window = self.window \
                if 'window' not in kwargs else kwargs['window']
            ch = self.parent.showMessage(
                msg="%s already exists! Overwrite it?" %
                    os.path.basename(path),
                showCancel=True,
                icon=QtGui.QMessageBox.Warning,
                parent=window)
            if not ch:
                # user clicked cancel
                return True

        return False

    def openPreset(self, presetName):
        componentList = self.parent.window.listWidget_componentList
        selectedComponents = self.parent.core.selectedComponents

        index = componentList.currentRow()
        if index == -1:
            return
        componentName = str(selectedComponents[index]).strip()
        version = selectedComponents[index].version()
        dirname = os.path.join(self.presetDir, componentName, str(version))
        filepath = os.path.join(dirname, presetName)
        self.core.openPreset(filepath, index, presetName)

        self.parent.updateComponentTitle(index)
        self.parent.drawPreview()

    def openDeletePresetDialog(self):
        selected = self.window.listWidget_presets.selectedItems()
        if not selected:
            return
        row = self.window.listWidget_presets.row(selected[0])
        comp, vers, name = self.presetRows[row]
        ch = self.parent.showMessage(
            msg='Really delete %s?' % name,
            showCancel=True,
            icon=QtGui.QMessageBox.Warning,
            parent=self.window
        )
        if not ch:
            return
        self.deletePreset(comp, vers, name)
        self.findPresets()
        self.drawPresetList()

    def deletePreset(self, comp, vers, name):
        filepath = os.path.join(self.presetDir, comp, str(vers), name)
        os.remove(filepath)

    def warnMessage(self, window=None):
        print(window)
        self.parent.showMessage(
            msg='Preset names must contain only letters, '
            'numbers, and spaces.',
            parent=window if window else self.window)

    def openRenamePresetDialog(self):
        presetList = self.window.listWidget_presets
        if presetList.currentRow() == -1:
            return

        while True:
            index = presetList.currentRow()
            newName, OK = QtGui.QInputDialog.getText(
                self.window,
                'Preset Manager',
                'Rename Preset:',
                QtGui.QLineEdit.Normal,
                self.presetRows[index][2]
            )
            if OK:
                if core.Core.badName(newName):
                    self.warnMessage()
                    continue
                if newName:
                    comp, vers, oldName = self.presetRows[index]
                    path = os.path.join(
                        self.presetDir, comp, str(vers))
                    newPath = os.path.join(path, newName)
                    oldPath = os.path.join(path, oldName)
                    if self.presetExists(newPath):
                        return
                    if os.path.exists(newPath):
                        os.remove(newPath)
                    os.rename(oldPath, newPath)
                    self.findPresets()
                    self.drawPresetList()
            break

    def openImportDialog(self):
        filename = QtGui.QFileDialog.getOpenFileName(
            self.window, "Import Preset File",
            self.settings.value("projectDir"),
            "Preset Files (*.avl)")
        if filename:
            path = ''
            while True:
                if path:
                    if self.presetExists(path):
                        break
                    else:
                        if os.path.exists(path):
                            os.remove(path)
                success, path = self.core.importPreset(filename)
                if success:
                    break
            self.findPresets()
            self.drawPresetList()

    def openExportDialog(self):
        if not self.window.listWidget_presets.selectedItems():
            return
        filename = QtGui.QFileDialog.getSaveFileName(
            self.window, "Export Preset",
            self.settings.value("projectDir"),
            "Preset Files (*.avl)")
        if filename:
            index = self.window.listWidget_presets.currentRow()
            comp, vers, name = self.presetRows[index]
            if not self.core.exportPreset(filename, comp, vers, name):
                self.parent.showMessage(
                    msg='Couldn\'t export %s.' % filename,
                    parent=self.window
                )
