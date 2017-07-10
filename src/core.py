'''
   Home to the Core class which tracks program state. Used by GUI & commandline
'''
import sys
import os
from PyQt5 import QtCore, QtGui, uic
import subprocess as sp
import numpy
import json
from importlib import import_module
from PyQt5.QtCore import QStandardPaths

import toolkit


class Core:
    '''
        MainWindow and Command module both use an instance of this class
        to store the program state. This object tracks the components,
        opens projects and presets, and stores settings/paths to data.
    '''
    def __init__(self):
        self.dataDir = QStandardPaths.writableLocation(
            QStandardPaths.AppConfigLocation
        )
        self.presetDir = os.path.join(self.dataDir, 'presets')
        if getattr(sys, 'frozen', False):
            # frozen
            self.wd = os.path.dirname(sys.executable)
        else:
            # unfrozen
            self.wd = os.path.dirname(os.path.realpath(__file__))
        self.componentsPath = os.path.join(self.wd, 'components')
        self.settings = QtCore.QSettings(
            os.path.join(self.dataDir, 'settings.ini'),
            QtCore.QSettings.IniFormat
        )

        self.loadEncoderOptions()
        self.videoFormats = toolkit.appendUppercase([
            '*.mp4',
            '*.mov',
            '*.mkv',
            '*.avi',
            '*.webm',
            '*.flv',
        ])
        self.audioFormats = toolkit.appendUppercase([
            '*.mp3',
            '*.wav',
            '*.ogg',
            '*.fla',
            '*.flac',
            '*.aac',
        ])
        self.imageFormats = toolkit.appendUppercase([
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

        self.FFMPEG_BIN = self.findFfmpeg()
        self.findComponents()
        self.selectedComponents = []
        # copies of named presets to detect modification
        self.savedPresets = {}

    def findComponents(self):
        def findComponents():
            for f in sorted(os.listdir(self.componentsPath)):
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
        self.compNames = [mod.Component.__doc__ for mod in self.modules]
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
            moduleIndex, compPos, self
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

    def getPresetDir(self, comp):
        return os.path.join(
            self.presetDir, str(comp), str(comp.version()))

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
                    self.settings.setValue(key, value)

                for tup in data['Components']:
                    name, vers, preset = tup
                    clearThis = False
                    modified = False

                    # add loaded named presets to savedPresets dict
                    if 'preset' in preset and preset['preset'] is not None:
                        nam = preset['preset']
                        filepath2 = os.path.join(
                            self.presetDir, name, str(vers), nam)
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
                self.presetDir,
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
            self.presetDir, compName, str(vers), origName
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
            dirname = os.path.join(self.presetDir, compName, str(vers))
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
                    f.write('%s\n' % str(comp))
                    f.write('%s\n' % str(comp.version()))
                    f.write('%s\n' % toolkit.presetToString(saveValueStore))

                f.write('\n[Settings]\n')
                for key in self.settings.allKeys():
                    if key in settingsKeys:
                        f.write('%s=%s\n' % (key, self.settings.value(key)))

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

    def loadEncoderOptions(self):
        file_path = os.path.join(self.wd, 'encoder-options.json')
        with open(file_path) as json_file:
            self.encoder_options = json.load(json_file)

    def findFfmpeg(self):
        if getattr(sys, 'frozen', False):
            # The application is frozen
            if sys.platform == "win32":
                return os.path.join(self.wd, 'ffmpeg.exe')
            else:
                return os.path.join(self.wd, 'ffmpeg')

        else:
            if sys.platform == "win32":
                return "ffmpeg"
            else:
                try:
                    with open(os.devnull, "w") as f:
                        toolkit.checkOutput(
                            ['ffmpeg', '-version'], stderr=f
                        )
                    return "ffmpeg"
                except sp.CalledProcessError:
                    return "avconv"

    def createFfmpegCommand(self, inputFile, outputFile):
        '''
            Constructs the major ffmpeg command used to export the video
        '''

        # Test if user has libfdk_aac
        encoders = toolkit.checkOutput(
            "%s -encoders -hide_banner" % self.FFMPEG_BIN, shell=True
        )
        encoders = encoders.decode("utf-8")

        acodec = self.settings.value('outputAudioCodec')

        options = self.encoder_options
        containerName = self.settings.value('outputContainer')
        vcodec = self.settings.value('outputVideoCodec')
        vbitrate = str(self.settings.value('outputVideoBitrate'))+'k'
        acodec = self.settings.value('outputAudioCodec')
        abitrate = str(self.settings.value('outputAudioBitrate'))+'k'

        for cont in options['containers']:
            if cont['name'] == containerName:
                container = cont['container']
                break

        vencoders = options['video-codecs'][vcodec]
        aencoders = options['audio-codecs'][acodec]

        for encoder in vencoders:
            if encoder in encoders:
                vencoder = encoder
                break

        for encoder in aencoders:
            if encoder in encoders:
                aencoder = encoder
                break

        ffmpegCommand = [
            self.FFMPEG_BIN,
            '-thread_queue_size', '512',
            '-y',  # overwrite the output file if it already exists.

            # INPUT VIDEO
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', '%sx%s' % (
                self.settings.value('outputWidth'),
                self.settings.value('outputHeight'),
            ),
            '-pix_fmt', 'rgba',
            '-r', self.settings.value('outputFrameRate'),
            '-i', '-',  # the video input comes from a pipe
            '-an',  # the video input has no sound

            # INPUT SOUND
            '-i', inputFile
        ]

        extraAudio = [
            comp.audio() for comp in self.selectedComponents
            if 'audio' in comp.properties()
        ]
        if extraAudio:
            for extraInputFile in extraAudio:
                ffmpegCommand.extend([
                    '-i', extraInputFile
                ])
            ffmpegCommand.extend([
                '-filter_complex',
                'amix=inputs=%s:duration=longest:dropout_transition=3' % str(
                    len(extraAudio) + 1
                )
            ])

        ffmpegCommand.extend([
            # OUTPUT
            '-vcodec', vencoder,
            '-acodec', aencoder,
            '-b:v', vbitrate,
            '-b:a', abitrate,
            '-pix_fmt', self.settings.value('outputVideoFormat'),
            '-preset', self.settings.value('outputPreset'),
            '-f', container
        ])

        if acodec == 'aac':
            ffmpegCommand.append('-strict')
            ffmpegCommand.append('-2')

        ffmpegCommand.append(outputFile)
        return ffmpegCommand

    def readAudioFile(self, filename, parent):
        command = [self.FFMPEG_BIN, '-i', filename]

        try:
            fileInfo = toolkit.checkOutput(command, stderr=sp.STDOUT)
        except sp.CalledProcessError as ex:
            fileInfo = ex.output

        info = fileInfo.decode("utf-8").split('\n')
        for line in info:
            if 'Duration' in line:
                d = line.split(',')[0]
                d = d.split(' ')[3]
                d = d.split(':')
                duration = float(d[0])*3600 + float(d[1])*60 + float(d[2])

        command = [
            self.FFMPEG_BIN,
            '-i', filename,
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',  # ouput will have 44100 Hz
            '-ac', '1',  # mono (set to '2' for stereo)
            '-']
        in_pipe = toolkit.openPipe(
            command, stdout=sp.PIPE, stderr=sp.DEVNULL, bufsize=10**8
        )

        completeAudioArray = numpy.empty(0, dtype="int16")

        progress = 0
        lastPercent = None
        while True:
            if self.canceled:
                break
            # read 2 seconds of audio
            progress += 4
            raw_audio = in_pipe.stdout.read(88200*4)
            if len(raw_audio) == 0:
                break
            audio_array = numpy.fromstring(raw_audio, dtype="int16")
            completeAudioArray = numpy.append(completeAudioArray, audio_array)

            percent = int(100*(progress/duration))
            if percent >= 100:
                percent = 100

            if lastPercent != percent:
                string = 'Loading audio file: '+str(percent)+'%'
                parent.progressBarSetText.emit(string)
                parent.progressBarUpdate.emit(percent)

            lastPercent = percent

        in_pipe.kill()
        in_pipe.wait()

        # add 0s the end
        completeAudioArrayCopy = numpy.zeros(
            len(completeAudioArray) + 44100, dtype="int16")
        completeAudioArrayCopy[:len(completeAudioArray)] = completeAudioArray
        completeAudioArray = completeAudioArrayCopy

        return completeAudioArray

    def cancel(self):
        self.canceled = True

    def reset(self):
        self.canceled = False
