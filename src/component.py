'''
    Base classes for components to import. Read comments for some documentation
    on making a valid component.
'''
from PyQt5 import uic, QtCore, QtWidgets
from PyQt5.QtGui import QColor
import os
import sys
import math
import time

from toolkit.frame import BlankFrame
from toolkit import (
    getWidgetValue, setWidgetValue, connectWidget, rgbFromString
)


class ComponentMetaclass(type(QtCore.QObject)):
    '''
        Checks the validity of each Component class and mutates some attrs.
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
            except Exception as e:
                try:
                    if e.__class__.__name__.startswith('Component'):
                        raise
                    else:
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
            'frameRender', 'command',
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

            if key in ('previewRender', 'frameRender'):
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
        self._colorWidgets = {}
        self._colorFuncs = {}
        self._relativeWidgets = {}
        # pixel values stored as floats
        self._relativeValues = {}
        # maximum values of spinBoxes at 1080p (Core.resolutions[0])
        self._relativeMaximums = {}

        self._lockedProperties = None
        self._lockedError = None
        self._lockedSize = None

        # Stop lengthy processes in response to this variable
        self.canceled = False

    def __str__(self):
        return self.__class__.name

    def __repr__(self):
        try:
            preset = self.savePreset()
        except Exception as e:
            preset = '%s occured while saving preset' % str(e)
        return '%s\n%s\n%s' % (
            self.__class__.name, str(self.__class__.version), preset
        )

    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
    # Render Methods
    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~

    def previewRender(self):
        image = BlankFrame(self.width, self.height)
        return image

    def preFrameRender(self, **kwargs):
        '''
            Must call super() when subclassing
            Triggered only before a video is exported (video_thread.py)
                self.audioFile = filepath to the main input audio file
                self.completeAudioArray = a list of audio samples
                self.sampleSize = number of audio samples per video frame
                self.progressBarUpdate = signal to set progress bar number
                self.progressBarSetText = signal to set progress bar text
            Use the latter two signals to update the MainWindow if needed
            for a long initialization procedure (i.e., for a visualizer)
        '''
        for key, value in kwargs.items():
            setattr(self, key, value)

    def frameRender(self, frameNo):
        audioArrayIndex = frameNo * self.sampleSize
        image = BlankFrame(self.width, self.height)
        return image

    def postFrameRender(self):
        pass

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
            Alternatively use lockError(msgString) within properties()
            to skip this method entirely.
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
    # Idle Methods
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
        for widgetList in widgets.values():
            for widget in widgetList:
                connectWidget(widget, self.update)

    def update(self):
        '''
            Reads all tracked widget values into instance attributes
            and tells the MainWindow that the component was modified.
            Call super() at the END if you need to subclass this.
        '''
        for attr, widget in self._trackedWidgets.items():
            if attr in self._colorWidgets:
                # Color Widgets: text stored as tuple & update the button color
                rgbTuple = rgbFromString(widget.text())
                btnStyle = (
                    "QPushButton { background-color : %s; outline: none; }"
                    % QColor(*rgbTuple).name())
                self._colorWidgets[attr].setStyleSheet(btnStyle)
                setattr(self, attr, rgbTuple)

            elif attr in self._relativeWidgets:
                # Relative widgets: number scales to fit export resolution
                self.updateRelativeWidget(attr)
                setattr(self, attr, self._trackedWidgets[attr].value())

            else:
                # Normal tracked widget
                setattr(self, attr, getWidgetValue(widget))

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
            key = attr if attr not in self._presetNames \
                else self._presetNames[attr]
            val = presetDict[key]

            if attr in self._colorWidgets:
                widget.setText('%s,%s,%s' % val)
                btnStyle = (
                    "QPushButton { background-color : %s; outline: none; }"
                    % QColor(*val).name()
                )
                self._colorWidgets[attr].setStyleSheet(btnStyle)
            else:
                setWidgetValue(widget, val)

    def savePreset(self):
        saveValueStore = {}
        for attr, widget in self._trackedWidgets.items():
            saveValueStore[
                attr if attr not in self._presetNames
                else self._presetNames[attr]
            ] = getattr(self, attr)
        return saveValueStore

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
                if kwarg in (
                        'presetNames',
                        'commandArgs',
                        'colorWidgets',
                        'relativeWidgets',
                        ):
                    setattr(self, '_%s' % kwarg, kwargs[kwarg])
                else:
                    raise ComponentError(
                        self, 'Nonsensical keywords to trackWidgets.')
            except ComponentError:
                continue

            if kwarg == 'colorWidgets':
                def makeColorFunc(attr):
                    def pickColor_():
                        self.pickColor(
                            self._trackedWidgets[attr],
                            self._colorWidgets[attr]
                        )
                    return pickColor_
                self._colorFuncs = {
                    attr: makeColorFunc(attr) for attr in kwargs[kwarg]
                }
                for attr, func in self._colorFuncs.items():
                    self._colorWidgets[attr].clicked.connect(func)
                    self._colorWidgets[attr].setStyleSheet(
                        "QPushButton {"
                        "background-color : #FFFFFF; outline: none; }"
                    )

            if kwarg == 'relativeWidgets':
                # store maximum values of spinBoxes to be scaled appropriately
                for attr in kwargs[kwarg]:
                    self._relativeMaximums[attr] = \
                            self._trackedWidgets[attr].maximum()
                    self.updateRelativeWidgetMaximum(attr)

    def pickColor(self, textWidget, button):
        '''Use color picker to get color input from the user.'''
        dialog = QtWidgets.QColorDialog()
        dialog.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, True)
        color = dialog.getColor()
        if color.isValid():
            RGBstring = '%s,%s,%s' % (
                str(color.red()), str(color.green()), str(color.blue()))
            btnStyle = "QPushButton{background-color: %s; outline: none;}" \
                % color.name()
            textWidget.setText(RGBstring)
            button.setStyleSheet(btnStyle)

    def lockProperties(self, propList):
        self._lockedProperties = propList

    def lockError(self, msg):
        self._lockedError = msg

    def lockSize(self, w, h):
        self._lockedSize = (w, h)

    def unlockProperties(self):
        self._lockedProperties = None

    def unlockError(self):
        self._lockedError = None

    def unlockSize(self):
        self._lockedSize = None

    def loadUi(self, filename):
        '''Load a Qt Designer ui file to use for this component's widget'''
        return uic.loadUi(os.path.join(self.core.componentsPath, filename))

    @property
    def width(self):
        if self._lockedSize is None:
            return int(self.settings.value('outputWidth'))
        else:
            return self._lockedSize[0]

    @property
    def height(self):
        if self._lockedSize is None:
            return int(self.settings.value('outputHeight'))
        else:
            return self._lockedSize[1]

    def cancel(self):
        '''Stop any lengthy process in response to this variable.'''
        self.canceled = True

    def reset(self):
        self.canceled = False
        self.unlockProperties()
        self.unlockError()

    def updateRelativeWidget(self, attr):
        dimension = self.width
        if 'height' in attr.lower() \
                or 'ypos' in attr.lower() or attr == 'y':
            dimension = self.height
        try:
            oldUserValue = getattr(self, attr)
        except AttributeError:
            oldUserValue = self._trackedWidgets[attr].value()
        newUserValue = self._trackedWidgets[attr].value()
        newRelativeVal = newUserValue / dimension

        if attr in self._relativeValues:
            oldRelativeVal = self._relativeValues[attr]
            if oldUserValue == newUserValue \
                    and oldRelativeVal != newRelativeVal:
                # Float changed without pixel value changing, which
                # means the pixel value needs to be updated
                self._trackedWidgets[attr].blockSignals(True)
                self.updateRelativeWidgetMaximum(attr)
                self._trackedWidgets[attr].setValue(
                    math.ceil(dimension * oldRelativeVal))
                self._trackedWidgets[attr].blockSignals(False)

        if attr not in self._relativeValues \
                or oldUserValue != newUserValue:
            self._relativeValues[attr] = newRelativeVal

    def updateRelativeWidgetMaximum(self, attr):
        maxRes = int(self.core.resolutions[0].split('x')[0])
        newMaximumValue = self.width * (
            self._relativeMaximums[attr] /
            maxRes
        )
        self._trackedWidgets[attr].setMaximum(int(newMaximumValue))


