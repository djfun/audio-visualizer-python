import sys
import io
import os
from PyQt4 import QtCore, QtGui, uic
from os.path import expanduser
import subprocess as sp
import numpy
from PIL import Image
#import tempfile
from shutil import rmtree
#import atexit
import time
from collections import OrderedDict
import json
from importlib import import_module
from PyQt4.QtGui import QDesktopServices
import string


class Core():

    def __init__(self):
        self.FFMPEG_BIN = self.findFfmpeg()
        #self.tempDir = os.path.join(
        #    tempfile.gettempdir(), 'audio-visualizer-python-data')
        #if not os.path.exists(self.tempDir):
        #    os.makedirs(self.tempDir)
        #atexit.register(self.deleteTempDir)
        self.dataDir = QDesktopServices.storageLocation(
            QDesktopServices.DataLocation)
        self.presetDir = os.path.join(self.dataDir, 'presets')
        self.wd = os.path.dirname(os.path.realpath(__file__))
        self.loadEncoderOptions()

        self.findComponents()
        self.selectedComponents = []

    def findComponents(self):
        def findComponents():
            srcPath = os.path.join(self.wd, 'components')
            if os.path.exists(srcPath):
                for f in sorted(os.listdir(srcPath)):
                    name, ext = os.path.splitext(f)
                    if name.startswith("__"):
                        continue
                    elif ext == '.py':
                        yield name
        self.modules = [
            import_module('components.%s' % name)
            for name in findComponents()]
        self.moduleIndexes = [i for i in range(len(self.modules))]

    def insertComponent(self, compPos, moduleIndex):
        if compPos < 0:
            compPos = len(self.selectedComponents) -1
        self.selectedComponents.insert(
            compPos,
            self.modules[moduleIndex].Component()
        )
        return compPos

    def moveComponent(self, startI, endI):
        comp = self.selectedComponents.pop(startI)
        self.selectedComponents.insert(endI, comp)
        return endI

    def updateComponent(self, i):
        # print('updating %s' % self.selectedComponents[i])
        self.selectedComponents[i].update()

    def moduleIndexFor(self, compName):
        compNames = [mod.Component.__doc__ for mod in self.modules]
        index = compNames.index(compName)
        return self.moduleIndexes[index]

    def openProject(self, loader, filepath):
        '''loader is the object calling this method (mainwindow/command)
        which implements an insertComponent method'''
        errcode, data = self.parseAvFile(filepath)
        if errcode == 0:
            for name, vers, preset in data['Components']:
                loader.insertComponent(
                    self.moduleIndexFor(name), -1)
                self.selectedComponents[-1].loadPreset(
                    preset)
        elif errcode == 1:
            typ, value, _ = data
            if typ.__name__ == KeyError:
                # probably just an old version, still loadable
                print('file missing value: %s' % value)
                return
            loader.createNewProject()
            msg = '%s: %s' % (typ.__name__, value)
            loader.showMessage(
                msg="Project file '%s' is corrupted." % filepath,
                showCancel=False,
                icon=QtGui.QMessageBox.Warning,
                detail=msg)

    def parseAvFile(self, filepath):
        '''Parses an avp (project) or avl (preset package) file.
        Returns data usable by another method.'''
        data = {}
        try:
            with open(filepath, 'r') as f:
                def parseLine(line):
                    '''Decides if a given avp or avl line is a section header'''
                    validSections = ('Components')
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
                        data[section] = []
                        continue
                    if line and section == 'Components':
                        if i == 0:
                            lastCompName = str(line)
                            i += 1
                        elif i == 1:
                            lastCompVers = str(line)
                            i += 1
                        elif i == 2:
                            lastCompPreset = Core.presetFromString(line)
                            data[section].append(
                                (lastCompName,
                                lastCompVers,
                                lastCompPreset)
                            )
                            i = 0
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
        internalPath = os.path.join(self.presetDir, compName, str(vers), origName)
        if not os.path.exists(internalPath):
            return
        if os.path.exists(exportPath):
            os.remove(exportPath)
        with open(internalPath, 'r') as f:
            internalData = [line for line in f]
        try:
            saveValueStore = Core.presetFromString(internalData[0].strip())
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
           Or if filepath is empty, create an internal preset using
           the args for the filepath.'''
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
            f.write(Core.presetToString(saveValueStore))

    def createProjectFile(self, filepath):
        '''Create a project file (.avp) using the current program state'''
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
                    f.write('%s\n' % Core.presetToString(saveValueStore))
            return True
        except:
            return False

    def loadEncoderOptions(self):
        file_path = os.path.join(self.wd, 'encoder-options.json')
        with open(file_path) as json_file:
            self.encoder_options = json.load(json_file)

    def findFfmpeg(self):
        if sys.platform == "win32":
            return "ffmpeg.exe"
        else:
            try:
                with open(os.devnull, "w") as f:
                    sp.check_call(['ffmpeg', '-version'], stdout=f, stderr=f)
                return "ffmpeg"
            except:
                return "avconv"

    def readAudioFile(self, filename, parent):
        command = [self.FFMPEG_BIN, '-i', filename]

        try:
            fileInfo = sp.check_output(command, stderr=sp.STDOUT, shell=False)
        except sp.CalledProcessError as ex:
            fileInfo = ex.output
            pass

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
        in_pipe = sp.Popen(
            command, stdout=sp.PIPE, stderr=sp.DEVNULL, bufsize=10**8)

        completeAudioArray = numpy.empty(0, dtype="int16")

        progress = 0
        lastPercent = None
        while True:
            if self.canceled:
                break
            # read 2 seconds of audio
            progress = progress + 4
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

    #def deleteTempDir(self):
    #    try:
    #        rmtree(self.tempDir)
    #    except FileNotFoundError:
    #        pass

    def cancel(self):
        self.canceled = True

    def reset(self):
        self.canceled = False

    @staticmethod
    def badName(name):
        '''Returns whether a name contains non-alphanumeric chars'''
        return any([letter in string.punctuation for letter in name])

    @staticmethod
    def presetToString(dictionary):
        '''Alphabetizes a dict into OrderedDict & returns string repr'''
        return repr(OrderedDict(sorted(dictionary.items(), key=lambda t: t[0])))

    @staticmethod
    def presetFromString(string):
        '''Turns a string repr of OrderedDict into a regular dict'''
        return dict(eval(string))
