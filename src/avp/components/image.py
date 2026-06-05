from PIL import Image, ImageOps, ImageEnhance
from PyQt6 import QtWidgets, QtCore
import os

from ..libcomponent import BaseComponent
from ..libcomponent.actions import ComponentPreviewClick, ComponentSettingsUpdate
from ..toolkit.frame import BlankFrame, addShadow
from ..toolkit.visualizer import createSpectrumArray


class Component(BaseComponent):
    name = "Image"
    version = "2.2.0"

    def widget(self, *args):
        super().widget(*args)

        # cache a modified image object in case we are rendering beyond frame 1
        self.existingImage = None

        # cache image size for reference when centering the image
        self.imageSize = (0, 0)

        self.page.pushButton_image.clicked.connect(self.pickImage)
        self.page.pushButton_centerImage.clicked.connect(self.addCenterAction)
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
                "shadow": self.page.checkBox_shadow,
                "shadX": self.page.spinBox_shadX,
                "shadY": self.page.spinBox_shadY,
                "shadBlur": self.page.spinBox_shadBlur,
            },
            presetNames={
                "imagePath": "image",
                "xPosition": "x",
                "yPosition": "y",
            },
            relativeWidgets=[
                "xPosition",
                "yPosition",
                "scale",
                "shadX",
                "shadY",
                "shadBlur",
            ],
        )

    def update(self):
        self.page.spinBox_sensitivity.setEnabled(
            self.page.checkBox_respondToAudio.isChecked()
        )
        self.page.spinBox_scale.setEnabled(
            self.page.comboBox_resizeMode.currentIndex() == 0
        )
        if self.page.checkBox_shadow.isChecked():
            self.page.label_shadOffset.setHidden(False)
            self.page.spinBox_shadX.setHidden(False)
            self.page.spinBox_shadY.setHidden(False)
            self.page.label_shadBlur.setHidden(False)
            self.page.spinBox_shadBlur.setHidden(False)
        else:
            self.page.label_shadOffset.setHidden(True)
            self.page.spinBox_shadX.setHidden(True)
            self.page.spinBox_shadY.setHidden(True)
            self.page.label_shadBlur.setHidden(True)
            self.page.spinBox_shadBlur.setHidden(True)

    def previewClickEvent(self, pos, size, button):
        if self.imageSize == (0, 0) or button != QtCore.Qt.MouseButton.LeftButton:
            return
        action = ClickPreviewAction(self, pos, size, button)
        self.parent.undoStack.push(action)

    def addCenterAction(self):
        """Triggered when user clicks "center image" button."""
        if self.imageSize == (0, 0):
            return
        action = CenterImageAction(self)
        self.parent.undoStack.push(action)

    def centerXY(self):
        self.setRelativeWidget(
            "xPosition",
            0.5 - (self.floatValForAttr("xPosition", self.imageSize[0]) / 2),
        )
        self.setRelativeWidget(
            "yPosition",
            0.5 - (self.floatValForAttr("yPosition", self.imageSize[1] / 2)),
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

        self.spectrumArray = createSpectrumArray(
            self,
            self.completeAudioArray,
            self.sampleSize,
            0.08,
            0.8,
            self.sensitivity,
            self.progressBarUpdate,
            self.progressBarSetText,
        )

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
                self.imageSize = (image.width, image.height)

            # Shadow-related variables (modified below if "respond to audio")
            resolutionFactor = height / 1080
            shadX = int(resolutionFactor * self.shadX)
            shadY = int(resolutionFactor * self.shadY)
            shadBlur = resolutionFactor * (self.shadBlur / 10)

            # Respond to audio
            scale = 0
            if dynamicScale is not None:
                scale = dynamicScale[36 * 4] / 4
                shadX += int((scale / 4) * resolutionFactor)
                shadY += int((scale / 2) * resolutionFactor)
                shadBlur += (scale / 8) * resolutionFactor
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
            if self.shadow:
                frame = addShadow(frame, shadBlur, shadX, shadY)
        else:
            self.imageSize = (0, 0)
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
        def fail():
            print("Not a supported image format")
            quit(1)

        if "=" in arg:
            key, arg = arg.split("=", 1)
            if key == "path" and os.path.exists(arg):
                if f"*{os.path.splitext(arg)[1]}" not in self.core.imageFormats:
                    fail()
                try:
                    Image.open(arg)
                    self.page.lineEdit_image.setText(arg)
                    self.page.comboBox_resizeMode.setCurrentIndex(2)
                    return
                except OSError as e:
                    fail()
        super().command(arg)

    def commandHelp(self):
        print("Load an image:\n    path=/filepath/to/image.png")


class ClickPreviewAction(ComponentPreviewClick):
    def __init__(self, *args):
        super().__init__(*args)

        self.oldXY = (
            self.comp.floatValForAttr("xPosition"),
            self.comp.floatValForAttr("yPosition"),
        )

    def add(self):
        for pos in self.pos[:]:
            self.comp.setRelativeWidget("xPosition", pos[0] / self.size[0])
            self.comp.setRelativeWidget("yPosition", pos[1] / self.size[1])

    def remove(self):
        self.comp.setRelativeWidget("xPosition", self.oldXY[0])
        self.comp.setRelativeWidget("yPosition", self.oldXY[1])


class CenterImageAction(ComponentSettingsUpdate):
    def __init__(self, comp):
        super().__init__(comp)
        self.oldXY = (
            self.comp.floatValForAttr("xPosition"),
            self.comp.floatValForAttr("yPosition"),
        )

    def redo(self):
        self.comp.centerXY()

    def undo(self):
        self.comp.setRelativeWidget("xPosition", self.oldXY[0])
        self.comp.setRelativeWidget("yPosition", self.oldXY[1])
