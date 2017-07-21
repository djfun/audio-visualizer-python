'''
   Home to the Core class which tracks program state. Used by GUI & commandline
'''
from PyQt5 import QtCore, QtGui, uic
import sys
import os
import json
from importlib import import_module

import toolkit
from toolkit.ffmpeg import findFfmpeg
import video_thread


class Core:
    '''
        MainWindow and Command module both use an instance of this class
        to store the core program state. This object tracks the components,
        talks to the components and handles opening/creating project files
        and presets. The class also stores constants as class variables.
    '''

    @classmethod
    def storeSettings(cls):
        '''Store settings/paths to directories as class variables.'''
        if getattr(sys, 'frozen', False):
            # frozen
            wd = os.path.dirname(sys.executable)
        else:
            wd = os.path.dirname(os.path.realpath(__file__))

        dataDir = QtCore.QStandardPaths.writableLocation(
            QtCore.QStandardPaths.AppConfigLocation
        )
        with open(os.path.join(wd, 'encoder-options.json')) as json_file:
            encoderOptions = json.load(json_file)

        settings = {
            'wd': wd,
            'dataDir': dataDir,
            'settings': QtCore.QSettings(
                            os.path.join(dataDir, 'settings.ini'),
                            QtCore.QSettings.IniFormat),
            'presetDir': os.path.join(dataDir, 'presets'),
            'componentsPath': os.path.join(wd, 'components'),
            'encoderOptions': encoderOptions,
            'FFMPEG_BIN': findFfmpeg(),
            'canceled': False,
        }

        settings['videoFormats'] = toolkit.appendUppercase([
            '*.mp4',
            '*.mov',
            '*.mkv',
            '*.avi',
            '*.webm',
            '*.flv',
        ])
        settings['audioFormats'] = toolkit.appendUppercase([
            '*.mp3',
            '*.wav',
            '*.ogg',
            '*.fla',
            '*.flac',
            '*.aac',
        ])
        settings['imageFormats'] = toolkit.appendUppercase([
            '*.png',
            '*.jpg',
            '*.tif',
            '*.tiff',
            '*.gif',
            '*.bmp',
            '*.ico',
            '*.xbm',
            '*.xpm',
        ])

        # Register all settings as class variables
        for classvar, val in settings.items():
            setattr(cls, classvar, val)
        # Make settings accessible to the toolkit package
        toolkit.init(settings)

    def __init__(self):
        Core.storeSettings()

        self.findComponents()
        self.selectedComponents = []
        self.savedPresets = {}  # copies of presets to detect modification

    def findComponents(self):
        def findComponents():
            for f in sorted(os.listdir(Core.componentsPath)):
                name, ext = os.path.splitext(f)
                if name.startswith("__"):
                    continue
                elif ext == '.py':
                    yield name
        self.modules = [
            import_module('components.%s' % name)
            for name in findComponents()
        ]
        # store canonical module names and indexes
        self.moduleIndexes = [i for i in range(len(self.modules))]
        self.compNames = [mod.Component.name for mod in self.modules]
        self.altCompNames = []
        # store alternative names for modules
        for i, mod in enumerate(self.modules):
            if hasattr(mod.Component, 'names'):
                for name in mod.Component.names():
                    self.altCompNames.append((name, i))

    def componentListChanged(self):
        for i, component in enumerate(self.selectedComponents):
            component.compPos = i

    def insertComponent(self, compPos, moduleIndex, loader):
        '''Creates a new component'''
        if compPos < 0 or compPos > len(self.selectedComponents):
            compPos = len(self.selectedComponents)
        if len(self.selectedComponents) > 50:
            return None

        component = self.modules[moduleIndex].Component(
            moduleIndex, compPos
        )
        self.selectedComponents.insert(
            compPos,
            component
        )
        self.componentListChanged()

        # init component's widget for loading/saving presets
        self.selectedComponents[compPos].widget(loader)
        self.updateComponent(compPos)

        if hasattr(loader, 'insertComponent'):
            loader.insertComponent(compPos)
        return compPos

    def moveComponent(self, startI, endI):
        comp = self.selectedComponents.pop(startI)
        self.selectedComponents.insert(endI, comp)

        self.componentListChanged()
        return endI

    def removeComponent(self, i):
        self.selectedComponents.pop(i)
        self.componentListChanged()

    def clearComponents(self):
        self.selectedComponents = list()
        self.componentListChanged()

    def updateComponent(self, i):
        # print('updating %s' % self.selectedComponents[i])
        self.selectedComponents[i].update()

    def moduleIndexFor(self, compName):
        try:
            index = self.compNames.index(compName)
            return self.moduleIndexes[index]
        except ValueError:
            for altName, modI in self.altCompNames:
                if altName == compName:
                    return self.moduleIndexes[modI]

    def clearPreset(self, compIndex):
        self.selectedComponents[compIndex].currentPreset = None

    def openPreset(self, filepath, compIndex, presetName):
        '''Applies a preset to a specific component'''
        saveValueStore = self.getPreset(filepath)
        if not saveValueStore:
            return False
        try:
            self.selectedComponents[compIndex].loadPreset(
                saveValueStore,
                presetName
            )
        except KeyError as e:
            print('preset missing value: %s' % e)

        self.savedPresets[presetName] = dict(saveValueStore)
        return True

    def getPreset(self, filepath):
        '''Returns the preset dict stored at this filepath'''
        if not os.path.exists(filepath):
            return False
        with open(filepath, 'r') as f:
            for line in f:
                saveValueStore = toolkit.presetFromString(line.strip())
                break
        return saveValueStore

    def openProject(self, loader, filepath):
        ''' loader is the object calling this method which must have
        its own showMessage(**kwargs) method for displaying errors.
        '''
        if not os.path.exists(filepath):
            loader.showMessage(msg='Project file not found.')
            return

        errcode, data = self.parseAvFile(filepath)
        if errcode == 0:
            try:
                if hasattr(loader, 'window'):
                    for widget, value in data['WindowFields']:
                        widget = eval('loader.window.%s' % widget)
                        widget.blockSignals(True)
                        widget.setText(value)
                        widget.blockSignals(False)

                for key, value in data['Settings']:
                    Core.settings.setValue(key, value)

                for tup in data['Components']:
                    name, vers, preset = tup
                    clearThis = False
                    modified = False

                    # add loaded named presets to savedPresets dict
                    if 'preset' in preset and preset['preset'] is not None:
                        nam = preset['preset']
                        filepath2 = os.path.join(
                            Core.presetDir, name, str(vers), nam)
                        origSaveValueStore = self.getPreset(filepath2)
                        if origSaveValueStore:
                            self.savedPresets[nam] = dict(origSaveValueStore)
                            modified = not origSaveValueStore == preset
                        else:
                            # saved preset was renamed or deleted
                            clearThis = True

                    # create the actual component object & get its index
                    i = self.insertComponent(
                        -1,
                        self.moduleIndexFor(name),
                        loader)
                    if i is None:
                        loader.showMessage(msg="Too many components!")
                        break

                    try:
                        if 'preset' in preset and preset['preset'] is not None:
                            self.selectedComponents[i].loadPreset(
                                preset
                            )
                        else:
                            self.selectedComponents[i].loadPreset(
                                preset,
                                preset['preset']
                            )
                    except KeyError as e:
                        print('%s missing value: %s' % (
                            self.selectedComponents[i], e)
                        )

                    if clearThis:
                        self.clearPreset(i)
                    if hasattr(loader, 'updateComponentTitle'):
                        loader.updateComponentTitle(i, modified)

            except:
                errcode = 1
                data = sys.exc_info()

        if errcode == 1:
            typ, value, tb = data
            if typ.__name__ == 'KeyError':
                # probably just an old version, still loadable
                print('file missing value: %s' % value)
                return
            if hasattr(loader, 'createNewProject'):
                loader.createNewProject(prompt=False)
            import traceback
            msg = '%s: %s\n\nTraceback:\n' % (typ.__name__, value)
            msg += "\n".join(traceback.format_tb(tb))
            loader.showMessage(
                msg="Project file '%s' is corrupted." % filepath,
                showCancel=False,
                icon='Warning',
                detail=msg)

    def parseAvFile(self, filepath):
        '''Parses an avp (project) or avl (preset package) file.
        Returns dictionary with section names as the keys, each one
        contains a list of tuples: (compName, version, compPresetDict)
        '''
        validSections = (
                    'Components',
                    'Settings',
                    'WindowFields'
                )
        data = {sect: [] for sect in validSections}
        try:
            with open(filepath, 'r') as f:
                def parseLine(line):
                    '''Decides if a file line is a section header'''
                    line = line.strip()
                    newSection = ''

                    if line.startswith('[') and line.endswith(']') \
                            and line[1:-1] in validSections:
                        newSection = line[1:-1]

                    return line, newSection

                section = ''
                i = 0
                for line in f:
                    line, newSection = parseLine(line)
                    if newSection:
                        section = str(newSection)
                        continue
                    if line and section == 'Components':
                        if i == 0:
                            lastCompName = str(line)
                            i += 1
                        elif i == 1:
                            lastCompVers = str(line)
                            i += 1
                        elif i == 2:
                            lastCompPreset = toolkit.presetFromString(line)
                            data[section].append((
                                lastCompName,
                                lastCompVers,
                                lastCompPreset
                            ))
                            i = 0
                    elif line and section:
                        key, value = line.split('=', 1)
                        data[section].append((key, value.strip()))

            return 0, data
        except:
            return 1, sys.exc_info()

    def importPreset(self, filepath):
        errcode, data = self.parseAvFile(filepath)
        returnList = []
        if errcode == 0:
            name, vers, preset = data['Components'][0]
            presetName = preset['preset'] \
                if preset['preset'] else os.path.basename(filepath)[:-4]
            newPath = os.path.join(
                Core.presetDir,
                name,
                vers,
                presetName
            )
            if os.path.exists(newPath):
                return False, newPath
            preset['preset'] = presetName
            self.createPresetFile(
                name, vers, presetName, preset
            )
            return True, presetName
        elif errcode == 1:
            # TODO: an error message
            return False, ''

    def exportPreset(self, exportPath, compName, vers, origName):
        internalPath = os.path.join(
            Core.presetDir, compName, str(vers), origName
        )
        if not os.path.exists(internalPath):
            return
        if os.path.exists(exportPath):
            os.remove(exportPath)
        with open(internalPath, 'r') as f:
            internalData = [line for line in f]
        try:
            saveValueStore = toolkit.presetFromString(internalData[0].strip())
            self.createPresetFile(
                compName, vers,
                origName, saveValueStore,
                exportPath
            )
            return True
        except:
            return False

    def createPresetFile(
            self, compName, vers, presetName, saveValueStore, filepath=''):
        '''Create a preset file (.avl) at filepath using args.
        Or if filepath is empty, create an internal preset using args'''
        if not filepath:
            dirname = os.path.join(Core.presetDir, compName, str(vers))
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            filepath = os.path.join(dirname, presetName)
            internal = True
        else:
            if not filepath.endswith('.avl'):
                filepath += '.avl'
            internal = False

        with open(filepath, 'w') as f:
            if not internal:
                f.write('[Components]\n')
                f.write('%s\n' % compName)
                f.write('%s\n' % str(vers))
            f.write(toolkit.presetToString(saveValueStore))

    def createProjectFile(self, filepath, window=None):
        '''Create a project file (.avp) using the current program state'''
        settingsKeys = [
            'componentDir',
            'inputDir',
            'outputDir',
            'presetDir',
            'projectDir',
        ]
        try:
            if not filepath.endswith(".avp"):
                filepath += '.avp'
            if os.path.exists(filepath):
                os.remove(filepath)
            with open(filepath, 'w') as f:
                print('creating %s' % filepath)

                f.write('[Components]\n')
                for comp in self.selectedComponents:
                    saveValueStore = comp.savePreset()
                    saveValueStore['preset'] = comp.currentPreset
                    f.write('%s\n' % str(comp))
                    f.write('%s\n' % str(comp.version))
                    f.write('%s\n' % toolkit.presetToString(saveValueStore))

                f.write('\n[Settings]\n')
                for key in Core.settings.allKeys():
                    if key in settingsKeys:
                        f.write('%s=%s\n' % (key, Core.settings.value(key)))

                if window:
                    f.write('\n[WindowFields]\n')
                    f.write(
                        'lineEdit_audioFile=%s\n'
                        'lineEdit_outputFile=%s\n' % (
                            window.lineEdit_audioFile.text(),
                            window.lineEdit_outputFile.text()
                        )
                    )
            return True
        except:
            return False

    def newVideoWorker(self, loader, audioFile, outputPath):
        '''loader is MainWindow or Command object which must own the thread'''
        self.videoThread = QtCore.QThread(loader)
        videoWorker = video_thread.Worker(
            loader, audioFile, outputPath, self.selectedComponents
        )
        videoWorker.moveToThread(self.videoThread)
        videoWorker.videoCreated.connect(self.videoCreated)

        self.videoThread.start()
        return videoWorker

    def videoCreated(self):
        self.videoThread.quit()
        self.videoThread.wait()

    def cancel(self):
        Core.canceled = True
        toolkit.cancel()

    def reset(self):
        Core.canceled = False
        toolkit.reset()
