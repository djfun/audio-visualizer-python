from PyQt5 import uic, QtWidgets
import sys
import os


def main():
    if getattr(sys, 'frozen', False):
        # frozen
        wd = os.path.dirname(sys.executable)
    else:
        # unfrozen
        wd = os.path.dirname(os.path.realpath(__file__))

    # make local imports work everywhere
    sys.path.insert(0, wd)

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

    print('Starting Audio Visualizer in %s mode' % mode)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("audio-visualizer")
    # app.setOrganizationName("audio-visualizer")

    if mode == 'commandline':
        from command import Command

        main = Command()

    elif mode == 'GUI':
        from mainwindow import MainWindow
        import atexit
        import signal

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
        window.raise_()

        signal.signal(signal.SIGINT, main.cleanUp)
        atexit.register(main.cleanUp)

    # applicable to both modes
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
