from PyQt5 import QtCore
import argparse
import os
import sys

import core
import video_thread
from main import LoadDefaultSettings


class Command(QtCore.QObject):

    videoTask = QtCore.pyqtSignal(str, str, list)

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.core = core.Core()
        self.dataDir = self.core.dataDir
        self.canceled = False

        self.parser = argparse.ArgumentParser(
            description='Create a visualization for an audio file',
            epilog='EXAMPLE COMMAND:   main.py myvideotemplate.avp '
                        '-i ~/Music/song.mp3 -o ~/video.mp4 '
                        '-c 0 image path=~/Pictures/thisWeeksPicture.jpg '
                        '-c 1 video "preset=My Logo" -c 2 vis layout=classic')
        self.parser.add_argument(
            '-i', '--input', metavar='SOUND',
            help='input audio file')
        self.parser.add_argument(
            '-o', '--output', metavar='OUTPUT',
            help='output video file')

        # optional arguments
        self.parser.add_argument(
            'projpath', metavar='path-to-project',
            help='open a project file (.avp)', nargs='?')
        self.parser.add_argument(
            '-c', '--comp', metavar=('LAYER', 'ARG'),
            help='first arg must be component NAME to insert at LAYER.'
            '"help" for information about possible args for a component.',
            nargs='*', action='append')

        self.args = self.parser.parse_args()
        self.settings = self.core.settings
        LoadDefaultSettings(self)

        if self.args.projpath:
            self.core.openProject(self, self.args.projpath)
            self.core.selectedComponents = list(
                reversed(self.core.selectedComponents))
            self.core.componentListChanged()

        if self.args.comp:
            for comp in self.args.comp:
                pos = comp[0]
                name = comp[1]
                args = comp[2:]
                try:
                    pos = int(pos)
                except ValueError:
                    print(pos, 'is not a layer number.')
                    quit(1)
                realName = self.parseCompName(name)
                if not realName:
                    print(name, 'is not a valid component name.')
                    quit(1)
                modI = self.core.moduleIndexFor(realName)
                i = self.core.insertComponent(pos, modI, self)
                for arg in args:
                    self.core.selectedComponents[i].command(arg)

        if self.args.input and self.args.output:
            self.createAudioVisualisation()
        elif 'help' not in sys.argv:
            self.parser.print_help()
            quit(1)

    def createAudioVisualisation(self):
        self.videoThread = QtCore.QThread(self)
        self.videoWorker = video_thread.Worker(self)
        self.videoWorker.moveToThread(self.videoThread)
        self.videoWorker.videoCreated.connect(self.videoCreated)

        self.videoThread.start()
        self.videoTask.emit(
          self.args.input,
          self.args.output,
          list(reversed(self.core.selectedComponents))
        )

    def videoCreated(self):
        self.videoThread.quit()
        self.videoThread.wait()
        quit(0)

    def showMessage(self, **kwargs):
        print(kwargs['msg'])
        if 'detail' in kwargs:
            print(kwargs['detail'])

    def drawPreview(self, *args):
        pass

    def parseCompName(self, name):
        '''Deduces a proper component name out of a commandline arg'''

        if name.title() in self.core.compNames:
            return name.title()
        for compName in self.core.compNames:
            if name.capitalize() in compName:
                return compName

        compFileNames = [
            os.path.splitext(
                os.path.basename(mod.__file__)
            )[0]
            for mod in self.core.modules
        ]
        for i, compFileName in enumerate(compFileNames):
            if name.lower() in compFileName:
                return self.core.compNames[i]
            return

        return None
