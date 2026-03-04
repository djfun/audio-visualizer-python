import numpy
from PIL import Image, ImageDraw, ImageChops

from ..libcomponent import BaseComponent
from ..toolkit.frame import BlankFrame
from ..toolkit.visualizer import createSpectrumArray

sparsity = 15


class Component(BaseComponent):
    name = "Trails"
    version = "1.0.0"

    def properties(self):
        return ["pcm", "composite"]

    def widget(self, *args):
        self.scale = 20
        self.lastPeaks = list([0.0] * 64)
        super().widget(*args)

        self.trackWidgets(
            {
                "color": self.page.lineEdit_color,
                "scale": self.page.spinBox_scale,
                "sensitivity": self.page.spinBox_sensitivity,
            },
            colorWidgets={
                "color": self.page.pushButton_color,
            },
        )

    def previewRender(self, frame=None):
        spectrum = numpy.fromfunction(
            lambda x: float(self.scale + 20) / 2500 * (x - 128) ** 2,
            (255,),
            dtype="int16",
        )
        image = self.drawBars(-1, self.width, self.height, spectrum, self.color)
        for num in range(-16, 16, 4):
            zone = (
                int(num % 32 + ((1 / 30) - 0.50)),
                -8,
            )
            image.paste(image, zone, mask=image)
        return Image.alpha_composite(frame, image)

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        self.frameBuffer = {}
        self.swerveLeft = False
        self.lastPeaks = list([0.0] * 64)
        self.peakSpamHistory = set()

        smoothConstantDown = 0.08 if not self.sensitivity else self.sensitivity / 15
        smoothConstantUp = 0.8 if not self.sensitivity else self.sensitivity / 15
        self.spectrumArray = createSpectrumArray(
            self,
            self.completeAudioArray,
            self.sampleSize,
            smoothConstantDown,
            smoothConstantUp,
            self.scale + 20,
            self.progressBarUpdate,
            self.progressBarSetText,
        )

    def frameRender(self, frameNo, frame=None):
        arrayNo = frameNo * self.sampleSize
        img = self.drawBars(
            frameNo,
            self.width,
            self.height,
            self.spectrumArray[arrayNo],
            self.color,
        )
        fragment = img.copy()
        self.frameBuffer[frameNo] = fragment

        startZone = max(0, frameNo - 8)
        scrollFrame = frameNo % (self.width / 64)
        if scrollFrame == 0:
            self.swerveLeft = not self.swerveLeft

        for num, fnum in zip(range(frameNo, startZone, -1), range(startZone, frameNo)):
            swerveX = int(num % 4 + (((frameNo - startZone) / 30) - 0.50))
            zone = (
                -swerveX if self.swerveLeft else swerveX,
                -(frameNo - startZone),
            )
            img = Image.alpha_composite(
                img,
                self.frameBuffer[fnum],
            )
            fragment.paste(
                img,
                zone,
                self.frameBuffer[num],
            )

        if frameNo > 0 and frame is not None:
            self.frameBuffer[frameNo - 1].paste(
                frame,
                (0, 0),
                mask=self.frameBuffer[frameNo - 1],
            )

        # keep buffer small
        if frameNo - startZone > 7:
            del self.frameBuffer[startZone]
        # TODO put in test
        assert len(self.frameBuffer) < 9

        return Image.alpha_composite(frame, Image.alpha_composite(fragment, img))

    def drawBars(self, frameNo, width, height, spectrum, color):
        smallYCoord = height / 1200
        bigYCoord = height  # - smallYCoord
        bigXCoord = width / 64

        # scrollFrame = frameNo % width
        middleXCoord = bigXCoord / width  # scrollFrame
        smallXCoord = bigXCoord / width  # scrollFrame

        im = BlankFrame(width, height)
        draw = ImageDraw.Draw(im)
        r, g, b = color

        def drawOneBar(i, alpha=None):
            # x0 = ((middleXCoord + i) * bigXCoord) - (middleXCoord * bigXCoord)
            peakOfTwo = numpy.maximum(spectrum[i * 4], spectrum[(i + 1) * 4]) - 1
            ratio = max((peakOfTwo / 255), 0.0)
            if alpha is None:
                alpha = min(min(int(255 * ratio) - int(200 - peakOfTwo), 64), 255)

            color = (r, g, b, alpha)
            x0 = (middleXCoord + i) * bigXCoord
            y0 = bigYCoord + smallXCoord
            x1 = ((middleXCoord + i) * bigXCoord) + (bigXCoord * ratio)
            y1 = bigYCoord + smallXCoord - peakOfTwo * smallYCoord - middleXCoord
            if alpha == 255:
                x0 -= smallXCoord * ratio
                x1 += smallXCoord * ratio
            draw.rounded_rectangle(
                (
                    x0,
                    y0 if y0 < y1 else y1,
                    x1 if x1 > x0 else x0,
                    y1 if y0 < y1 else y0,
                ),
                radius=50,
                fill=color,
            )

        if frameNo < 0:
            for i in range(0, 64, 2):
                drawOneBar(i)
            return im
        else:
            peaks = [
                self.spectrumArray[frameNo * self.sampleSize][i * 4] for i in range(64)
            ]
            lastPeak = max(*self.lastPeaks)
            newPeakDiff = 0.0
            newPeakIndex = 0
            for i, val in enumerate(peaks):
                if i in self.peakSpamHistory:
                    continue
                diff = abs(val - lastPeak)

                if diff > newPeakDiff:
                    newPeakDiff = diff
                    newPeakIndex = i
                if val > 200:
                    drawOneBar(i)
            # print(newPeakIndex)
            if len(self.peakSpamHistory) > sparsity:
                self.peakSpamHistory = set()
            self.peakSpamHistory.add(newPeakIndex)
            drawOneBar(newPeakIndex, 255)
            self.lastPeaks = peaks
            """
            peakIndex = peaks.index(maxPeak)
            if frameNo % 64 > 31:
                drawOneBar(peakIndex)
            else:
                drawOneBar(frameNo % 32)
                drawOneBar(31 + (frameNo % 32))
            """
            return ImageChops.offset(
                im, int(newPeakDiff) if self.swerveLeft else -int(newPeakDiff), 0
            )
        # image = BlankFrame()
        # image.paste(im, (0, 0), mask=im)

    def command(self, arg):
        if "=" in arg:
            key, arg = arg.split("=", 1)
            try:
                if key == "color":
                    self.page.lineEdit_visColor.setText(arg)
                    return
                elif key == "layout":
                    if arg == "classic":
                        self.page.comboBox_visLayout.setCurrentIndex(0)
                    elif arg == "split":
                        self.page.comboBox_visLayout.setCurrentIndex(1)
                    elif arg == "bottom":
                        self.page.comboBox_visLayout.setCurrentIndex(2)
                    elif arg == "top":
                        self.page.comboBox_visLayout.setCurrentIndex(3)
                    return
                elif key == "scale":
                    arg = int(arg)
                    self.page.spinBox_scale.setValue(arg)
                    return
                elif key == "y":
                    arg = int(arg)
                    self.page.spinBox_y.setValue(arg)
                    return
            except ValueError:
                print("You must enter a number.")
                quit(1)
        super().command(arg)

    def commandHelp(self):
        print("Give a layout name:\n    layout=[classic/split/bottom/top]")
        print("Specify a color:\n    color=255,255,255")
        print("Visualizer scale (20 is default):\n    scale=number")
        print("Y position:\n    y=number")
