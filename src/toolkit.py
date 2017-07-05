'''
    Common functions
'''
import string
import os
import sys
import subprocess
from collections import OrderedDict


def badName(name):
    '''Returns whether a name contains non-alphanumeric chars'''
    return any([letter in string.punctuation for letter in name])


def presetToString(dictionary):
    '''Alphabetizes a dict into OrderedDict & returns string repr'''
    return repr(
        OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))
    )


def presetFromString(string):
    '''Turns a string repr of OrderedDict into a regular dict'''
    return dict(eval(string))


def appendUppercase(lst):
    for form, i in zip(lst, range(len(lst))):
        lst.append(form.upper())
    return lst


def checkOutput(commandList, **kwargs):
    _subprocess(subprocess.check_output)


def openPipe(commandList, **kwargs):
    _subprocess(subprocess.Popen)


def _subprocess(func, commandList, **kwargs):
    if sys.platform == 'win32':
        # Stop CMD window from appearing on Windows
        # http://code.activestate.com/recipes/409002/
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs['startupinfo'] = startupinfo
    return func(commandList, shell=False, **kwargs)


def disableWhenEncoding(func):
    def decorator(*args, **kwargs):
        if args[0].encoding:
            return
        else:
            return func(*args, **kwargs)
    return decorator


def LoadDefaultSettings(self):
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
