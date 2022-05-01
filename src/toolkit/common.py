'''
    Common functions
'''
from PyQt5 import QtWidgets
import string
import os
import sys
import subprocess
import logging
from copy import copy
from collections import OrderedDict


log = logging.getLogger('AVP.Toolkit.Common')


class blockSignals:
    '''
        Context manager to temporarily block list of QtWidgets from updating,
        and guarantee restoring the previous state afterwards.
    '''
    def __init__(self, widgets):
        if type(widgets) is dict:
            self.widgets = concatDictVals(widgets)
        else:
            self.widgets = (
                widgets if hasattr(widgets, '__iter__')
                else [widgets]
            )

    def __enter__(self):
        log.verbose(
            'Blocking signals for %s',
            ", ".join([
                str(w.__class__.__name__) for w in self.widgets
            ])
        )
        self.oldStates = [w.signalsBlocked() for w in self.widgets]
        for w in self.widgets:
            w.blockSignals(True)

    def __exit__(self, *args):
        log.verbose(
            'Resetting blockSignals to %s', str(bool(sum(self.oldStates))))
        for w, state in zip(self.widgets, self.oldStates):
            w.blockSignals(state)


def concatDictVals(d):
    '''Concatenates all values in given dict into one list.'''
    key, value = d.popitem()
    d[key] = value
    final = copy(value)
    if type(final) is not list:
        final = [final]
        final.extend([val for val in d.values()])
    else:
        value.extend([item for val in d.values() for item in val])
    return final


def badName(name):
    '''Returns whether a name contains non-alphanumeric chars'''
    return any([letter in string.punctuation for letter in name])


def alphabetizeDict(dictionary):
    '''Alphabetizes a dict into OrderedDict '''
    return OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))


def presetToString(dictionary):
    '''Returns string repr of a preset'''
    return repr(alphabetizeDict(dictionary))


def presetFromString(string):
    '''Turns a string repr of OrderedDict into a regular dict'''
    return dict(eval(string))


def appendUppercase(lst):
    for form, i in zip(lst, range(len(lst))):
        lst.append(form.upper())
    return lst


def pipeWrapper(func):
    '''A decorator to insert proper kwargs into Popen objects.'''
    def pipeWrapper(commandList, **kwargs):
        if sys.platform == 'win32':
            # Stop CMD window from appearing on Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs['startupinfo'] = startupinfo

        if 'bufsize' not in kwargs:
            kwargs['bufsize'] = 10**8
        if 'stdin' not in kwargs:
            kwargs['stdin'] = subprocess.DEVNULL
        return func(commandList, **kwargs)
    return pipeWrapper


@pipeWrapper
def checkOutput(commandList, **kwargs):
    return subprocess.check_output(commandList, **kwargs)


def disableWhenEncoding(func):
    def decorator(self, *args, **kwargs):
        if self.encoding:
            return
        else:
            return func(self, *args, **kwargs)
    return decorator


def disableWhenOpeningProject(func):
    def decorator(self, *args, **kwargs):
        if self.core.openingProject:
            return
        else:
            return func(self, *args, **kwargs)
    return decorator


def rgbFromString(string):
    '''Turns an RGB string like "255, 255, 255" into a tuple'''
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


def formatTraceback(tb=None):
    import traceback
    if tb is None:
        import sys
        tb = sys.exc_info()[2]
    return 'Traceback:\n%s' % "\n".join(traceback.format_tb(tb))


def connectWidget(widget, func):
    if type(widget) == QtWidgets.QLineEdit:
        widget.textChanged.connect(func)
    elif type(widget) == QtWidgets.QSpinBox \
            or type(widget) == QtWidgets.QDoubleSpinBox:
        widget.valueChanged.connect(func)
    elif type(widget) == QtWidgets.QCheckBox:
        widget.stateChanged.connect(func)
    elif type(widget) == QtWidgets.QComboBox:
        widget.currentIndexChanged.connect(func)
    else:
        log.warning('Failed to connect %s ', str(widget.__class__.__name__))
        return False
    return True


def setWidgetValue(widget, val):
    '''Generic setValue method for use with any typical QtWidget'''
    log.verbose('Setting %s to %s' % (str(widget.__class__.__name__), val))
    if type(widget) == QtWidgets.QLineEdit:
        widget.setText(val)
    elif type(widget) == QtWidgets.QSpinBox \
            or type(widget) == QtWidgets.QDoubleSpinBox:
        widget.setValue(val)
    elif type(widget) == QtWidgets.QCheckBox:
        widget.setChecked(val)
    elif type(widget) == QtWidgets.QComboBox:
        widget.setCurrentIndex(val)
    else:
        log.warning('Failed to set %s ', str(widget.__class__.__name__))
        return False
    return True


def getWidgetValue(widget):
    if type(widget) == QtWidgets.QLineEdit:
        return widget.text()
    elif type(widget) == QtWidgets.QSpinBox \
            or type(widget) == QtWidgets.QDoubleSpinBox:
        return widget.value()
    elif type(widget) == QtWidgets.QCheckBox:
        return widget.isChecked()
    elif type(widget) == QtWidgets.QComboBox:
        return widget.currentIndex()
