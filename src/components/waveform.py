from PIL import Image
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QColor
import os
import math
import subprocess

from component import Component
from toolkit.frame import BlankFrame, scale
from toolkit import checkOutput
from toolkit.ffmpeg import (
    openPipe, closePipe, getAudioDuration, FfmpegVideo, exampleSound
)


class Component(Component):
    name = 'Waveform'
    version = '1.0.0'

    def widget(self, *args):
        super().widget(*args)
        self._image = BlankFrame(self.width, self.height)

        self.page.lineEdit_color.setText('255,255,255')

        if hasattr(self.parent, 'window'):
            self.parent.window.lineEdit_audioFile.textChanged.connect(
                self.update
            )

        self.trackWidgets({
            'color': self.page.lineEdit_color,
            'mode': self.page.comboBox_mode,
            'amplitude': self.page.comboBox_amplitude,
            'x': self.page.spinBox_x,
            'y': self.page.spinBox_y,
            'mirror': self.page.checkBox_mirror,
            'scale': self.page.spinBox_scale,
            'opacity': self.page.spinBox_opacity,
            'compress': self.page.checkBox_compress,
            'mono': self.page.checkBox_mono,
        }, colorWidgets={
            'color': self.page.pushButton_color,
        }, relativeWidgets=[
            'x', 'y',
        ])

    def previewRender(self):
        self.updateChunksize()
        frame = self.getPreviewFrame(self.width, self.height)
        if not frame:
            return BlankFrame(self.width, self.height)
        else:
            return frame

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        self.updateChunksize()
        w, h = scale(self.scale, self.width, self.height, str)
        self.video = FfmpegVideo(
            inputPath=self.audioFile,
            filter_=self.makeFfmpegFilter(),
            width=w, height=h,
            chunkSize=self.chunkSize,
            frameRate=int(self.settings.value("outputFrameRate")),
            parent=self.parent, component=self, debug=True,
        )

    def frameRender(self, frameNo):
        if FfmpegVideo.threadError is not None:
            raise FfmpegVideo.threadError
        return self.finalizeFrame(self.video.frame(frameNo))

    def postFrameRender(self):
        closePipe(self.video.pipe)

    def getPreviewFrame(self, width, height):
        genericPreview = self.settings.value("pref_genericPreview")
        startPt = 0
        if not genericPreview:
            inputFile = self.parent.window.lineEdit_audioFile.text()
            if not inputFile or not os.path.exists(inputFile):
                return
            duration = getAudioDuration(inputFile)
            if not duration:
                return
            startPt = duration / 3
            if startPt + 3 > duration:
                startPt += startPt - 3

        command = [
            self.core.FFMPEG_BIN,
            '-thread_queue_size', '512',
            '-r', self.settings.value("outputFrameRate"),
            '-ss', "{0:.3f}".format(startPt),
            '-i',
            os.path.join(self.core.wd, 'background.png')
            if genericPreview else inputFile,
            '-f', 'image2pipe',
            '-pix_fmt', 'rgba',
        ]
        command.extend(self.makeFfmpegFilter(preview=True, startPt=startPt))
        command.extend([
            '-an',
            '-s:v', '%sx%s' % scale(self.scale, self.width, self.height, str),
            '-codec:v', 'rawvideo', '-',
            '-frames:v', '1',
        ])
        pipe = openPipe(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=10**8
        )
        byteFrame = pipe.stdout.read(self.chunkSize)
        closePipe(pipe)

        frame = self.finalizeFrame(byteFrame)
        return frame

    def makeFfmpegFilter(self, preview=False, startPt=0):
        w, h = scale(self.scale, self.width, self.height, str)
        if self.amplitude == 0:
            amplitude = 'lin'
        elif self.amplitude == 1:
            amplitude = 'log'
        elif self.amplitude == 2:
            amplitude = 'sqrt'
        elif self.amplitude == 3:
            amplitude = 'cbrt'
        hexcolor = QColor(*self.color).name()
        opacity = "{0:.1f}".format(self.opacity / 100)
        genericPreview = self.settings.value("pref_genericPreview")
        if self.mode < 3:
            filter_ = 'showwaves=r=%s:s=%sx%s:mode=%s:colors=%s@%s:scale=%s' % (
                self.settings.value("outputFrameRate"),
                self.settings.value("outputWidth"),
                self.settings.value("outputHeight"),
                self.page.comboBox_mode.currentText().lower()
                if self.mode != 3 else 'p2p',
                hexcolor, opacity, amplitude,
            )
        elif self.mode > 2:
            filter_ = (
                'showfreqs=s=%sx%s:mode=%s:colors=%s@%s'
                ':ascale=%s:fscale=%s' % (
                    self.settings.value("outputWidth"),
                    self.settings.value("outputHeight"),
                    'line' if self.mode == 4 else 'bar',
                    hexcolor, opacity, amplitude,
                    'log' if self.mono else 'lin'
                )
            )

        return [
            '-filter_complex',
            '%s%s%s'
            '%s%s%s [v1]; '
            '[v1] scale=%s:%s%s [v]' % (
                exampleSound() if preview and genericPreview else '[0:a] ',
                'compand=gain=4,' if self.compress else '',
                'aformat=channel_layouts=mono,'
                if self.mono and self.mode < 3 else '',
                filter_,
                ', drawbox=x=(iw-w)/2:y=(ih-h)/2:w=iw:h=4:color=%s@%s' % (
                    hexcolor, opacity
                ) if self.mode < 2 else '',
                ', hflip' if self.mirror else'',
                w, h,
                ', trim=duration=%s' % "{0:.3f}".format(startPt + 3)
                if preview else '',
            ),
            '-map', '[v]',
        ]

    def updateChunksize(self):
        width, height = scale(self.scale, self.width, self.height, int)
        self.chunkSize = 4 * width * height

    def finalizeFrame(self, imageData):
        try:
            image = Image.frombytes(
                'RGBA',
                scale(self.scale, self.width, self.height, int),
                imageData
            )
            self._image = image
        except ValueError:
            image = self._image
        if self.scale != 100 \
                or self.x != 0 or self.y != 0:
            frame = BlankFrame(self.width, self.height)
            frame.paste(image, box=(self.x, self.y))
        else:
            frame = image
        return frame
