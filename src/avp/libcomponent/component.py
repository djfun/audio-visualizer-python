"""
Base classes for components to import. Read comments for some documentation
on making a valid component.
"""

from PyQt6 import uic, QtCore, QtWidgets
from PyQt6.QtGui import QColor
import os
import math
import logging
from copy import copy

from .metaclass import ComponentMetaclass
from .actions import ComponentUpdate
from .exceptions import ComponentError
from ..toolkit.frame import BlankFrame

from ..toolkit import (
    getWidgetValue,
    setWidgetValue,
    rgbFromString,
    randomColor,
    blockSignals,
)

log = logging.getLogger("AVP.BaseComponent")


class Component(QtCore.QObject, metaclass=ComponentMetaclass):
    """
    The base class for components to inherit.
    """

    name = "Component"
    # ui = 'name_Of_Non_Default_Ui_File'

    version = "1.0.0"
    # The major version (before the first dot) is used to determine
    # preset compatibility; the rest is ignored so it can be non-numeric.

    modified = QtCore.pyqtSignal(int, dict)
    _error = QtCore.pyqtSignal(str, str)

    def __init__(self, moduleIndex, compPos, core):
        super().__init__()
        self.moduleIndex = moduleIndex
        self.compPos = compPos
        self.core = core

        # STATUS VARIABLES
        self.currentPreset = None
        self._allWidgets = {}
        self._trackedWidgets = {}
        self._presetNames = {}
        self._commandArgs = {}
        self._colorWidgets = {}
        self._colorFuncs = {}
        self._relativeWidgets = {}
        # Pixel values stored as floats
        self._relativeValues = {}
        # Maximum values of spinBoxes at 1080p (Core.resolutions[0])
        self._relativeMaximums = {}

        # LOCKING VARIABLES
        self.openingPreset = False
        self.mergeUndo = True
        self._lockedProperties = None
        self._lockedError = None
        self._lockedSize = None
        # If set to a dict, values are used as basis to update relative widgets
        self.oldAttrs = None
        # Stop lengthy processes in response to this variable
        self.canceled = False

    def __str__(self):
        return self.__class__.name

    def __repr__(self):
        import pprint

        try:
            preset = self.savePreset()
        except Exception as e:
            preset = "%s occurred while saving preset" % str(e)

        return "Component(module %s, pos %s) (%s)\n" "Name: %s v%s\nPreset: %s" % (
            self.moduleIndex,
            self.compPos,
            object.__repr__(self),
            self.__class__.name,
            str(self.__class__.version),
            pprint.pformat(preset),
        )

    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~
    # Render Methods
    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~

    def previewRender(self):
        image = BlankFrame(self.width, self.height)
        return image

    def preFrameRender(self, **kwargs):
        """
        Must call super() when subclassing
        Triggered only before a video is exported (video_thread.py)
            self.audioFile = filepath to the main input audio file
            self.completeAudioArray = a list of audio samples
            self.sampleSize = number of audio samples per video frame
            self.progressBarUpdate = signal to set progress bar number
            self.progressBarSetText = signal to set progress bar text
        Use the latter two signals to update the MainWindow if needed
        for a long initialization procedure (i.e., for a visualizer)
        """
        for key, value in kwargs.items():
            setattr(self, key, value)

    def frameRender(self, frameNo):
        audioArrayIndex = frameNo * self.sampleSize
        image = BlankFrame(self.width, self.height)
        return image

    def postFrameRender(self):
        pass

    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~
    # Properties
    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~

    def properties(self):
        """
        Return a list of properties to signify if your component is
        non-animated ('static'), returns sound ('audio'), or has
        encountered an error in configuration ('error').
        """
        return []

    def error(self):
        """
        Return a string containing an error message, or None for a default.
        Or tuple of two strings for a message with details.
        Alternatively use lockError(msgString) within properties()
        to skip this method entirely.
        """
        return

    def audio(self):
        """
        Return audio to mix into master as a tuple with two elements:
        The first element can be:
            - A string (path to audio file),
            - Or an object that returns audio data through a pipe
        The second element must be a dictionary of ffmpeg filters/options
        to apply to the input stream. See the filter docs for ideas:
        https://ffmpeg.org/ffmpeg-filters.html
        """

    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~
    # Idle Methods
    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~

    def widget(self, parent):
        """
        Call super().widget(*args) to create the component widget
        which also auto-connects any common widgets (e.g., checkBoxes)
        to self.update(). Then in a subclass connect special actions
        (e.g., pushButtons to select a file) and initialize
        """
        self.parent = parent
        self.settings = parent.settings
        log.verbose(
            "Creating UI for %s #%s's widget",
            self.__class__.name,
            self.compPos,
        )
        self.page = self.loadUi(self.__class__.ui)

        # Find all normal widgets which will be connected after subclass method
        self._allWidgets = {
            "lineEdit": self.page.findChildren(QtWidgets.QLineEdit),
            "checkBox": self.page.findChildren(QtWidgets.QCheckBox),
            "spinBox": self.page.findChildren(QtWidgets.QSpinBox),
            "comboBox": self.page.findChildren(QtWidgets.QComboBox),
        }
        self._allWidgets["spinBox"].extend(
            self.page.findChildren(QtWidgets.QDoubleSpinBox)
        )

    def update(self):
        """
        Starting point for a component update. A subclass should override
        this method, and the base class will then magically insert a call
        to either _autoUpdate() or _userUpdate() at the end.
        """

    def loadPreset(self, presetDict, presetName=None):
        """
        Subclasses should take (presetDict, *args) as args.
        Must use super().loadPreset(presetDict, *args) first,
        then update self.page widgets using the preset dict.
        """
        self.currentPreset = (
            presetName if presetName is not None else presetDict["preset"]
        )
        for attr, widget in self._trackedWidgets.items():
            key = attr if attr not in self._presetNames else self._presetNames[attr]
            try:
                val = presetDict[key]
            except KeyError as e:
                log.info(
                    "%s missing value %s. Outdated preset?",
                    self.currentPreset,
                    str(e),
                )
                val = getattr(self, key)

            if attr in self._colorWidgets:
                widget.setText("%s,%s,%s" % val)
                btnStyle = (
                    "QPushButton { background-color : %s; outline: none; }"
                    % QColor(*val).name()
                )
                self._colorWidgets[attr].setStyleSheet(btnStyle)
            elif attr in self._relativeWidgets:
                self._relativeValues[attr] = val
                pixelVal = self.pixelValForAttr(attr, val)
                setWidgetValue(widget, pixelVal)
            else:
                setWidgetValue(widget, val)

    def savePreset(self):
        saveValueStore = {}
        for attr, widget in self._trackedWidgets.items():
            presetAttrName = (
                attr if attr not in self._presetNames else self._presetNames[attr]
            )
            if attr in self._relativeWidgets:
                try:
                    val = self._relativeValues[attr]
                except AttributeError:
                    val = self.floatValForAttr(attr)
            else:
                val = getattr(self, attr)

            saveValueStore[presetAttrName] = val
        return saveValueStore

    def commandHelp(self):
        """Help text as string for this component's commandline arguments"""

    def command(self, arg=""):
        """
        Configure a component using an arg from the commandline. This is
        never called if global args like 'preset=' are found in the arg.
        So simply check for any non-global args in your component and
        call super().command() at the end to get a Help message.
        """
        print(
            self.__class__.name,
            "Usage:\n" "Open a preset for this component:\n" '    "preset=Preset Name"',
        )
        self.commandHelp()
        quit(0)

    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~
    # "Private" Methods
    # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~
    def _preUpdate(self):
        """Happens before subclass update()"""
        for attr in self._relativeWidgets:
            self.updateRelativeWidget(attr)

    def _userUpdate(self):
        """Happens after subclass update() for an undoable update by user."""
        oldWidgetVals = {
            attr: copy(getattr(self, attr)) for attr in self._trackedWidgets
        }
        newWidgetVals = {
            attr: (
                getWidgetValue(widget)
                if attr not in self._colorWidgets
                else rgbFromString(widget.text())
            )
            for attr, widget in self._trackedWidgets.items()
        }
        modifiedWidgets = {
            attr: val
            for attr, val in newWidgetVals.items()
            if val != oldWidgetVals[attr]
        }
        if modifiedWidgets:
            action = ComponentUpdate(self, oldWidgetVals, modifiedWidgets)
            self.parent.undoStack.push(action)

    def _autoUpdate(self):
        """Happens after subclass update() for an internal component update."""
        newWidgetVals = {
            attr: getWidgetValue(widget)
            for attr, widget in self._trackedWidgets.items()
        }
        self.setAttrs(newWidgetVals)
        self._sendUpdateSignal()

    def setAttrs(self, attrDict):
        """
        Sets attrs (linked to trackedWidgets) in this component to
        the values in the attrDict. Mutates certain widget values if needed
        """
        for attr, val in attrDict.items():
            if attr in self._colorWidgets:
                # Color Widgets must have a tuple & have a button to update
                if type(val) is tuple:
                    rgbTuple = val
                else:
                    rgbTuple = rgbFromString(val)
                btnStyle = (
                    "QPushButton { background-color : %s; outline: none; }"
                    % QColor(*rgbTuple).name()
                )
                self._colorWidgets[attr].setStyleSheet(btnStyle)
                setattr(self, attr, rgbTuple)

            else:
                # Normal tracked widget
                setattr(self, attr, val)
            log.verbose("Setting %s self.%s to %s" % (self.__class__.name, attr, val))

    def setWidgetValues(self, attrDict):
        """
        Sets widgets defined by keys in trackedWidgets in this preset to
        the values in the attrDict.
        """
        affectedWidgets = [self._trackedWidgets[attr] for attr in attrDict]
        with blockSignals(affectedWidgets):
            for attr, val in attrDict.items():
                widget = self._trackedWidgets[attr]
                if attr in self._colorWidgets:
                    val = "%s,%s,%s" % val
                setWidgetValue(widget, val)

    def _sendUpdateSignal(self):
        if not self.core.openingProject:
            self.parent.drawPreview()
            saveValueStore = self.savePreset()
            saveValueStore["preset"] = self.currentPreset
            self.modified.emit(self.compPos, saveValueStore)

    def trackWidgets(self, trackDict, **kwargs):
        """
        Name widgets to track in update(), savePreset(), loadPreset(), and
        command(). Requires a dict of attr names as keys, widgets as values

        Optional args:
            'presetNames': preset variable names to replace attr names
            'commandArgs': arg keywords that differ from attr names
            'colorWidgets': identify attr as RGB tuple & update button CSS
            'relativeWidgets': change value proportionally to resolution

        NOTE: Any kwarg key set to None will selectively disable tracking.
        """
        self._trackedWidgets = trackDict
        for kwarg in kwargs:
            try:
                if kwarg in (
                    "presetNames",
                    "commandArgs",
                    "colorWidgets",
                    "relativeWidgets",
                ):
                    setattr(self, "_{}".format(kwarg), kwargs[kwarg])
                else:
                    raise ComponentError(self, "Nonsensical keywords to trackWidgets.")
            except ComponentError:
                continue

            if kwarg == "colorWidgets":

                def makeColorFunc(attr):
                    def pickColor_():
                        self.mergeUndo = False
                        self.pickColor(
                            self._trackedWidgets[attr],
                            self._colorWidgets[attr],
                        )
                        self.mergeUndo = True

                    return pickColor_

                self._colorFuncs = {attr: makeColorFunc(attr) for attr in kwargs[kwarg]}
                for attr, func in self._colorFuncs.items():
                    colorText = self._trackedWidgets[attr].text()
                    if colorText == "":
                        rndColor = randomColor()
                        self._trackedWidgets[attr].setText(str(rndColor)[1:-1])
                    self._colorWidgets[attr].clicked.connect(func)
                    self._colorWidgets[attr].setStyleSheet(
                        "QPushButton {"
                        "background-color : %s; outline: none; }"
                        % QColor(
                            *rgbFromString(colorText) if colorText else rndColor
                        ).name()
                    )

            if kwarg == "relativeWidgets":
                # store maximum values of spinBoxes to be scaled appropriately
                for attr in kwargs[kwarg]:
                    self._relativeMaximums[attr] = self._trackedWidgets[attr].maximum()
                    self.updateRelativeWidgetMaximum(attr)
                    setattr(self, attr, getWidgetValue(self._trackedWidgets[attr]))

        self._preUpdate()
        self._autoUpdate()

    def pickColor(self, textWidget, button):
        """Use color picker to get color input from the user."""
        dialog = QtWidgets.QColorDialog()
        # TODO alpha channel is not actually shown in most color picker widgets?
        dialog.setOption(
            QtWidgets.QColorDialog.ColorDialogOption.ShowAlphaChannel, True
        )
        color = dialog.getColor()
        if color.isValid():
            RGBstring = "%s,%s,%s" % (
                str(color.red()),
                str(color.green()),
                str(color.blue()),
            )
            btnStyle = (
                "QPushButton{background-color: %s; outline: none;}" % color.name()
            )
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
        """Load a Qt Designer ui file to use for this component's widget"""
        return uic.loadUi(os.path.join(self.core.componentsPath, filename))

    @property
    def width(self):
        if self._lockedSize is None:
            return int(self.settings.value("outputWidth"))
        else:
            return self._lockedSize[0]

    @property
    def height(self):
        if self._lockedSize is None:
            return int(self.settings.value("outputHeight"))
        else:
            return self._lockedSize[1]

    def cancel(self):
        """Stop any lengthy process in response to this variable."""
        self.canceled = True

    def reset(self):
        self.canceled = False
        self.unlockProperties()
        self.unlockError()

    def relativeWidgetAxis(func):
        def relativeWidgetAxis(self, attr, *args, **kwargs):
            hasVerticalWords = (
                lambda attr: "height" in attr.lower()
                or "ypos" in attr.lower()
                or attr == "y"
            )
            if "axis" not in kwargs:
                axis = self.width
                if hasVerticalWords(attr):
                    axis = self.height
                kwargs["axis"] = axis
            if "axis" in kwargs and type(kwargs["axis"]) is tuple:
                axis = kwargs["axis"][0]
                if hasVerticalWords(attr):
                    axis = kwargs["axis"][1]
                kwargs["axis"] = axis
            return func(self, attr, *args, **kwargs)

        return relativeWidgetAxis

    @relativeWidgetAxis
    def pixelValForAttr(self, attr, val=None, **kwargs):
        if val is None:
            val = self._relativeValues[attr]
        if val > 50.0:
            log.warning(
                "%s #%s attempted to set %s to dangerously high number %s",
                self.__class__.name,
                self.compPos,
                attr,
                val,
            )
            val = 50.0
        result = math.ceil(kwargs["axis"] * val)
        log.verbose(
            "Converting %s: f%s to px%s using axis %s",
            attr,
            val,
            result,
            kwargs["axis"],
        )
        return result

    @relativeWidgetAxis
    def floatValForAttr(self, attr, val=None, **kwargs):
        if val is None:
            val = self._trackedWidgets[attr].value()
        return val / kwargs["axis"]

    def setRelativeWidget(self, attr, floatVal):
        """Set a relative widget using a float"""
        pixelVal = self.pixelValForAttr(attr, floatVal)
        with blockSignals(self._trackedWidgets[attr]):
            self._trackedWidgets[attr].setValue(pixelVal)
        self.update(auto=True)

    def getOldAttr(self, attr):
        """
        Returns previous state of this attr. Used to determine whether
        a relative widget must be updated. Required because undoing/redoing
        can make determining the 'previous' value tricky.
        """
        if self.oldAttrs is not None:
            return self.oldAttrs[attr]
        else:
            try:
                return getattr(self, attr)
            except AttributeError:
                log.error("Using visible values instead of oldAttrs")
                return self._trackedWidgets[attr].value()

    def updateRelativeWidget(self, attr):
        """Called by _preUpdate() for each relativeWidget before each update"""
        oldUserValue = self.getOldAttr(attr)
        newUserValue = self._trackedWidgets[attr].value()
        newRelativeVal = self.floatValForAttr(attr, newUserValue)

        if attr in self._relativeValues:
            oldRelativeVal = self._relativeValues[attr]
            if oldUserValue == newUserValue and oldRelativeVal != newRelativeVal:
                # Float changed without pixel value changing, which
                # means the pixel value needs to be updated
                # TODO QDoubleSpinBox doesn't work with relativeWidgets because of this
                log.debug(
                    "Updating %s #%s's relative widget: %s",
                    self.__class__.name,
                    self.compPos,
                    attr,
                )
                with blockSignals(self._trackedWidgets[attr]):
                    self.updateRelativeWidgetMaximum(attr)
                    pixelVal = self.pixelValForAttr(attr, oldRelativeVal)
                    self._trackedWidgets[attr].setValue(pixelVal)

        if attr not in self._relativeValues or oldUserValue != newUserValue:
            self._relativeValues[attr] = newRelativeVal

    def updateRelativeWidgetMaximum(self, attr):
        maxRes = int(self.core.resolutions[0].split("x")[0])
        newMaximumValue = self.width * (self._relativeMaximums[attr] / maxRes)
        self._trackedWidgets[attr].setMaximum(int(newMaximumValue))
