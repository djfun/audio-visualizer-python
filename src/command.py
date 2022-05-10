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
import glob
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
        parser = argparse.ArgumentParser(
            prog='avp' if os.path.basename(sys.argv[0]) == "__main__.py" else None,
            description='Create a visualization for an audio file',
            epilog='EXAMPLE COMMAND:   avp myvideotemplate '
                        '-i ~/Music/song.mp3 -o ~/video.mp4 '
                        '-c 0 image path=~/Pictures/thisWeeksPicture.jpg '
                        '-c 1 video "preset=My Logo" -c 2 vis layout=classic'
        )


        # input/output automatic-export commands
        parser.add_argument(
            '-i', '--input', metavar='SOUND',
            help='input audio file'
        )
        parser.add_argument(
            '-o', '--output', metavar='OUTPUT',
            help='output video file'
        )
        parser.add_argument(
            '--export-project', action='store_true',
            help='use input and output files from project file if -i or -o is missing'
        )

        # mutually exclusive debug options
        debugCommands = parser.add_mutually_exclusive_group()
        debugCommands.add_argument(
            '--test', action='store_true',
            help='run tests and create a report full of debugging info'
        )
        debugCommands.add_argument(
            '--debug', action='store_true',
            help='create bigger logfiles while program is running'
        )

        # project/GUI options
        parser.add_argument(
            'projpath', metavar='path-to-project',
            help='open a project file (.avp)', nargs='?')
        parser.add_argument(
            '-c', '--comp', metavar=('LAYER', 'ARG'),
            help='first arg must be component NAME to insert at LAYER.'
            '"help" for information about possible args for a component.',
            nargs='*', action='append')
        parser.add_argument(
            '--no-preview', action='store_true',
            help='disable live preview during export'
        )

        args = parser.parse_args()

        if args.debug:
            core.FILE_LOGLVL = logging.DEBUG
            core.STDOUT_LOGLVL = logging.DEBUG
            core.Core.makeLogger()

        if args.test:
            self.runTests()
            quit(0)

        if args.projpath:
            projPath = args.projpath
            if not os.path.dirname(projPath):
                projPath = os.path.join(
                    self.settings.value("projectDir"),
                    projPath
                )
            if not projPath.endswith('.avp'):
                projPath += '.avp'
            self.core.openProject(self, projPath)
            self.core.selectedComponents = list(
                reversed(self.core.selectedComponents))
            self.core.componentListChanged()

        if args.comp:
            for comp in args.comp:
                pos = comp[0]
                name = comp[1]
                compargs = comp[2:]
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
                for arg in compargs:
                    self.core.selectedComponents[i].command(arg)

        if args.export_project and args.projpath:
            errcode, data = self.core.parseAvFile(projPath)
            input_ = None
            output = None
            for key, value in data['WindowFields']:
                if 'outputFile' in key:
                    output = value
                    if output and not os.path.dirname(value):
                        output = os.path.join(
                            os.path.expanduser('~'),
                            output
                        )
                if 'audioFile' in key:
                    input_ = value

            # use input/output from project file, overwritten by -i and -o
            if (not input_ and not args.input) or (not output and not args.output):
                parser.print_help()
                quit(1)

            self.createAudioVisualization(
                input_ if not args.input else args.input,
                output if not args.output else args.output
            )
            return "commandline"

        elif args.input and args.output:
            self.createAudioVisualization(args.input, args.output)
            return "commandline"

        elif args.no_preview:
            core.Core.previewEnabled = False

        elif (
                args.projpath is None and 
                'help' not in sys.argv and
                '--debug' not in sys.argv and
                '--test' not in sys.argv
                ):
            parser.print_help()
            quit(1)

        return "GUI"

    def createAudioVisualization(self, input, output):
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
        self.quit(0)

    def quit(self, code):
        quit(code)

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
            with open(filename, "a") as f:
                f.write(f"{'='*60} debug log ends {'='*60}\n")
        except FileNotFoundError:
            with open(filename, "w") as f:
                f.write(f"{'='*60} no debug log {'='*60}\n")

        def concatenateLogs(logPattern):
            nonlocal filename
            renderLogs = glob.glob(os.path.join(core.Core.logDir, logPattern))
            with open(filename, "a") as fw:
                for renderLog in renderLogs:
                    with open(renderLog, "r") as fr:
                        fw.write(f"{'='*60} {os.path.basename(renderLog)} {'='*60}\n")
                        logContents = fr.readlines()
                        fw.write("".join(logContents[:5]))
                        fw.write("...trimmed...\n")
                        fw.write("".join(logContents[-10:]))
                        fw.write(f"{'='*60} {os.path.basename(renderLog)} {'='*60}\n")

        concatenateLogs("render_*.log")
        concatenateLogs("preview_*.log")

        # Append actual test report to debug log
        with open(filename, "a") as f:
            f.write(test_output)
        print(f"Test Report created at {filename}")
