from PyQt6 import QtGui, QtCore, QtWidgets
import os

from ..libcomponent import BaseComponent
from ..toolkit.frame import BlankFrame


class Component(BaseComponent):
    name = "Sound"
    version = "1.0.0"

    def widget(self, *args):
        super().widget(*args)
        self.page.pushButton_sound.clicked.connect(self.pickSound)
        self.trackWidgets(
            {
                "sound": self.page.lineEdit_sound,
                "chorus": self.page.checkBox_chorus,
                "delay": self.page.spinBox_delay,
                "volume": self.page.spinBox_volume,
            },
            commandArgs={
                "sound": None,
            },
        )

    def properties(self):
        props = ["static", "audio"]
        if not os.path.exists(self.sound):
            props.append("error")
        return props

    def error(self):
        if not self.sound:
            return "No audio file selected."
        if not os.path.exists(self.sound):
            return "The audio file selected no longer exists!"

    def audio(self):
        params = {}
        if self.delay != 0.0:
            params["adelay"] = "=%s" % str(int(self.delay * 1000.00))
        if self.chorus:
            params["chorus"] = "=0.5:0.9:50|60|40:0.4|0.32|0.3:0.25|0.4|0.3:2|2.3|1.3"
        if self.volume != 1.0:
            params["volume"] = "=%s:replaygain_noclip=0" % str(self.volume)

        return (self.sound, params)

    def pickSound(self):
        sndDir = self.settings.value("componentDir", os.path.expanduser("~"))
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.page,
            "Choose Sound",
            sndDir,
            "Audio Files (%s)" % " ".join(self.core.audioFormats),
        )
        if filename:
            self.settings.setValue("componentDir", os.path.dirname(filename))
            self.mergeUndo = False
            self.page.lineEdit_sound.setText(filename)
            self.mergeUndo = True

    def commandHelp(self):
        print("Path to audio file:\n    path=/filepath/to/sound.ogg")

    def command(self, arg):
        if "=" in arg:
            key, arg = arg.split("=", 1)
            if key == "path":
                if "*%s" % os.path.splitext(arg)[1] not in self.core.audioFormats:
                    print("Not a supported audio format")
                    quit(1)
                self.page.lineEdit_sound.setText(arg)
                return

        super().command(arg)
