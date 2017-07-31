from PIL import Image
from PyQt5 import QtGui, QtCore, QtWidgets
import os
import math
import subprocess
import time

from component import Component
from toolkit.frame import BlankFrame, scale
from toolkit import checkOutput, connectWidget
from toolkit.ffmpeg import (
    openPipe, closePipe, getAudioDuration, FfmpegVideo, exampleSound
)


class Component(Component):
    name = 'Spectrum'
    version = '1.0.0'

    def widget(self, *args):
        self.previewFrame = None
        super().widget(*args)
        self.chunkSize = 4 * self.width * self.height
        self.changedOptions = True

        if hasattr(self.parent, 'window'):
            # update preview when audio file changes (if genericPreview is off)
            self.parent.window.lineEdit_audioFile.textChanged.connect(
                self.update
            )

        self.trackWidgets(
            {
                'filterType': self.page.comboBox_filterType,
                'window': self.page.comboBox_window,
                'mode': self.page.comboBox_mode,
                'amplitude': self.page.comboBox_amplitude0,
                'amplitude1': self.page.comboBox_amplitude1,
                'amplitude2': self.page.comboBox_amplitude2,
                'display': self.page.comboBox_display,
                'zoom': self.page.spinBox_zoom,
                'tc': self.page.spinBox_tc,
                'x': self.page.spinBox_x,
                'y': self.page.spinBox_y,
                'mirror': self.page.checkBox_mirror,
                'draw': self.page.checkBox_draw,
                'scale': self.page.spinBox_scale,
                'color': self.page.comboBox_color,
                'compress': self.page.checkBox_compress,
                'mono': self.page.checkBox_mono,
                'hue': self.page.spinBox_hue,
            }
        )
        for widget in self._trackedWidgets.values():
            connectWidget(widget, lambda: self.changed())

    def changed(self):
        self.changedOptions = True

    def update(self):
        self.page.stackedWidget.setCurrentIndex(
            self.page.comboBox_filterType.currentIndex())
        super().update()

    def previewRender(self):
        changedSize = self.updateChunksize()
        if not changedSize \
                and not self.changedOptions \
                and self.previewFrame is not None:
            return self.previewFrame

        frame = self.getPreviewFrame()
        self.changedOptions = False
        if not frame:
            self.previewFrame = None
            return BlankFrame(self.width, self.height)
        else:
            self.previewFrame = frame
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
            parent=self.parent, component=self,
        )

    def frameRender(self, frameNo):
        if FfmpegVideo.threadError is not None:
            raise FfmpegVideo.threadError
        return self.finalizeFrame(self.video.frame(frameNo))

    def postFrameRender(self):
        closePipe(self.video.pipe)

    def getPreviewFrame(self):
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
        logFilename = os.path.join(
            self.core.dataDir, 'preview_%s.log' % str(self.compPos))
        with open(logFilename, 'w') as log:
            log.write(" ".join(command) + '\n\n')
        with open(logFilename, 'a') as log:
            pipe = openPipe(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=log, bufsize=10**8
            )
        byteFrame = pipe.stdout.read(self.chunkSize)
        closePipe(pipe)

        frame = self.finalizeFrame(byteFrame)
        return frame

    def makeFfmpegFilter(self, preview=False, startPt=0):
        w, h = scale(self.scale, self.width, self.height, str)
        color = self.page.comboBox_color.currentText().lower()
        genericPreview = self.settings.value("pref_genericPreview")

        if self.filterType == 0:  # Spectrum
            if self.amplitude == 0:
                amplitude = 'sqrt'
            elif self.amplitude == 1:
                amplitude = 'cbrt'
            elif self.amplitude == 2:
                amplitude = '4thrt'
            elif self.amplitude == 3:
                amplitude = '5thrt'
            elif self.amplitude == 4:
                amplitude = 'lin'
            elif self.amplitude == 5:
                amplitude = 'log'
            filter_ = (
                'showspectrum=s=%sx%s:slide=scroll:win_func=%s:'
                'color=%s:scale=%s,'
                'colorkey=color=black:similarity=0.1:blend=0.5' % (
                    self.settings.value("outputWidth"),
                    self.settings.value("outputHeight"),
                    self.page.comboBox_window.currentText(),
                    color, amplitude,
                )
            )
        elif self.filterType == 1:  # Histogram
            if self.amplitude1 == 0:
                amplitude = 'log'
            elif self.amplitude1 == 1:
                amplitude = 'lin'
            if self.display == 0:
                display = 'log'
            elif self.display == 1:
                display = 'sqrt'
            elif self.display == 2:
                display = 'cbrt'
            elif self.display == 3:
                display = 'lin'
            elif self.display == 4:
                display = 'rlog'
            filter_ = (
                'ahistogram=r=%s:s=%sx%s:dmode=separate:ascale=%s:scale=%s' % (
                    self.settings.value("outputFrameRate"),
                    self.settings.value("outputWidth"),
                    self.settings.value("outputHeight"),
                    amplitude, display
                )
            )
        elif self.filterType == 2:  # Vector Scope
            if self.amplitude2 == 0:
                amplitude = 'log'
            elif self.amplitude2 == 1:
                amplitude = 'sqrt'
            elif self.amplitude2 == 2:
                amplitude = 'cbrt'
            elif self.amplitude2 == 3:
                amplitude = 'lin'
            m = self.page.comboBox_mode.currentText()
            filter_ = (
                'avectorscope=s=%sx%s:draw=%s:m=%s:scale=%s:zoom=%s' % (
                    self.settings.value("outputWidth"),
                    self.settings.value("outputHeight"),
                    'line'if self.draw else 'dot',
                    m, amplitude, str(self.zoom),
                )
            )
        elif self.filterType == 3:  # Musical Scale
            filter_ = (
                'showcqt=r=%s:s=%sx%s:count=30:text=0:tc=%s,'
                'colorkey=color=black:similarity=0.1:blend=0.5 ' % (
                    self.settings.value("outputFrameRate"),
                    self.settings.value("outputWidth"),
                    self.settings.value("outputHeight"),
                    str(self.tc),
                )
            )
        elif self.filterType == 4:  # Phase
            filter_ = (
                'aphasemeter=r=%s:s=%sx%s:video=1 [atrash][vtmp1]; '
                '[atrash] anullsink; '
                '[vtmp1] colorkey=color=black:similarity=0.1:blend=0.5 ' % (
                    self.settings.value("outputFrameRate"),
                    self.settings.value("outputWidth"),
                    self.settings.value("outputHeight"),
                )
            )

        return [
            '-filter_complex',
            '%s%s%s%s [v1]; '
            '[v1] %sscale=%s:%s%s%s%s [v]' % (
                exampleSound() if preview and genericPreview else '[0:a] ',
                'compand=gain=4,' if self.compress else '',
                'aformat=channel_layouts=mono,' if self.mono else '',
                filter_,
                'hflip, ' if self.mirror else '',
                w, h,
                ', hue=h=%s:s=10' % str(self.hue) if self.hue > 0 else '',
                ', trim=start=%s:end=%s' % (
                    "{0:.3f}".format(startPt + 12),
                    "{0:.3f}".format(startPt + 12.5)
                ) if preview else '',
                ', convolution=-2 -1 0 -1 1 1 0 1 2:-2 -1 0 -1 1 1 0 1 2:-2 '
                '-1 0 -1 1 1 0 1 2:-2 -1 0 -1 1 1 0 1 2'
                if self.filterType == 3 else ''
            ),
            '-map', '[v]',
        ]

    def updateChunksize(self):
        width, height = scale(self.scale, self.width, self.height, int)
        oldChunkSize = int(self.chunkSize)
        self.chunkSize = 4 * width * height
        changed = self.chunkSize != oldChunkSize
        return changed

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
