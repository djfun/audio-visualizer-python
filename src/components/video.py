from PIL import Image
from PyQt5 import QtGui, QtCore, QtWidgets
import os
import math
import subprocess
import logging

from component import Component
from toolkit.frame import BlankFrame, scale
from toolkit.ffmpeg import openPipe, closePipe, testAudioStream, FfmpegVideo
from toolkit import checkOutput


log = logging.getLogger('AVP.Components.Video')


class Component(Component):
    name = 'Video'
    version = '1.0.0'

    def widget(self, *args):
        self.videoPath = ''
        self.badAudio = False
        self.x = 0
        self.y = 0
        self.loopVideo = False
        super().widget(*args)
        self._image = BlankFrame(self.width, self.height)
        self.page.pushButton_video.clicked.connect(self.pickVideo)
        self.trackWidgets({
            'videoPath': self.page.lineEdit_video,
            'loopVideo': self.page.checkBox_loop,
            'useAudio': self.page.checkBox_useAudio,
            'distort': self.page.checkBox_distort,
            'scale': self.page.spinBox_scale,
            'volume': self.page.spinBox_volume,
            'xPosition': self.page.spinBox_x,
            'yPosition': self.page.spinBox_y,
        }, presetNames={
            'videoPath': 'video',
            'loopVideo': 'loop',
            'xPosition': 'x',
            'yPosition': 'y',
        }, relativeWidgets=[
            'xPosition', 'yPosition',
        ])

    def update(self):
        if self.page.checkBox_useAudio.isChecked():
            self.page.label_volume.setEnabled(True)
            self.page.spinBox_volume.setEnabled(True)
        else:
            self.page.label_volume.setEnabled(False)
            self.page.spinBox_volume.setEnabled(False)
        super().update()

    def previewRender(self):
        self.updateChunksize()
        frame = self.getPreviewFrame(self.width, self.height)
        if not frame:
            return BlankFrame(self.width, self.height)
        else:
            return frame

    def properties(self):
        props = []
        if hasattr(self.parent, 'window'):
            outputFile = self.parent.window.lineEdit_outputFile.text()
        else:
            outputFile = str(self.parent.args.output)

        if not self.videoPath:
            self.lockError("There is no video selected.")
        elif not os.path.exists(self.videoPath):
            self.lockError("The video selected does not exist!")
        elif os.path.realpath(self.videoPath) == os.path.realpath(outputFile):
            self.lockError("Input and output paths match.")

        if self.useAudio:
            props.append('audio')
            if not testAudioStream(self.videoPath) \
                    and self.error() is None:
                self.lockError(
                    "Could not identify an audio stream in this video.")

        return props

    def audio(self):
        params = {}
        if self.volume != 1.0:
            params['volume'] = '=%s:replaygain_noclip=0' % str(self.volume)
        return (self.videoPath, params)

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        self.updateChunksize()
        self.video = FfmpegVideo(
            inputPath=self.videoPath, filter_=self.makeFfmpegFilter(),
            width=self.width, height=self.height, chunkSize=self.chunkSize,
            frameRate=int(self.settings.value("outputFrameRate")),
            parent=self.parent, loopVideo=self.loopVideo,
            component=self
        ) if os.path.exists(self.videoPath) else None

    def frameRender(self, frameNo):
        if FfmpegVideo.threadError is not None:
            raise FfmpegVideo.threadError
        return self.finalizeFrame(self.video.frame(frameNo))

    def postFrameRender(self):
        closePipe(self.video.pipe)

    def pickVideo(self):
        imgDir = self.settings.value("componentDir", os.path.expanduser("~"))
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.page, "Choose Video",
            imgDir, "Video Files (%s)" % " ".join(self.core.videoFormats)
        )
        if filename:
            self.settings.setValue("componentDir", os.path.dirname(filename))
            self.page.lineEdit_video.setText(filename)
            self.update()

    def getPreviewFrame(self, width, height):
        if not self.videoPath or not os.path.exists(self.videoPath):
            return

        command = [
            self.core.FFMPEG_BIN,
            '-thread_queue_size', '512',
            '-i', self.videoPath,
            '-f', 'image2pipe',
            '-pix_fmt', 'rgba',
        ]
        command.extend(self.makeFfmpegFilter())
        command.extend([
            '-codec:v', 'rawvideo', '-',
            '-ss', '90',
            '-frames:v', '1',
        ])

        logFilename = os.path.join(
            self.core.logDir, 'preview_%s.log' % str(self.compPos))
        log.debug('Creating ffmpeg process (log at %s)' % logFilename)
        with open(logFilename, 'w') as logf:
            logf.write(" ".join(command) + '\n\n')
        with open(logFilename, 'a') as logf:
            pipe = openPipe(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=logf, bufsize=10**8
            )
        byteFrame = pipe.stdout.read(self.chunkSize)
        closePipe(pipe)

        frame = self.finalizeFrame(byteFrame)
        return frame

    def makeFfmpegFilter(self):
        return [
            '-filter_complex',
            '[0:v] scale=%s:%s' % scale(
                self.scale, self.width, self.height, str),
        ]

    def updateChunksize(self):
        if self.scale != 100 and not self.distort:
            width, height = scale(self.scale, self.width, self.height, int)
        else:
            width, height = self.width, self.height
        self.chunkSize = 4 * width * height

    def command(self, arg):
        if '=' in arg:
            key, arg = arg.split('=', 1)
            if key == 'path' and os.path.exists(arg):
                if '*%s' % os.path.splitext(arg)[1] in self.core.videoFormats:
                    self.page.lineEdit_video.setText(arg)
                    self.page.spinBox_scale.setValue(100)
                    self.page.checkBox_loop.setChecked(True)
                    return
                else:
                    print("Not a supported video format")
                    quit(1)
        elif arg == 'audio':
            if not self.page.lineEdit_video.text():
                print("'audio' option must follow a video selection")
                quit(1)
            self.page.checkBox_useAudio.setChecked(True)
            return
        super().command(arg)

    def commandHelp(self):
        print('Load a video:\n    path=/filepath/to/video.mp4')
        print('Using audio:\n    path=/filepath/to/video.mp4 audio')

    def finalizeFrame(self, imageData):
        try:
            if self.distort:
                image = Image.frombytes(
                    'RGBA',
                    (self.width, self.height),
                    imageData)
            else:
                image = Image.frombytes(
                    'RGBA',
                    scale(self.scale, self.width, self.height, int),
                    imageData)
            self._image = image
        except ValueError:
            # use last good frame
            image = self._image

        if self.scale != 100 \
                or self.xPosition != 0 or self.yPosition != 0:
            frame = BlankFrame(self.width, self.height)
            frame.paste(image, box=(self.xPosition, self.yPosition))
        else:
            frame = image
        return frame
