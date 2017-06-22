from PyQt4 import QtCore
from PyQt4.QtCore import QSettings
import argparse
import os

import core
import video_thread
from main import LoadDefaultSettings


class Command(QtCore.QObject):

    videoTask = QtCore.pyqtSignal(str, str, list)

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.core = core.Core()
        self.dataDir = self.core.dataDir

        self.parser = argparse.ArgumentParser(
            description='Create a visualization for an audio file',
            epilog='EXAMPLE COMMAND:   main.py myvideotemplate.avp '
                '-i ~/Music/song.mp3 -o ~/video.mp4 '
                '-c 0 image ~/Pictures/thisWeeksPicture.jpg '
                '-c 1 vis classic')
        self.parser.add_argument(
            '-i', '--input', metavar='SOUND',
            help='input audio file', required=True)
        self.parser.add_argument(
            '-o', '--output', metavar='OUTPUT',
            help='output video file', required=True)

        # optional arguments
        self.parser.add_argument(
            'projpath', metavar='path-to-project',
            help='open a project file (.avp)', nargs='?')
        self.parser.add_argument(
            '-c', '--comp', metavar=('LAYER', 'NAME', 'ARG'),
            help='create component NAME at LAYER.'
            '"help" for information about possible args', nargs=3,
            action='append')

        '''
        self.parser.add_argument(
            '-b', '--background', dest='bgimage',
            help='background image file', required=True)
        self.parser.add_argument(
            '-t', '--text', dest='text', help='title text', required=True)
        self.parser.add_argument(
            '-f', '--font', dest='font', help='title font', required=False)
        self.parser.add_argument(
            '-s', '--fontsize', dest='fontsize',
            help='title font size', required=False)
        self.parser.add_argument(
            '-c', '--textcolor', dest='textcolor',
            help='title text color in r,g,b format', required=False)
        self.parser.add_argument(
            '-C', '--viscolor', dest='viscolor',
            help='visualization color in r,g,b format', required=False)
        self.parser.add_argument(
            '-x', '--xposition', dest='xposition',
            help='x position', required=False)
        self.parser.add_argument(
            '-y', '--yposition', dest='yposition',
            help='y position', required=False)
        self.parser.add_argument(
            '-a', '--alignment', dest='alignment',
            help='title alignment', required=False,
            type=int, choices=[0, 1, 2])
        '''

        self.args = self.parser.parse_args()
        self.settings = QSettings(
            os.path.join(self.dataDir, 'settings.ini'), QSettings.IniFormat)
        LoadDefaultSettings(self)

        if self.args.projpath:
            self.core.openProject(self, self.args.projpath)

        if self.args.comp:
            for comp in self.args.comp:
                pos, name, arg = comp
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
                self.core.selectedComponents[i].command(arg)

        self.createAudioVisualisation()

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

        compFileNames = [ \
            os.path.splitext(os.path.basename(
                mod.__file__))[0] \
            for mod in self.core.modules \
        ]
        for i, compFileName in enumerate(compFileNames):
            if name.lower() in compFileName:
                return self.core.compNames[i]
            return

        return None
