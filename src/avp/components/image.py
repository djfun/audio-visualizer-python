from PIL import Image, ImageOps, ImageEnhance
from PyQt6 import QtWidgets
import os
from copy import copy

from ..component import Component
from ..toolkit.frame import BlankFrame
from .original import Component as Visualizer


class Component(Component):
    name = "Image"
    version = "2.0.0"

    def widget(self, *args):
        super().widget(*args)

        # cache a modified image object in case we are rendering beyond frame 1
        self.existingImage = None

        self.page.pushButton_image.clicked.connect(self.pickImage)
        self.page.comboBox_resizeMode.addItem("Scale")
        self.page.comboBox_resizeMode.addItem("Cover")
        self.page.comboBox_resizeMode.addItem("Stretch")
        self.page.comboBox_resizeMode.setCurrentIndex(0)
        self.trackWidgets(
            {
                "imagePath": self.page.lineEdit_image,
                "scale": self.page.spinBox_scale,
                "rotate": self.page.spinBox_rotate,
                "color": self.page.spinBox_color,
                "xPosition": self.page.spinBox_x,
                "yPosition": self.page.spinBox_y,
                "resizeMode": self.page.comboBox_resizeMode,
                "mirror": self.page.checkBox_mirror,
                "respondToAudio": self.page.checkBox_respondToAudio,
                "sensitivity": self.page.spinBox_sensitivity,
            },
            presetNames={
                "imagePath": "image",
                "xPosition": "x",
                "yPosition": "y",
            },
            relativeWidgets=["xPosition", "yPosition", "scale"],
        )

    def update(self):
        self.page.spinBox_sensitivity.setEnabled(
            self.page.checkBox_respondToAudio.isChecked()
        )
        self.page.spinBox_scale.setEnabled(
            self.page.comboBox_resizeMode.currentIndex() == 0
        )

    def previewRender(self):
        return self.drawFrame(self.width, self.height, None)

    def properties(self):
        props = ["pcm" if self.respondToAudio else "static"]
        if not os.path.exists(self.imagePath):
            props.append("error")
        return props

    def error(self):
        if not self.imagePath:
            return "There is no image selected."
        if not os.path.exists(self.imagePath):
            return "The image selected does not exist!"

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        if not self.respondToAudio:
            return

        # Trigger creation of new base image
        self.existingImage = None

        smoothConstantDown = 0.08 + 0
        smoothConstantUp = 0.8 - 0
        self.lastSpectrum = None
        self.spectrumArray = {}

        for i in range(0, len(self.completeAudioArray), self.sampleSize):
            if self.canceled:
                break
            self.lastSpectrum = Visualizer.transformData(
                i,
                self.completeAudioArray,
                self.sampleSize,
                smoothConstantDown,
                smoothConstantUp,
                self.lastSpectrum,
                self.sensitivity,
            )
            self.spectrumArray[i] = copy(self.lastSpectrum)

            progress = int(100 * (i / len(self.completeAudioArray)))
            if progress >= 100:
                progress = 100
            pStr = "Analyzing audio: " + str(progress) + "%"
            self.progressBarSetText.emit(pStr)
            self.progressBarUpdate.emit(int(progress))

    def frameRender(self, frameNo):
        return self.drawFrame(
            self.width,
            self.height,
            (
                None
                if not self.respondToAudio
                else self.spectrumArray[frameNo * self.sampleSize]
            ),
        )

    def drawFrame(self, width, height, dynamicScale):
        frame = BlankFrame(width, height)
        if self.imagePath and os.path.exists(self.imagePath):
            if dynamicScale is not None and self.existingImage:
                image = self.existingImage
            else:
                image = Image.open(self.imagePath)
                # Modify static image appearance
                if self.color != 100:
                    image = ImageEnhance.Color(image).enhance(float(self.color / 100))
                if self.mirror:
                    image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if self.resizeMode == 1:  # Cover
                    image = ImageOps.fit(
                        image, (width, height), Image.Resampling.LANCZOS
                    )
                elif self.resizeMode == 2:  # Stretch
                    image = image.resize((width, height), Image.Resampling.LANCZOS)
                elif self.scale != 100:  # Scale
                    newHeight = int((image.height / 100) * self.scale)
                    newWidth = int((image.width / 100) * self.scale)
                    image = image.resize(
                        (newWidth, newHeight), Image.Resampling.LANCZOS
                    )
                self.existingImage = image

            # Respond to audio
            scale = 0
            if dynamicScale is not None:
                scale = dynamicScale[36 * 4] / 4
                image = ImageOps.contain(
                    image,
                    (
                        image.width + int(scale / 2),
                        image.height + int(scale / 2),
                    ),
                    Image.Resampling.LANCZOS,
                )

            # Paste image at correct position
            frame.paste(
                image,
                box=(
                    self.xPosition - (0 if not self.respondToAudio else int(scale / 2)),
                    self.yPosition - (0 if not self.respondToAudio else int(scale / 2)),
                ),
            )
            if self.rotate != 0:
                frame = frame.rotate(self.rotate)

        return frame

    def postFrameRender(self):
        self.existingImage = None

    def pickImage(self):
        imgDir = self.settings.value("componentDir", os.path.expanduser("~"))
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.page,
            "Choose Image",
            imgDir,
            "Image Files (%s)" % " ".join(self.core.imageFormats),
        )
        if filename:
            self.settings.setValue("componentDir", os.path.dirname(filename))
            self.mergeUndo = False
            self.page.lineEdit_image.setText(filename)
            self.mergeUndo = True

    def command(self, arg):
        if "=" in arg:
            key, arg = arg.split("=", 1)
            if key == "path" and os.path.exists(arg):
                try:
                    Image.open(arg)
                    self.page.lineEdit_image.setText(arg)
                    self.page.checkBox_stretch.setChecked(True)
                    return
                except OSError as e:
                    print("Not a supported image format")
                    quit(1)
        super().command(arg)

    def commandHelp(self):
        print("Load an image:\n    path=/filepath/to/image.png")
