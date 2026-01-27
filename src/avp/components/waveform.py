from PIL import Image, ImageChops
from PyQt6.QtGui import QColor
import os
import subprocess
import logging
from copy import copy

from ..component import Component
from ..toolkit.visualizer import transformData, createSpectrumArray
from ..toolkit.frame import BlankFrame, scale
from ..toolkit import checkOutput
from ..toolkit.ffmpeg import (
    openPipe,
    closePipe,
    getAudioDuration,
    FfmpegVideo,
    exampleSound,
)


log = logging.getLogger("AVP.Components.Waveform")


class Component(Component):
    name = "Waveform"
    version = "2.0.0"

    @property
    def updateInterval(self):
        """How many frames from FFmpeg are ignored between each final frame"""
        return 100 - self.speed

    def properties(self):
        return [] if self.speed == 100 else ["pcm"]

    def widget(self, *args):
        super().widget(*args)
        self._image = BlankFrame(self.width, self.height)

        self.page.lineEdit_color.setText("255,255,255")

        if hasattr(self.parent, "lineEdit_audioFile"):
            self.parent.lineEdit_audioFile.textChanged.connect(self.update)

        self.trackWidgets(
            {
                "color": self.page.lineEdit_color,
                "mode": self.page.comboBox_mode,
                "amplitude": self.page.comboBox_amplitude,
                "x": self.page.spinBox_x,
                "y": self.page.spinBox_y,
                "mirror": self.page.checkBox_mirror,
                "scale": self.page.spinBox_scale,
                "opacity": self.page.spinBox_opacity,
                "compress": self.page.checkBox_compress,
                "mono": self.page.checkBox_mono,
                "speed": self.page.spinBox_speed,
            },
            colorWidgets={
                "color": self.page.pushButton_color,
            },
            relativeWidgets=[
                "x",
                "y",
            ],
        )

    def previewRender(self):
        self.updateChunksize()
        frame = self.getPreviewFrame(self.width, self.height)
        if not frame:
            return BlankFrame(self.width, self.height)
        else:
            return frame

    def preFrameRender(self, **kwargs):
        self._fadingImage = None
        self._prevImage = None
        self._currImage = None
        self._lastUpdatedFrame = 0
        super().preFrameRender(**kwargs)
        self.updateChunksize()
        w, h = scale(self.scale, self.width, self.height, str)
        self.video = FfmpegVideo(
            inputPath=self.audioFile,
            filter_=self.makeFfmpegFilter(),
            width=w,
            height=h,
            chunkSize=self.chunkSize,
            frameRate=int(self.settings.value("outputFrameRate")),
            parent=self.parent,
            component=self,
            debug=True,
        )
        if self.speed == 100:
            return
        self.spectrumArray = createSpectrumArray(
            self,
            self.completeAudioArray,
            self.sampleSize,
            0.08,
            0.8,
            20,
            self.progressBarUpdate,
            self.progressBarSetText,
        )

    def frameRender(self, frameNo):
        if FfmpegVideo.threadError is not None:
            raise FfmpegVideo.threadError
        newFrame = self.finalizeFrame(self.video.frame(frameNo))
        if self.speed == 100:
            return newFrame
        frameDiff = 0 if frameNo == 0 else frameNo % self.updateInterval
        peaks = [
            self.spectrumArray[frameNo * self.sampleSize][i * 4] for i in range(64)
        ]
        peakValue = 70 - (max(*peaks) - min(*peaks))
        isValidPeak = (
            peakValue > 27
            and frameNo - self._lastUpdatedFrame > self.updateInterval / 2
        )
        if frameDiff == 0 or isValidPeak:
            self._lastUpdatedFrame = frameNo
            self._fadingImage = self._prevImage
            self._prevImage = self._image
            self._currImage = newFrame
        usualAlpha = 0.0 + (1 / self.updateInterval) * frameDiff
        alpha = max(
            0.1
            + (
                1
                / max(
                    10,
                    peakValue,
                )
            ),
            usualAlpha,
        )
        baseImage = self._prevImage
        if self._fadingImage is not None:
            # fade away the old previous frame from ages ago
            baseImage = ImageChops.blend(
                self._prevImage, self._fadingImage, max(0.0, 0.9 - usualAlpha)
            )
        blendedImage = ImageChops.blend(
            baseImage,
            ImageChops.lighter(self._prevImage, newFrame),
            alpha,
        )
        baseImage.paste(blendedImage, (0, 0), mask=blendedImage)
        return Image.alpha_composite(self._currImage, baseImage)

    def postFrameRender(self):
        closePipe(self.video.pipe)

    def getPreviewFrame(self, width, height):
        genericPreview = self.settings.value("pref_genericPreview")
        startPt = 0
        if not genericPreview:
            inputFile = self.parent.lineEdit_audioFile.text()
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
            "-thread_queue_size",
            "512",
            "-r",
            str(self.settings.value("outputFrameRate")),
            "-ss",
            "{0:.3f}".format(startPt),
            "-i",
            self.core.junkStream if genericPreview else inputFile,
            "-f",
            "image2pipe",
            "-pix_fmt",
            "rgba",
        ]
        command.extend(self.makeFfmpegFilter(preview=True, startPt=startPt))
        command.extend(
            [
                "-an",
                "-s:v",
                "%sx%s" % scale(self.scale, self.width, self.height, str),
                "-codec:v",
                "rawvideo",
                "-",
                "-frames:v",
                "1",
            ]
        )
        if self.core.logEnabled:
            logFilename = os.path.join(
                self.core.logDir, "preview_%s.log" % str(self.compPos)
            )
            log.debug("Creating ffmpeg log at %s", logFilename)
            with open(logFilename, "w") as logf:
                logf.write(" ".join(command) + "\n\n")
            with open(logFilename, "a") as logf:
                pipe = openPipe(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=logf,
                    bufsize=10**8,
                )
        else:
            pipe = openPipe(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=10**8,
            )
        byteFrame = pipe.stdout.read(self.chunkSize)
        closePipe(pipe)

        frame = self.finalizeFrame(byteFrame)
        return frame

    def makeFfmpegFilter(self, preview=False, startPt=0):
        w, h = scale(self.scale, self.width, self.height, str)
        if self.amplitude == 0:
            amplitude = "log"
        elif self.amplitude == 1:
            amplitude = "sqrt"
        elif self.amplitude == 2:
            amplitude = "cbrt"
        elif self.amplitude == 3:
            amplitude = "lin"
        hexcolor = QColor(*self.color).name()
        opacity = "{0:.1f}".format(self.opacity / 100)
        genericPreview = self.settings.value("pref_genericPreview")
        if self.mode > 1:
            filter_ = (
                "showwaves="
                f'r={str(self.settings.value("outputFrameRate"))}:'
                f's={self.settings.value("outputWidth")}x{self.settings.value("outputHeight")}:'
                f'mode={self.page.comboBox_mode.currentText().lower() if self.mode != 3 else "p2p"}:'
                f"colors={hexcolor}@{opacity}:scale={amplitude}"
            )
        elif self.mode < 2:
            filter_ = (
                f'showfreqs=s={str(self.settings.value("outputWidth"))}x{str(self.settings.value("outputHeight"))}:'
                f'mode={"line" if self.mode == 0 else "bar"}:'
                f"colors={hexcolor}@{opacity}"
                f":ascale={amplitude}:fscale={'log' if self.mono else 'lin'}"
            )

        baselineHeight = int(self.height * (4 / 1080))
        return [
            "-filter_complex",
            f"{exampleSound('wave', extra='') if preview and genericPreview else '[0:a] '}"
            f"{'compand=gain=4,' if self.compress else ''}"
            f"{'aformat=channel_layouts=mono,' if self.mono and self.mode < 3 else ''}"
            f"{filter_}"
            f"{', drawbox=x=(iw-w)/2:y=(ih-h)/2:w=iw:h=%s:color=%s@%s' % (baselineHeight, hexcolor, opacity) if self.mode < 2 else ''}"
            f"{', hflip' if self.mirror else''}"
            " [v1]; "
            "[v1] scale=%s:%s%s [v]"
            % (
                w,
                h,
                ", trim=duration=%s" % "{0:.3f}".format(startPt + 3) if preview else "",
            ),
            "-map",
            "[v]",
        ]

    def updateChunksize(self):
        width, height = scale(self.scale, self.width, self.height, int)
        self.chunkSize = 4 * width * height

    def finalizeFrame(self, imageData):
        try:
            image = Image.frombytes(
                "RGBA",
                scale(self.scale, self.width, self.height, int),
                imageData,
            )
            self._image = image
        except ValueError:
            image = self._image
        if self.scale != 100 or self.x != 0 or self.y != 0:
            frame = BlankFrame(self.width, self.height)
            frame.paste(image, box=(self.x, self.y))
        else:
            frame = image
        return frame
