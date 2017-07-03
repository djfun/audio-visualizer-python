from PyQt5 import uic, QtCore, QtWidgets
from PIL import Image
import os


class Component(QtCore.QObject):
    '''A base class for components to inherit from'''

    # modified = QtCore.pyqtSignal(int, bool)

    def __init__(self, moduleIndex, compPos, core):
        super().__init__()
        self.currentPreset = None
        self.canceled = False
        self.moduleIndex = moduleIndex
        self.compPos = compPos
        self.core = core

    def __str__(self):
        return self.__doc__

    def version(self):
        # change this number to identify new versions of a component
        return 1

    def cancel(self):
        # please stop any lengthy process in response to this variable
        self.canceled = True

    def reset(self):
        self.canceled = False

    def update(self):
        self.modified.emit(self.compPos, self.savePreset())
        # read your widget values, then call super().update()

    def loadPreset(self, presetDict, presetName):
        '''Subclasses take (presetDict, presetName=None) as args.
        Must use super().loadPreset(presetDict, presetName) first,
        then update self.page widgets using the preset dict.
        '''
        self.currentPreset = presetName \
            if presetName is not None else presetDict['preset']

    def preFrameRender(self, **kwargs):
        '''Triggered only before a video is exported (video_thread.py)
            self.worker = the video thread worker
            self.completeAudioArray = a list of audio samples
            self.sampleSize = number of audio samples per video frame
            self.progressBarUpdate = signal to set progress bar number
            self.progressBarSetText = signal to set progress bar text
        Use the latter two signals to update the MainProgram if needed
        for a long initialization procedure (i.e., for a visualizer)
        '''
        for var, value in kwargs.items():
            exec('self.%s = value' % var)

    def command(self, arg):
        '''Configure a component using argument from the commandline.
        Use super().command(arg) at the end of a subclass's method,
        if no arguments are found in that method first
        '''
        if arg.startswith('preset='):
            _, preset = arg.split('=', 1)
            path = os.path.join(self.core.getPresetDir(self), preset)
            if not os.path.exists(path):
                print('Couldn\'t locate preset "%s"' % preset)
                quit(1)
            else:
                print('Opening "%s" preset on layer %s' % (
                    preset, self.compPos)
                )
                self.core.openPreset(path, self.compPos, preset)
        else:
            print(
                self.__doc__, 'Usage:\n'
                'Open a preset for this component:\n'
                '    "preset=Preset Name"')
            self.commandHelp()
            quit(0)

    def commandHelp(self):
        '''Print help text for this Component's commandline arguments'''

    def blankFrame(self, width, height):
        return Image.new("RGBA", (width, height), (0, 0, 0, 0))

    def pickColor(self):
        '''Use color picker to get color input from the user,
        and return this as an RGB string and QPushButton stylesheet.
        In a subclass apply stylesheet to any color selection widgets
        '''
        dialog = QtWidgets.QColorDialog()
        dialog.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, True)
        color = dialog.getColor()
        if color.isValid():
            RGBstring = '%s,%s,%s' % (
                str(color.red()), str(color.green()), str(color.blue()))
            btnStyle = "QPushButton{background-color: %s; outline: none;}" \
                % color.name()
            return RGBstring, btnStyle
        else:
            return None, None

    def RGBFromString(self, string):
        ''' Turns an RGB string like "255, 255, 255" into a tuple '''
        try:
            tup = tuple([int(i) for i in string.split(',')])
            if len(tup) != 3:
                raise ValueError
            for i in tup:
                if i > 255 or i < 0:
                    raise ValueError
            return tup
        except:
            return (255, 255, 255)

    def loadUi(self, filename):
        return uic.loadUi(os.path.join(self.core.componentsPath, filename))

    '''
    ### Reference methods for creating a new component
    ### (Inherit from this class and define these)

    def widget(self, parent):
        self.parent = parent
        page = uic.loadUi(os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'example.ui'))
        # --- connect widget signals here ---
        self.page = page
        return page

    def update(self):
        super().update()
        self.parent.drawPreview()

    def previewRender(self, previewWorker):
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        image = Image.new("RGBA", (width, height), (0,0,0,0))
        return image

    def frameRender(self, moduleNo, frameNo):
        width = int(self.worker.core.settings.value('outputWidth'))
        height = int(self.worker.core.settings.value('outputHeight'))
        image = Image.new("RGBA", (width, height), (0,0,0,0))
        return image

    @classmethod
    def names(cls):
        # Alternative names for renaming a component between project files
        return []
    '''


class BadComponentInit(Exception):
    def __init__(self, arg, name):
        string = '''################################
Mandatory argument "%s" not specified
  in %s instance initialization
###################################'''
        print(string % (arg, name))
        quit()
