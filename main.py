from PyQt4 import QtGui, uic
import sys
import os

import core
import preview_thread
import video_thread


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
        #print(parm, self.settings.value(parm))
        if self.settings.value(parm) is None:
            self.settings.setValue(parm, value)

if __name__ == "__main__":
    mode = 'gui'
    if len(sys.argv) > 2:
        mode = 'cmd'

    elif len(sys.argv) == 2:
        if sys.argv[1].startswith('-'):
            mode = 'cmd'
        else:
            # opening a project file with gui
            proj = sys.argv[1]
    else:
        # normal gui launch
        proj = None

    app = QtGui.QApplication(sys.argv)
    app.setApplicationName("audio-visualizer")
    app.setOrganizationName("audio-visualizer")

    if mode == 'cmd':
        from command import *

        main = Command()

    elif mode == 'gui':
        from mainwindow import *
        import atexit
        import signal

        window = uic.loadUi(os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "mainwindow.ui"))
        # window.adjustSize()
        desc = QtGui.QDesktopWidget()
        dpi = desc.physicalDpiX()

        topMargin = 0 if (dpi == 96) else int(10 * (dpi / 96))
        window.resize(window.width() * (dpi / 96), window.height() * (dpi / 96))
        # window.verticalLayout_2.setContentsMargins(0, topMargin, 0, 0)

        signal.signal(signal.SIGINT, main.cleanUp)
        atexit.register(main.cleanUp)

        main = MainWindow(window, proj)

    # applicable to both modes
    sys.exit(app.exec_())
