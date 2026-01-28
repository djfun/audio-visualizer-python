import numpy
from PIL import Image, ImageDraw
from copy import copy

from ..component import Component
from ..toolkit.frame import BlankFrame
from ..toolkit.visualizer import createSpectrumArray


class Component(Component):
    name = "Classic Visualizer"
    version = "1.1.0"

    def names(*args):
        return ["Original Audio Visualization"]

    def properties(self):
        return ["pcm"]

    def widget(self, *args):
        self.scale = 20
        self.bars = 63
        self.y = 0
        super().widget(*args)

        self.page.comboBox_visLayout.addItem("Classic")
        self.page.comboBox_visLayout.addItem("Split")
        self.page.comboBox_visLayout.addItem("Bottom")
        self.page.comboBox_visLayout.addItem("Top")
        self.page.comboBox_visLayout.setCurrentIndex(0)

        self.trackWidgets(
            {
                "visColor": self.page.lineEdit_visColor,
                "layout": self.page.comboBox_visLayout,
                "scale": self.page.spinBox_scale,
                "y": self.page.spinBox_y,
                "smooth": self.page.spinBox_sensitivity,
                "bars": self.page.spinBox_bars,
            },
            colorWidgets={
                "visColor": self.page.pushButton_visColor,
            },
            relativeWidgets=[
                "y",
            ],
        )

    def previewRender(self):
        spectrum = numpy.fromfunction(
            lambda x: float(self.scale) / 2500 * (x - 128) ** 2,
            (255,),
            dtype="int16",
        )
        return self.drawBars(
            self.width, self.height, spectrum, self.visColor, self.layout
        )

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        smoothConstantDown = 0.08 if not self.smooth else self.smooth / 15
        smoothConstantUp = 0.8 if not self.smooth else self.smooth / 15
        self.spectrumArray = createSpectrumArray(
            self,
            self.completeAudioArray,
            self.sampleSize,
            smoothConstantDown,
            smoothConstantUp,
            self.scale,
            self.progressBarUpdate,
            self.progressBarSetText,
        )

    def frameRender(self, frameNo):
        arrayNo = frameNo * self.sampleSize
        return self.drawBars(
            self.width,
            self.height,
            self.spectrumArray[arrayNo],
            self.visColor,
            self.layout,
        )

    def drawBars(self, width, height, spectrum, color, layout):
        bigYCoord = height - height / 8
        smallYCoord = height / 1200
        bigXCoord = width / (self.bars + 1)
        middleXCoord = bigXCoord / 2
        smallXCoord = bigXCoord / 4

        imTop = BlankFrame(width, height)
        draw = ImageDraw.Draw(imTop)
        r, g, b = color
        color2 = (r, g, b, 125)

        for i in range(self.bars):
            x0 = middleXCoord + i * bigXCoord
            y0 = bigYCoord + smallXCoord
            y1 = bigYCoord + smallXCoord - spectrum[i * 4] * smallYCoord - middleXCoord
            x1 = middleXCoord + i * bigXCoord + bigXCoord
            draw.rectangle(
                (
                    x0,
                    y0 if y0 < y1 else y1,
                    x1 if x1 > x0 else x0,
                    y1 if y0 < y1 else y0,
                ),
                fill=color2,
            )

            x0 = middleXCoord + smallXCoord + i * bigXCoord
            y0 = bigYCoord
            x1 = middleXCoord + smallXCoord + i * bigXCoord + middleXCoord
            y1 = bigYCoord - spectrum[i * 4] * smallYCoord
            draw.rectangle(
                (
                    x0,
                    y0 if y0 < y1 else y1,
                    x1 if x1 > x0 else x0,
                    y1 if y0 < y1 else y0,
                ),
                fill=color,
            )

        imBottom = imTop.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        im = BlankFrame(width, height)

        if layout == 0:  # Classic
            y = self.y - int(height / 100 * 43)
            im.paste(imTop, (0, y), mask=imTop)
            y = self.y + int(height / 100 * 43)
            im.paste(imBottom, (0, y), mask=imBottom)

        if layout == 1:  # Split
            y = self.y + int(height / 100 * 10)
            im.paste(imTop, (0, y), mask=imTop)
            y = self.y - int(height / 100 * 10)
            im.paste(imBottom, (0, y), mask=imBottom)

        if layout == 2:  # Bottom
            y = self.y + int(height / 100 * 10)
            im.paste(imTop, (0, y), mask=imTop)

        if layout == 3:  # Top
            y = self.y - int(height / 100 * 10)
            im.paste(imBottom, (0, y), mask=imBottom)

        return im

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
