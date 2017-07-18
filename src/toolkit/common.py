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


def hideCmdWin(func):
    ''' Stops CMD window from appearing on Windows.
        Adapted from here: http://code.activestate.com/recipes/409002/
    '''
    def decorator(commandList, **kwargs):
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs['startupinfo'] = startupinfo
        return func(commandList, **kwargs)
    return decorator


@hideCmdWin
def checkOutput(commandList, **kwargs):
    return subprocess.check_output(commandList, **kwargs)


@hideCmdWin
def openPipe(commandList, **kwargs):
    return subprocess.Popen(commandList, **kwargs)


def disableWhenEncoding(func):
    ''' Blocks calls to a function while the video is being exported
        in MainWindow.
    '''
    def decorator(*args, **kwargs):
        if args[0].encoding:
            return
        else:
            return func(*args, **kwargs)
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


def LoadDefaultSettings(self):
    ''' Runs once at each program start-up. Fills in default settings
        for any settings not found in settings.ini
    '''
    self.resolutions = [
        '1920x1080',
        '1280x720',
        '854x480'
    ]

    default = {
        "outputWidth": 1280,
        "outputHeight": 720,
        "outputFrameRate": 30,
        "outputAudioCodec": "AAC",
        "outputAudioBitrate": "192",
        "outputVideoCodec": "H264",
        "outputVideoBitrate": "2500",
        "outputVideoFormat": "yuv420p",
        "outputPreset": "medium",
        "outputFormat": "mp4",
        "outputContainer": "MP4",
        "projectDir": os.path.join(self.dataDir, 'projects'),
    }

    for parm, value in default.items():
        if self.settings.value(parm) is None:
            self.settings.setValue(parm, value)
