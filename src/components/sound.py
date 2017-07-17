from PyQt5 import QtGui, QtCore, QtWidgets
import os

from component import Component
from frame import BlankFrame


class Component(Component):
    '''Sound'''

    modified = QtCore.pyqtSignal(int, dict)

    def widget(self, parent):
        self.parent = parent
        self.settings = parent.settings
        page = self.loadUi('sound.ui')

        page.lineEdit_sound.textChanged.connect(self.update)
        page.pushButton_sound.clicked.connect(self.pickSound)
        page.checkBox_chorus.stateChanged.connect(self.update)
        page.spinBox_delay.valueChanged.connect(self.update)
        page.spinBox_volume.valueChanged.connect(self.update)

        self.page = page
        return page

    def update(self):
        self.sound = self.page.lineEdit_sound.text()
        self.delay = self.page.spinBox_delay.value()
        self.volume = self.page.spinBox_volume.value()
        self.chorus = self.page.checkBox_chorus.isChecked()
        super().update()

    def previewRender(self, previewWorker):
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        return BlankFrame(width, height)

    def preFrameRender(self, **kwargs):
        pass

    def properties(self):
        props = ['static', 'audio']
        if not os.path.exists(self.sound):
            props.append('error')
        return props

    def error(self):
        if not self.sound:
            return "No audio file selected."
        if not os.path.exists(self.sound):
            return "The audio file selected no longer exists!"

    def audio(self):
        params = {}
        if self.delay != 0.0:
            params['adelay'] = '=%s' % str(int(self.delay * 1000.00))
        if self.chorus:
            params['chorus'] = \
                '=0.5:0.9:50|60|40:0.4|0.32|0.3:0.25|0.4|0.3:2|2.3|1.3'
        if self.volume != 1.0:
            params['volume'] = '=%s:replaygain_noclip=0' % str(self.volume)

        return (self.sound, params)

    def pickSound(self):
        sndDir = self.settings.value("componentDir", os.path.expanduser("~"))
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.page, "Choose Sound", sndDir,
            "Audio Files (%s)" % " ".join(self.core.audioFormats))
        if filename:
            self.settings.setValue("componentDir", os.path.dirname(filename))
            self.page.lineEdit_sound.setText(filename)
            self.update()

    def frameRender(self, layerNo, frameNo):
        width = int(self.settings.value('outputWidth'))
        height = int(self.settings.value('outputHeight'))
        return BlankFrame(width, height)

    def loadPreset(self, pr, presetName=None):
        super().loadPreset(pr, presetName)
        self.page.lineEdit_sound.setText(pr['sound'])
        self.page.checkBox_chorus.setChecked(pr['chorus'])
        self.page.spinBox_delay.setValue(pr['delay'])
        self.page.spinBox_volume.setValue(pr['volume'])

    def savePreset(self):
        return {
            'sound': self.sound,
            'chorus': self.chorus,
            'delay': self.delay,
            'volume': self.volume,
        }

    def commandHelp(self):
        print('Path to audio file:\n    path=/filepath/to/sound.ogg')

    def command(self, arg):
        if not arg.startswith('preset=') and '=' in arg:
            key, arg = arg.split('=', 1)
            if key == 'path':
                if '*%s' % os.path.splitext(arg)[1] \
                        not in self.core.audioFormats:
                    print("Not a supported audio format")
                    quit(1)
                self.page.lineEdit_sound.setText(arg)
                return

        super().command(arg)
