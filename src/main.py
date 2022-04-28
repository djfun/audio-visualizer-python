from PyQt5 import uic, QtWidgets
import sys
import os
import logging
import re
import string

from .__init__ import wd


log = logging.getLogger('AVP.Main')


def main():
    # Determine primary mode
    proj = None
    mode = 'GUI'
    if len(sys.argv) > 2:
        mode = 'commandline'
    elif len(sys.argv) == 2:
        if sys.argv[1].startswith('-'):
            mode = 'commandline'
        else:
            # remove unsafe punctuation characters such as \/?*&^%$#
            sys.argv[1] = re.sub(f'[{re.escape(string.punctuation)}]', '', sys.argv[1])
            # opening a project file with gui
            proj = sys.argv[1]

    # Create Qt Application
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("audio-visualizer")
    # Launch program
    if mode == 'commandline':
        from .command import Command

        main = Command()
        mode = main.parseArgs()
        log.debug("Finished creating command object")

    # Both branches here may occur in one execution:
    # Commandline parsing could change mode back to GUI
    if mode == 'GUI':
        from .gui.mainwindow import MainWindow

        window = uic.loadUi(os.path.join(wd, "gui", "mainwindow.ui"))
        desc = QtWidgets.QDesktopWidget()
        dpi = desc.physicalDpiX()
        log.info("Detected screen DPI: %s", dpi)
        
        window.resize(
            int(window.width() *
            (dpi / 96)),
            int(window.height() *
            (dpi / 96))
        )

        main = MainWindow(window, proj)
        log.debug("Finished creating main window")
        window.raise_()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
