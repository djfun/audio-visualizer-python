'''
    Common functions
'''
from PyQt5 import QtWidgets
import string
import os
import sys
import subprocess
from collections import OrderedDict


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


def pickColor():
    '''
        Use color picker to get color input from the user,
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
