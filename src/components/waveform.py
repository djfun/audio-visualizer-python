from PIL import Image
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QColor
import os
import math
import subprocess

from component import Component
from toolkit.frame import BlankFrame, scale
from toolkit import checkOutput, rgbFromString, pickColor
from toolkit.ffmpeg import openPipe, closePipe, getAudioDuration, FfmpegVideo


class Component(Component):
    name = 'Waveform'
    version = '1.0.0'

    def widget(self, *args):
        self.color = (255, 255, 255)
        super().widget(*args)

        self.page.lineEdit_color.setText('%s,%s,%s' % self.color)
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*self.color).name()
        self.page.pushButton_color.setStyleSheet(btnStyle)
        self.page.pushButton_color.clicked.connect(lambda: self.pickColor())
        self.page.spinBox_scale.valueChanged.connect(self.updateChunksize)

        if hasattr(self.parent, 'window'):
            self.parent.window.lineEdit_audioFile.textChanged.connect(
                self.update
            )

        self.trackWidgets(
            {
                'mode': self.page.comboBox_mode,
                'amplitude': self.page.comboBox_amplitude,
                'x': self.page.spinBox_x,
                'y': self.page.spinBox_y,
                'mirror': self.page.checkBox_mirror,
                'scale': self.page.spinBox_scale,
                'opacity': self.page.spinBox_opacity,
                'compress': self.page.checkBox_compress,
                'mono': self.page.checkBox_mono,
            }
        )

    def update(self):
        self.color = rgbFromString(self.page.lineEdit_color.text())
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*self.color).name()
        self.page.pushButton_color.setStyleSheet(btnStyle)
        super().update()

    def loadPreset(self, pr, *args):
        super().loadPreset(pr, *args)

        self.page.lineEdit_color.setText('%s,%s,%s' % pr['color'])
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*pr['color']).name()
        self.page.pushButton_color.setStyleSheet(btnStyle)

    def savePreset(self):
        saveValueStore = super().savePreset()
        saveValueStore['color'] = self.color
        return saveValueStore

    def pickColor(self):
        RGBstring, btnStyle = pickColor()
        if not RGBstring:
            return
        self.page.lineEdit_color.setText(RGBstring)
        self.page.pushButton_color.setStyleSheet(btnStyle)

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

        return [
            '-filter_complex',
            '%s%s%s'
            'showwaves=r=30:s=%sx%s:mode=%s:colors=%s@%s:scale=%s%s%s [v1]; '
            '[v1] scale=%s:%s%s,setpts=2.0*PTS [v]' % (
                'aevalsrc=sin(1*2*PI*t)*sin(880*2*PI*t),'
                if preview and genericPreview else '[0:a] ',
                'compand=.3|.3:1|1:-90/-60|-60/-40|-40/-30|-20/-20:6:0:-90:0.2'
                ',' if self.compress and not preview else (
                    'compand=gain=5,' if self.compress else ''
                ),
                'aformat=channel_layouts=mono,' if self.mono else '',
                self.settings.value("outputWidth"),
                self.settings.value("outputHeight"),
                str(self.page.comboBox_mode.currentText()).lower(),
                hexcolor, opacity, amplitude,
                ', drawbox=x=(iw-w)/2:y=(ih-h)/2:w=iw:h=4:color=%s@%s' % (
                    hexcolor, opacity
                ) if self.mode < 2 else '',
                ', hflip' if self.mirror else'',
                w, h,
                ', trim=duration=%s' % "{0:.3f}".format(startPt + 1)
                if preview else '',
            ),
            '-map', '[v]',
        ]

    def updateChunksize(self):
        width, height = scale(self.scale, self.width, self.height, int)
        self.chunkSize = 4 * width * height

    def finalizeFrame(self, imageData):
        image = Image.frombytes(
            'RGBA',
            scale(self.scale, self.width, self.height, int),
            imageData
        )
        if self.scale != 100 \
                or self.x != 0 or self.y != 0:
            frame = BlankFrame(self.width, self.height)
            frame.paste(image, box=(self.x, self.y))
        else:
            frame = image
        return frame
