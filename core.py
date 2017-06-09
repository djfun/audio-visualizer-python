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

        self.modules = self.findComponents()
        self.selectedComponents = []
        self.selectedModules = []

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
        return [
            import_module('components.%s' % name)
            for name in findComponents()]

    def insertComponent(self, compPos, moduleIndex):
        if compPos < 0:
            compPos = len(self.selectedComponents) -1
        self.selectedComponents.insert(
            compPos,
            self.modules[moduleIndex].Component()
        )
        self.selectedModules.insert(
            compPos,
            moduleIndex
        )
        return compPos

    def moveComponent(self, startI, endI):
        comp = self.selectedComponents.pop(startI)
        self.selectedComponents.insert(endI, comp)
        i = self.selectedModules.pop(startI)
        self.selectedModules.insert(endI, i)
        return endI

    def updateComponent(self, i):
        print('updating %s' % self.selectedComponents[i])
        self.selectedComponents[i].update()

    def moduleIndexFor(self, compIndex):
        return self.selectedModules[compIndex]

    def createPresetFile(self, compName, vers, saveValueStore, filename):
        dirname = os.path.join(self.presetDir, compName, str(vers))
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        filepath = os.path.join(dirname, filename)
        with open(filepath, 'w') as f:
            f.write(Core.stringOrderedDict(saveValueStore))

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
        badName = False
        for letter in name:
            if letter in string.punctuation:
                badName = True
        return badName

    @staticmethod
    def stringOrderedDict(dictionary):
        sorted_ = OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))
        return repr(sorted_)
