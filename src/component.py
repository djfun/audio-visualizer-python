'''
    Base classes for components to import. Read comments for some documentation
    on making a valid component.
'''
from PyQt5 import uic, QtCore, QtWidgets
import os

from core import Core
from toolkit.common import getPresetDir


class ComponentMetaclass(type(QtCore.QObject)):
    '''
        Checks the validity of each Component class imported, and
        mutates some attributes for easier use by the core program.
        E.g., takes only major version from version string & decorates methods
    '''
    def __new__(cls, name, parents, attrs):
        # print('Creating %s component' % attrs['name'])

        # Turn certain class methods into properties and classmethods
        for key in ('error', 'properties', 'audio', 'commandHelp'):
            if key not in attrs:
                continue
            attrs[key] = property(attrs[key])

        for key in ('names'):
            if key not in attrs:
                continue
            attrs[key] = classmethod(key)

        # Turn version string into a number
        try:
            if 'version' not in attrs:
                print(
                    'No version attribute in %s. Defaulting to 1' %
                    attrs['name'])
                attrs['version'] = 1
            else:
                attrs['version'] = int(attrs['version'].split('.')[0])
        except ValueError:
            print('%s component has an invalid version string:\n%s' % (
                    attrs['name'], str(attrs['version'])))
        except KeyError:
            print('%s component has no version string.' % attrs['name'])
        else:
            return super().__new__(cls, name, parents, attrs)
        quit(1)


class Component(QtCore.QObject, metaclass=ComponentMetaclass):
    '''
        The base class for components to inherit.
    '''

    name = 'Component'
    version = '1.0.0'
    # The 1st number (before dot, aka the major version) is used to determine
    # preset compatibility; the rest is ignored so it can be non-numeric.

    modified = QtCore.pyqtSignal(int, dict)
    # ^ Signal used to tell core program that the component state changed,
    # you shouldn't need to use this directly, it is used by self.update()

    def __init__(self, moduleIndex, compPos):
        super().__init__()
        self.currentPreset = None
        self.moduleIndex = moduleIndex
        self.compPos = compPos

        # Stop lengthy processes in response to this variable
        self.canceled = False

    def __str__(self):
        return self.__class__.name

    def __repr__(self):
        return '%s\n%s\n%s' % (
            self.__class__.name, str(self.__class__.version), self.savePreset()
        )

    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
    # Properties
    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~

    def properties(self):
        '''
            Return a list of properties to signify if your component is
            non-animated ('static'), returns sound ('audio'), or has
            encountered an error in configuration ('error').
        '''
        return []

    def error(self):
        '''
            Return a string containing an error message, or None for a default.
        '''
        return

    def audio(self):
        '''
            Return audio to mix into master as a tuple with two elements:
            The first element can be:
                - A string (path to audio file),
                - Or an object that returns audio data through a pipe
            The second element must be a dictionary of ffmpeg filters/options
            to apply to the input stream. See the filter docs for ideas:
            https://ffmpeg.org/ffmpeg-filters.html
        '''

    def names():
        '''
            Alternative names for renaming a component between project files.
        '''
        return []

    def commandHelp(self):
        '''Help text as string for this component's commandline arguments'''

    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
    # Methods
    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~

    def update(self):
        '''Read widget values from self.page, then call super().update()'''
        self.parent.drawPreview()
        saveValueStore = self.savePreset()
        saveValueStore['preset'] = self.currentPreset
        self.modified.emit(self.compPos, saveValueStore)

    def loadPreset(self, presetDict, presetName):
        '''
            Subclasses take (presetDict, presetName=None) as args.
            Must use super().loadPreset(presetDict, presetName) first,
            then update self.page widgets using the preset dict.
        '''
        self.currentPreset = presetName \
            if presetName is not None else presetDict['preset']

    def preFrameRender(self, **kwargs):
        '''
            Triggered only before a video is exported (video_thread.py)
                self.worker = the video thread worker
                self.completeAudioArray = a list of audio samples
                self.sampleSize = number of audio samples per video frame
                self.progressBarUpdate = signal to set progress bar number
                self.progressBarSetText = signal to set progress bar text
            Use the latter two signals to update the MainWindow if needed
            for a long initialization procedure (i.e., for a visualizer)
        '''
        for key, value in kwargs.items():
            setattr(self, key, value)

    def command(self, arg):
        '''
            Configure a component using argument from the commandline.
            Use super().command(arg) at the end of a subclass's method,
            if no arguments are found in that method first
        '''
        if arg.startswith('preset='):
            _, preset = arg.split('=', 1)
            path = os.path.join(getPresetDir(self), preset)
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
            print(self.commandHelp)
            quit(0)

    def loadUi(self, filename):
        '''Load a Qt Designer ui file to use for this component's widget'''
        return uic.loadUi(os.path.join(Core.componentsPath, filename))

    def cancel(self):
        '''Stop any lengthy process in response to this variable.'''
        self.canceled = True

    def reset(self):
        self.canceled = False

    '''
    ### Reference methods for creating a new component
    ### (Inherit from this class and define these)

    def widget(self, parent):
        self.parent = parent
        self.settings = parent.settings
        self.page = self.loadUi('example.ui')
        # --- connect widget signals here ---
        return self.page

    def previewRender(self, previewWorker):
        width = int(self.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        from toolkit.frame import BlankFrame
        image = BlankFrame(width, height)
        return image

    def frameRender(self, layerNo, frameNo):
        audioArrayIndex = frameNo * self.sampleSize
        width = int(self.settings.value('outputWidth'))
        height = int(self.settings.value('outputHeight'))
        from toolkit.frame import BlankFrame
        image = BlankFrame(width, height)
        return image
    '''


class BadComponentInit(Exception):
    '''
        General purpose exception components can raise to indicate
        a Python issue with e.g., dynamic creation of instances or something.
        Decorative for now, may have future use for logging.
    '''
    def __init__(self, arg, name):
        string = '''################################
Mandatory argument "%s" not specified
  in %s instance initialization
###################################'''
        print(string % (arg, name))
        quit()
