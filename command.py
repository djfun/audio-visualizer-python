# FIXME: commandline functionality broken until we decide how to implement it
'''
class Command(QtCore.QObject):

  videoTask = QtCore.pyqtSignal(str, str, str, list)

  def __init__(self):
    QtCore.QObject.__init__(self)
    self.modules = []
    self.selectedComponents = []

    import argparse
    self.parser = argparse.ArgumentParser(
        description='Create a visualization for an audio file')
    self.parser.add_argument(
        '-i', '--input', dest='input', help='input audio file', required=True)
    self.parser.add_argument(
        '-o', '--output', dest='output',
        help='output video file', required=True)
    self.parser.add_argument(
        '-b', '--background', dest='bgimage',
        help='background image file', required=True)
    self.parser.add_argument(
        '-t', '--text', dest='text', help='title text', required=True)
    self.parser.add_argument(
        '-f', '--font', dest='font', help='title font', required=False)
    self.parser.add_argument(
        '-s', '--fontsize', dest='fontsize',
        help='title font size', required=False)
    self.parser.add_argument(
        '-c', '--textcolor', dest='textcolor',
        help='title text color in r,g,b format', required=False)
    self.parser.add_argument(
        '-C', '--viscolor', dest='viscolor',
        help='visualization color in r,g,b format', required=False)
    self.parser.add_argument(
        '-x', '--xposition', dest='xposition',
        help='x position', required=False)
    self.parser.add_argument(
        '-y', '--yposition', dest='yposition',
        help='y position', required=False)
    self.parser.add_argument(
        '-a', '--alignment', dest='alignment',
        help='title alignment', required=False,
        type=int, choices=[0, 1, 2])
    self.args = self.parser.parse_args()

    self.settings = QSettings('settings.ini', QSettings.IniFormat)
    LoadDefaultSettings(self)

    # load colours as tuples from comma-separated strings
    self.textColor = core.Core.RGBFromString(
        self.settings.value("textColor", '255, 255, 255'))
    self.visColor = core.Core.RGBFromString(
        self.settings.value("visColor", '255, 255, 255'))
    if self.args.textcolor:
      self.textColor = core.Core.RGBFromString(self.args.textcolor)
    if self.args.viscolor:
      self.visColor = core.Core.RGBFromString(self.args.viscolor)

    # font settings
    if self.args.font:
      self.font = QFont(self.args.font)
    else:
      self.font = QFont(self.settings.value("titleFont", QFont()))

    if self.args.fontsize:
      self.fontsize = int(self.args.fontsize)
    else:
      self.fontsize = int(self.settings.value("fontSize", 35))
    if self.args.alignment:
      self.alignment = int(self.args.alignment)
    else:
      self.alignment = int(self.settings.value("alignment", 0))

    if self.args.xposition:
      self.textX = int(self.args.xposition)
    else:
      self.textX = int(self.settings.value("xPosition", 70))

    if self.args.yposition:
      self.textY = int(self.args.yposition)
    else:
      self.textY = int(self.settings.value("yPosition", 375))

    ffmpeg_cmd = self.settings.value("ffmpeg_cmd", expanduser("~"))

    self.videoThread = QtCore.QThread(self)
    self.videoWorker = video_thread.Worker(self)

    self.videoWorker.moveToThread(self.videoThread)
    self.videoWorker.videoCreated.connect(self.videoCreated)

    self.videoThread.start()
    self.videoTask.emit(self.args.bgimage,
      self.args.text,
      self.font,
      self.fontsize,
      self.alignment,
      self.textX,
      self.textY,
      self.textColor,
      self.visColor,
      self.args.input,
      self.args.output,
      self.selectedComponents)

  def videoCreated(self):
    self.videoThread.quit()
    self.videoThread.wait()
    self.cleanUp()

  def cleanUp(self):
    self.settings.setValue("titleFont", self.font.toString())
    self.settings.setValue("alignment", str(self.alignment))
    self.settings.setValue("fontSize", str(self.fontsize))
    self.settings.setValue("xPosition", str(self.textX))
    self.settings.setValue("yPosition", str(self.textY))
    self.settings.setValue("visColor", '%s,%s,%s' % self.visColor)
    self.settings.setValue("textColor", '%s,%s,%s' % self.textColor)
    sys.exit(0)
'''
