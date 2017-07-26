'''
    Base classes for components to import. Read comments for some documentation
    on making a valid component.
'''
from PyQt5 import uic, QtCore, QtWidgets
import os


class ComponentMetaclass(type(QtCore.QObject)):
    '''
        Checks the validity of each Component class imported, and
        mutates some attributes for easier use by the core program.
        E.g., takes only major version from version string & decorates methods
    '''

    def initializationWrapper(func):
        def initializationWrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception:
                try:
                    raise ComponentError(self, 'initialization process')
                except ComponentError:
                    return
        return initializationWrapper

    def renderWrapper(func):
        def renderWrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception:
                from toolkit.frame import BlankFrame
                try:
                    raise ComponentError(self, 'renderer')
                except ComponentError:
                    return BlankFrame()
        return renderWrapper

    def commandWrapper(func):
        '''Intercepts the command() method to check for global args'''
        def commandWrapper(self, arg):
            if arg.startswith('preset='):
                from presetmanager import getPresetDir
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
                    # Don't call the component's command() method
                    return
            else:
                return func(self, arg)
        return commandWrapper

    def propertiesWrapper(func):
        '''Intercepts the usual properties if the properties are locked.'''
        def propertiesWrapper(self):
            if self._lockedProperties is not None:
                return self._lockedProperties
            else:
                try:
                    return func(self)
                except Exception:
                    try:
                        raise ComponentError(self, 'properties')
                    except ComponentError:
                        return []
        return propertiesWrapper

    def errorWrapper(func):
        '''Intercepts the usual error message if it is locked.'''
        def errorWrapper(self):
            if self._lockedError is not None:
                return self._lockedError
            else:
                return func(self)
        return errorWrapper

    def __new__(cls, name, parents, attrs):
        if 'ui' not in attrs:
            # Use module name as ui filename by default
            attrs['ui'] = '%s.ui' % os.path.splitext(
                    attrs['__module__'].split('.')[-1]
                )[0]

        # if parents[0] == QtCore.QObject: else:
        decorate = (
            'names',                            # Class methods
            'error', 'audio', 'properties',     # Properties
            'preFrameRender', 'previewRender',
            'command',
        )

        # Auto-decorate methods
        for key in decorate:
            if key not in attrs:
                continue

            if key in ('names'):
                attrs[key] = classmethod(attrs[key])

            if key in ('audio'):
                attrs[key] = property(attrs[key])

            if key == 'command':
                attrs[key] = cls.commandWrapper(attrs[key])

            if key == 'previewRender':
                attrs[key] = cls.renderWrapper(attrs[key])

            if key == 'preFrameRender':
                attrs[key] = cls.initializationWrapper(attrs[key])

            if key == 'properties':
                attrs[key] = cls.propertiesWrapper(attrs[key])

            if key == 'error':
                attrs[key] = cls.errorWrapper(attrs[key])

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
    # ui = 'name_Of_Non_Default_Ui_File'

    version = '1.0.0'
    # The major version (before the first dot) is used to determine
    # preset compatibility; the rest is ignored so it can be non-numeric.

    modified = QtCore.pyqtSignal(int, dict)
    _error = QtCore.pyqtSignal(str, str)

    def __init__(self, moduleIndex, compPos, core):
        super().__init__()
        self.moduleIndex = moduleIndex
        self.compPos = compPos
        self.core = core
        self.currentPreset = None

        self._trackedWidgets = {}
        self._presetNames = {}
        self._commandArgs = {}
        self._lockedProperties = None
        self._lockedError = None

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
            Or tuple of two strings for a message with details.
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

    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
    # Methods
    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~

    def widget(self, parent):
        '''
            Call super().widget(*args) to create the component widget
            which also auto-connects any common widgets (e.g., checkBoxes)
            to self.update(). Then in a subclass connect special actions
            (e.g., pushButtons to select a file/colour) and initialize
        '''
        self.parent = parent
        self.settings = parent.settings
        self.page = self.loadUi(self.__class__.ui)

        # Connect widget signals
        widgets = {
            'lineEdit': self.page.findChildren(QtWidgets.QLineEdit),
            'checkBox': self.page.findChildren(QtWidgets.QCheckBox),
            'spinBox': self.page.findChildren(QtWidgets.QSpinBox),
            'comboBox': self.page.findChildren(QtWidgets.QComboBox),
        }
        widgets['spinBox'].extend(
            self.page.findChildren(QtWidgets.QDoubleSpinBox)
        )
        for widget in widgets['lineEdit']:
            widget.textChanged.connect(self.update)
        for widget in widgets['checkBox']:
            widget.stateChanged.connect(self.update)
        for widget in widgets['spinBox']:
            widget.valueChanged.connect(self.update)
        for widget in widgets['comboBox']:
            widget.currentIndexChanged.connect(self.update)

    def trackWidgets(self, trackDict, **kwargs):
        '''
            Name widgets to track in update(), savePreset(), loadPreset(), and
            command(). Requires a dict of attr names as keys, widgets as values

            Optional args:
                'presetNames': preset variable names to replace attr names
                'commandArgs': arg keywords that differ from attr names

            NOTE: Any kwarg key set to None will selectively disable tracking.
        '''
        self._trackedWidgets = trackDict
        for kwarg in kwargs:
            try:
                if kwarg in ('presetNames', 'commandArgs'):
                    setattr(self, '_%s' % kwarg, kwargs[kwarg])
                else:
                    raise ComponentError(
                        self, 'Nonsensical keywords to trackWidgets.')
            except ComponentError:
                continue

    def update(self):
        '''
            Reads all tracked widget values into instance attributes
            and tells the MainWindow that the component was modified.
            Call at the END of your method if you need to subclass this.
        '''
        for attr, widget in self._trackedWidgets.items():
            if type(widget) == QtWidgets.QLineEdit:
                setattr(self, attr, widget.text())
            elif type(widget) == QtWidgets.QSpinBox \
                    or type(widget) == QtWidgets.QDoubleSpinBox:
                setattr(self, attr, widget.value())
            elif type(widget) == QtWidgets.QCheckBox:
                setattr(self, attr, widget.isChecked())
            elif type(widget) == QtWidgets.QComboBox:
                setattr(self, attr, widget.currentIndex())
        if not self.core.openingProject:
            self.parent.drawPreview()
            saveValueStore = self.savePreset()
            saveValueStore['preset'] = self.currentPreset
            self.modified.emit(self.compPos, saveValueStore)

    def loadPreset(self, presetDict, presetName=None):
        '''
            Subclasses should take (presetDict, *args) as args.
            Must use super().loadPreset(presetDict, *args) first,
            then update self.page widgets using the preset dict.
        '''
        self.currentPreset = presetName \
            if presetName is not None else presetDict['preset']
        for attr, widget in self._trackedWidgets.items():
            val = presetDict[
                attr if attr not in self._presetNames
                else self._presetNames[attr]
            ]
            if type(widget) == QtWidgets.QLineEdit:
                widget.setText(val)
            elif type(widget) == QtWidgets.QSpinBox \
                    or type(widget) == QtWidgets.QDoubleSpinBox:
                widget.setValue(val)
            elif type(widget) == QtWidgets.QCheckBox:
                widget.setChecked(val)
            elif type(widget) == QtWidgets.QComboBox:
                widget.setCurrentIndex(val)

    def savePreset(self):
        saveValueStore = {}
        for attr, widget in self._trackedWidgets.items():
            saveValueStore[
                attr if attr not in self._presetNames
                else self._presetNames[attr]
            ] = getattr(self, attr)
        return saveValueStore

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

    def commandHelp(self):
        '''Help text as string for this component's commandline arguments'''

    def command(self, arg=''):
        '''
            Configure a component using an arg from the commandline. This is
            never called if global args like 'preset=' are found in the arg.
            So simply check for any non-global args in your component and
            call super().command() at the end to get a Help message.
        '''
        print(
            self.__class__.name, 'Usage:\n'
            'Open a preset for this component:\n'
            '    "preset=Preset Name"'
        )
        self.commandHelp()
        quit(0)

    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
    # "Private" Methods
    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~

    def lockProperties(self, propList):
        self._lockedProperties = propList

    def lockError(self, msg):
        self._lockedError = msg

    def unlockProperties(self):
        self._lockedProperties = None

    def unlockError(self):
        self._lockedError = None

    def loadUi(self, filename):
        '''Load a Qt Designer ui file to use for this component's widget'''
        return uic.loadUi(os.path.join(self.core.componentsPath, filename))

    def cancel(self):
        '''Stop any lengthy process in response to this variable.'''
        self.canceled = True

    def reset(self):
        self.canceled = False
        self.unlockProperties()
        self.unlockError()

    '''
    ### Reference methods for creating a new component
    ### (Inherit from this class and define these)

    def previewRender(self, previewWorker):
        width = int(self.settings.value('outputWidth'))
        height = int(self.settings.value('outputHeight'))
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


class ComponentError(RuntimeError):
    '''Gives the MainWindow a traceback to display, and cancels the export.'''

    prevErrors = []

    def __init__(self, caller, name):
        print('ComponentError by %s: %s' % (caller.name, name))
        super().__init__()
        if len(ComponentError.prevErrors) > 1:
            ComponentError.prevErrors.pop()
        ComponentError.prevErrors.insert(0, name)
        if name in ComponentError.prevErrors[1:]:
            # Don't create multiple windows for repeated messages
            return

        from toolkit import formatTraceback
        import sys
        if sys.exc_info()[0] is not None:
            string = (
                "%s component's %s encountered %s %s." % (
                    caller.__class__.name,
                    name,
                    'an' if any([
                        sys.exc_info()[0].__name__.startswith(vowel)
                        for vowel in ('A', 'I')
                    ]) else 'a',
                    sys.exc_info()[0].__name__,
                )
            )
            detail = formatTraceback(sys.exc_info()[2])
        else:
            string = name
            detail = "Methods:\n%s" % (
                "\n".join(
                    [m for m in dir(caller) if not m.startswith('_')]
                )
            )

        caller._error.emit(string, detail)
