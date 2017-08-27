from PyQt5 import uic, QtWidgets
import sys
import os
import logging

from __init__ import wd


log = logging.getLogger('AVP.Main')


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("audio-visualizer")

    # Determine mode
    mode = 'GUI'
    if len(sys.argv) > 2:
        mode = 'commandline'
    elif len(sys.argv) == 2:
        if sys.argv[1].startswith('-'):
            mode = 'commandline'
        else:
            # opening a project file with gui
            proj = sys.argv[1]
    else:
        # normal gui launch
        proj = None

    # Launch program
    if mode == 'commandline':
        from command import Command

        main = Command()
        log.debug("Finished creating command object")

    elif mode == 'GUI':
        from gui.mainwindow import MainWindow

        window = uic.loadUi(os.path.join(wd, "gui", "mainwindow.ui"))
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
        log.debug("Finished creating main window")
        window.raise_()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
