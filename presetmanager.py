from PyQt4 import QtGui
from collections import OrderedDict
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
        self.window = window
        self.findPresets()
        self.lastFilter = '*'
        self.presetRows = [] # list of (comp, vers, name) tuples

        # connect button signals
        self.window.pushButton_delete.clicked.connect(self.openDeletePresetDialog)
        self.window.pushButton_rename.clicked.connect(self.openRenamePresetDialog)
        self.window.pushButton_close.clicked.connect(self.close)
        self.window.pushButton_import.clicked.connect(self.openImportDialog)
        self.window.pushButton_export.clicked.connect(self.openExportDialog)

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
        self.selectedComponents = self.parent.core.selectedComponents
        componentList = self.parent.window.listWidget_componentList

        if componentList.currentRow() == -1:
            return
        while True:
            index = componentList.currentRow()
            currentPreset = self.selectedComponents[index].currentPreset
            newName, OK = QtGui.QInputDialog.getText(
                self.parent.window,
                'Audio Visualizer',
                'New Preset Name:',
                QtGui.QLineEdit.Normal,
                currentPreset
            )
            if OK:
                if core.Core.badName(newName):
                    self.warnMessage()
                    continue
                if newName:
                    if index != -1:
                        saveValueStore = \
                            self.selectedComponents[index].savePreset()
                        componentName = str(self.selectedComponents[index]).strip()
                        vers = self.selectedComponents[index].version()
                        self.createNewPreset(
                            componentName, vers, saveValueStore, newName)
                        self.selectedComponents[index].currentPreset = newName
                        self.findPresets()
                        self.drawPresetList()
            break

    def createNewPreset(self, compName, vers, saveValueStore, filename):
        path = os.path.join(self.presetDir, compName, str(vers), filename)
        if self.presetExists(path):
            return
        self.core.createPresetFile(compName, vers, saveValueStore, filename)

    def presetExists(self, path):
        if os.path.exists(path):
            ch = self.parent.showMessage(
                msg="%s already exists! Overwrite it?" %
                    os.path.basename(path),
                showCancel=True, icon=QtGui.QMessageBox.Warning)
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
        if not os.path.exists(filepath):
            return
        with open(filepath, 'r') as f:
            for line in f:
                saveValueStore = dict(eval(line.strip()))
                break
        selectedComponents[index].loadPreset(
            saveValueStore,
            presetName
        )
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
            showCancel=True, icon=QtGui.QMessageBox.Warning
        )
        if not ch:
            return
        self.deletePreset(comp, vers, name)
        self.findPresets()
        self.drawPresetList()

    def deletePreset(self, comp, vers, name):
        filepath = os.path.join(self.presetDir, comp, str(vers), name)
        os.remove(filepath)

    def warnMessage(self):
        self.parent.showMessage(
            msg='Preset names must contain only letters, '
            'numbers, and spaces.')

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
            self.core.importPreset(filename)

    def openExportDialog(self):
        filename = QtGui.QFileDialog.getSaveFileName(
            self.window, "Export Preset",
            self.settings.value("projectDir"),
            "Preset Files (*.avl)")
        if filename:
            index = self.window.listWidget_presets.currentRow()
            comp, vers, name = self.presetRows[index]
            self.core.exportPreset(filename, comp, vers, name)
