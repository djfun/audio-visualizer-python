from PyQt5 import QtGui, uic, QtWidgets
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

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("audio-visualizer")
    # app.setOrganizationName("audio-visualizer")

    if mode == 'cmd':
        from command import *

        main = Command()

    elif mode == 'gui':
        from mainwindow import *
        import atexit
        import signal

        if getattr(sys, 'frozen', False):
            # frozen
            wd = os.path.dirname(sys.executable)
        else:
            # unfrozen
            wd = os.path.dirname(os.path.realpath(__file__))

        window = uic.loadUi(os.path.join(wd, "mainwindow.ui"))
        # window.adjustSize()
        desc = QtWidgets.QDesktopWidget()
        dpi = desc.physicalDpiX()

        topMargin = 0 if (dpi == 96) else int(10 * (dpi / 96))
        window.resize(
            window.width() *
            (dpi / 96), window.height() *
            (dpi / 96)
        )
        # window.verticalLayout_2.setContentsMargins(0, topMargin, 0, 0)

        main = MainWindow(window, proj)

        signal.signal(signal.SIGINT, main.cleanUp)
        atexit.register(main.cleanUp)

    # applicable to both modes
    sys.exit(app.exec_())
