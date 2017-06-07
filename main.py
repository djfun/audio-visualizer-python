from importlib import import_module
from collections import OrderedDict
from PyQt4 import QtGui, uic
from PyQt4.QtCore import Qt
import sys
import io
import os
import atexit
import signal

import core
import preview_thread
import video_thread
from mainwindow import *


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
        "outputAudioBitrate": "192k",
        "outputVideoCodec": "H264",
        "outputVideoFormat": "yuv420p",
        "outputPreset": "medium",
        "outputFormat": "mp4",
        "outputContainer": "MP4",
        "projectDir": os.path.join(self.dataDir, 'projects'),
    }

    for parm, value in default.items():
        if self.settings.value(parm) is None:
            self.settings.setValue(parm, value)

if __name__ == "__main__":
    ''' FIXME commandline functionality broken until we decide how to implement
    if len(sys.argv) > 1:
    # command line mode
    app = QtGui.QApplication(sys.argv, False)
    command = Command()
    signal.signal(signal.SIGINT, command.cleanUp)
    sys.exit(app.exec_())
    else:
    '''
    app = QtGui.QApplication(sys.argv)
    app.setApplicationName("audio-visualizer")
    app.setOrganizationName("audio-visualizer")
    window = uic.loadUi(os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "mainwindow.ui"))
    # window.adjustSize()
    desc = QtGui.QDesktopWidget()
    dpi = desc.physicalDpiX()

    topMargin = 0 if (dpi == 96) else int(10 * (dpi / 96))
    window.resize(window.width() * (dpi / 96), window.height() * (dpi / 96))
    # window.verticalLayout_2.setContentsMargins(0, topMargin, 0, 0)

    main = MainWindow(window)

    signal.signal(signal.SIGINT, main.cleanUp)
    atexit.register(main.cleanUp)

    sys.exit(app.exec_())
