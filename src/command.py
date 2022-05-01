'''
    When using commandline mode, this module's object handles interpreting
    the arguments and giving them to Core, which tracks the main program state.
    Then it immediately exports a video.
'''
from PyQt5 import QtCore
import argparse
import os
import sys
import time
import signal
import shutil
import logging

from . import core


log = logging.getLogger('AVP.Commandline')


class Command(QtCore.QObject):
    """
        This replaces the GUI MainWindow when in commandline mode.
    """

    createVideo = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.core = core.Core()
        core.Core.mode = 'commandline'
        self.dataDir = self.core.dataDir
        self.canceled = False
        self.settings = core.Core.settings

        # ctrl-c stops the export thread
        signal.signal(signal.SIGINT, self.stopVideo)

    def parseArgs(self):
        self.parser = argparse.ArgumentParser(
            description='Create a visualization for an audio file',
            epilog='EXAMPLE COMMAND:   main.py myvideotemplate.avp '
                        '-i ~/Music/song.mp3 -o ~/video.mp4 '
                        '-c 0 image path=~/Pictures/thisWeeksPicture.jpg '
                        '-c 1 video "preset=My Logo" -c 2 vis layout=classic'
        )
        self.parser.add_argument(
            '-i', '--input', metavar='SOUND',
            help='input audio file'
        )
        self.parser.add_argument(
            '-o', '--output', metavar='OUTPUT',
            help='output video file'
        )
        self.parser.add_argument(
            '--export-project', action='store_true',
            help='ignore -i and -o, use input and output from project file'
        )
        self.parser.add_argument(
            '--test', action='store_true',
            help='run tests, generate logfiles, then exit'
        )
        self.parser.add_argument(
            '--debug', action='store_true',
            help='create bigger logfiles while program is running'
        )

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

        if self.args.debug:
            core.FILE_LOGLVL = logging.DEBUG
            core.STDOUT_LOGLVL = logging.DEBUG
            core.Core.makeLogger()

        if self.args.test:
            self.runTests()
            quit(0)

        if self.args.projpath:
            projPath = self.args.projpath
            if not os.path.dirname(projPath):
                projPath = os.path.join(
                    self.settings.value("projectDir"),
                    projPath
                )
            if not projPath.endswith('.avp'):
                projPath += '.avp'
            success = self.core.openProject(self, projPath)
            if not success:
                quit(1)
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

        if self.args.export_project and self.args.projpath:
            errcode, data = self.core.parseAvFile(projPath)
            for key, value in data['WindowFields']:
                if 'outputFile' in key:
                    output = value
                    if not os.path.dirname(value):
                        output = os.path.join(
                            os.path.expanduser('~'),
                            output
                        )
                if 'audioFile' in key:
                    input = value
            self.createAudioVisualisation(input, output)
            return "commandline"

        elif self.args.input and self.args.output:
            self.createAudioVisualisation(self.args.input, self.args.output)
            return "commandline"

        elif 'help' not in sys.argv and self.args.projpath is None and '--debug' not in sys.argv:
            self.parser.print_help()
            quit(1)

        return "GUI"

    def createAudioVisualisation(self, input, output):
        self.core.selectedComponents = list(
            reversed(self.core.selectedComponents))
        self.core.componentListChanged()
        self.worker = self.core.newVideoWorker(
            self, input, output
        )
        # quit(0) after video is created
        self.worker.videoCreated.connect(self.videoCreated)
        self.lastProgressUpdate = time.time()
        self.worker.progressBarSetText.connect(self.progressBarSetText)
        self.createVideo.emit()

    def stopVideo(self, *args):
        self.worker.error = True
        self.worker.cancelExport()
        self.worker.cancel()

    @QtCore.pyqtSlot(str)
    def progressBarSetText(self, value):
        if 'Export ' in value:
            # Don't duplicate completion/failure messages
            return
        if not value.startswith('Exporting') \
                and time.time() - self.lastProgressUpdate >= 0.05:
            # Show most messages very often
            print(value)
        elif time.time() - self.lastProgressUpdate >= 2.0:
            # Give user time to read ffmpeg's output during the export
            print('##### %s' % value)
        else:
            return
        self.lastProgressUpdate = time.time()

    @QtCore.pyqtSlot()
    def videoCreated(self):
        quit(0)

    def showMessage(self, **kwargs):
        print(kwargs['msg'])
        if 'detail' in kwargs:
            print(kwargs['detail'])

    @QtCore.pyqtSlot(str, str)
    def videoThreadError(self, msg, detail):
        print(msg)
        print(detail)
        quit(1)

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

    def runTests(self):
        core.FILE_LOGLVL = logging.DEBUG
        core.Core.makeLogger()
        from . import tests
        test_report = os.path.join(core.Core.logDir, "test_report.log")
        tests.run(test_report)

        # Print test report into terminal
        with open(test_report, "r") as f:
            output = f.readlines()
        test_output = "".join(output)
        print(test_output)

        # Choose a numbered location to put the output file
        logNumber = 0
        def getFilename():
            """Get a numbered filename for the final test report"""
            nonlocal logNumber
            name = os.path.join(os.path.expanduser('~'), "avp_test_report")
            while True:
                possibleName = f"{name}{logNumber:0>2}.txt"
                if os.path.exists(possibleName) and logNumber < 100:
                    logNumber += 1
                    continue
                break
            return possibleName

        # Copy latest debug log to chosen test report location
        filename = getFilename()
        if logNumber == 100:
            print("Test Report could not be created.")
            return
        try:
            shutil.copy(os.path.join(core.Core.logDir, "avp_debug.log"), filename)
        except FileNotFoundError:
            print("No debug log found.")
        # Append actual test report to debug log
        with open(filename, "a") as f:
            f.write(f"{'='*59} debug log ends {'='*59}\n")
            f.write(test_output)
        print(f"Test Report created at {filename}")