class ComponentError(RuntimeError):
    '''Gives the MainWindow a traceback to display, and cancels the export.'''

    prevErrors = []
    lastTime = time.time()

    def __init__(self, caller, name, msg=None):
        if msg is None and sys.exc_info()[0] is not None:
            msg = str(sys.exc_info()[1])
        else:
            msg = 'Unknown error.'
        print("##### ComponentError by %s's %s: %s" % (
            caller.name, name, msg))

        # Don't create multiple windows for quickly repeated messages
        if len(ComponentError.prevErrors) > 1:
            ComponentError.prevErrors.pop()
        ComponentError.prevErrors.insert(0, name)
        curTime = time.time()
        if name in ComponentError.prevErrors[1:] \
                and curTime - ComponentError.lastTime < 1.0:
            return
        ComponentError.lastTime = time.time()

        from toolkit import formatTraceback
        if sys.exc_info()[0] is not None:
            string = (
                "%s component (#%s): %s encountered %s %s: %s" % (
                    caller.__class__.name,
                    str(caller.compPos),
                    name,
                    'an' if any([
                        sys.exc_info()[0].__name__.startswith(vowel)
                        for vowel in ('A', 'I', 'U', 'O', 'E')
                    ]) else 'a',
                    sys.exc_info()[0].__name__,
                    str(sys.exc_info()[1])
                )
            )
            detail = formatTraceback(sys.exc_info()[2])
        else:
            string = name
            detail = "Attributes:\n%s" % (
                "\n".join(
                    [m for m in dir(caller) if not m.startswith('_')]
                )
            )

        super().__init__(string)
        caller.lockError(string)
        caller._error.emit(string, detail)
