from PyQt4 import QtGui
#import sys
import os

class PresetManager(QtGui.QDialog):
    def __init__(self, window, parent):
        super().__init__()
        self.parent = parent
        self.presetDir = parent.presetDir
        self.window = window
        self.presets = self.findPresets()

        # create filter box and preset list
        self.drawFilterList()
        self.window.comboBox_filter.currentIndexChanged.connect(
            lambda: self.drawPresetList(self.window.comboBox_filter.currentText())
        )
        self.drawPresetList('*')

        # make auto-completion for search bar
        self.autocomplete = QtGui.QStringListModel()
        completer = QtGui.QCompleter()
        completer.setModel(self.autocomplete)
        self.window.lineEdit_search.setCompleter(completer)

    def show(self):
        presetNames = []
        for presetList in self.presets.values():
            for preset in presetList:
                presetNames.append(preset[1])
        self.autocomplete.setStringList(presetNames)
        self.presets = self.findPresets()
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
        return { compName : \
                    [ (vers, preset) \
                        for name, vers, preset in parseList \
                        if name == compName \
                    ] \
                for compName, _, __ in parseList \
                }

    def drawPresetList(self, filter):
        self.window.listWidget_presets.clear()
        for component, presets in self.presets.items():
            if filter != '*' and component != filter:
                continue
            for vers, preset in presets:
                self.window.listWidget_presets.addItem('%s: %s' % (component, preset))

    def drawFilterList(self):
        self.window.comboBox_filter.clear()
        self.window.comboBox_filter.addItem('*')
        for component in self.presets:
            self.window.comboBox_filter.addItem(component)
