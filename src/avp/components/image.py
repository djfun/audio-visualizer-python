from PIL import Image, ImageOps, ImageEnhance
from PyQt6 import QtWidgets
import os

from ..component import Component
from ..toolkit.frame import BlankFrame


class Component(Component):
    name = "Image"
    version = "2.0.0"

    def widget(self, *args):
        super().widget(*args)
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
            },
            presetNames={
                "imagePath": "image",
                "xPosition": "x",
                "yPosition": "y",
            },
            relativeWidgets=["xPosition", "yPosition", "scale"],
        )

    def update(self):
        if self.page.comboBox_resizeMode.currentIndex() == 0:
            self.page.spinBox_scale.setEnabled(True)
        else:
            self.page.spinBox_scale.setEnabled(False)

    def previewRender(self):
        return self.drawFrame(self.width, self.height)

    def properties(self):
        props = ["static"]
        if not os.path.exists(self.imagePath):
            props.append("error")
        return props

    def error(self):
        if not self.imagePath:
            return "There is no image selected."
        if not os.path.exists(self.imagePath):
            return "The image selected does not exist!"

    def frameRender(self, frameNo):
        return self.drawFrame(self.width, self.height)

    def drawFrame(self, width, height):
        frame = BlankFrame(width, height)
        if self.imagePath and os.path.exists(self.imagePath):
            image = Image.open(self.imagePath)

            # Modify image's appearance
            if self.color != 100:
                image = ImageEnhance.Color(image).enhance(float(self.color / 100))
            if self.mirror:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if self.resizeMode == 1:  # Cover
                image = ImageOps.fit(image, (width, height), Image.Resampling.LANCZOS)
            elif self.resizeMode == 2:  # Stretch
                image = image.resize((width, height), Image.Resampling.LANCZOS)
            elif self.scale != 100:  # Scale
                newHeight = int((image.height / 100) * self.scale)
                newWidth = int((image.width / 100) * self.scale)
                image = image.resize((newWidth, newHeight), Image.Resampling.LANCZOS)

            # Paste image at correct position
            frame.paste(image, box=(self.xPosition, self.yPosition))
            if self.rotate != 0:
                frame = frame.rotate(self.rotate)

        return frame

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
