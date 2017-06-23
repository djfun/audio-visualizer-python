from PIL import Image, ImageDraw
from PyQt4 import uic, QtGui, QtCore
import os
from . import __base__


class Component(__base__.Component):
    '''Image'''

    modified = QtCore.pyqtSignal(int, dict)

    def widget(self, parent):
        self.parent = parent
        self.settings = parent.settings
        page = uic.loadUi(os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'image.ui'))
        self.imagePath = ''
        self.x = 0
        self.y = 0

        page.lineEdit_image.textChanged.connect(self.update)
        page.pushButton_image.clicked.connect(self.pickImage)
        page.spinBox_scale.valueChanged.connect(self.update)
        page.checkBox_stretch.stateChanged.connect(self.update)
        page.spinBox_x.valueChanged.connect(self.update)
        page.spinBox_y.valueChanged.connect(self.update)

        self.page = page
        return page

    def update(self):
        self.imagePath = self.page.lineEdit_image.text()
        self.scale = self.page.spinBox_scale.value()
        self.xPosition = self.page.spinBox_x.value()
        self.yPosition = self.page.spinBox_y.value()
        self.stretched = self.page.checkBox_stretch.isChecked()
        self.parent.drawPreview()
        super().update()

    def previewRender(self, previewWorker):
        self.imageFormats = previewWorker.core.imageFormats
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        return self.drawFrame(width, height)

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        return ['static']

    def frameRender(self, moduleNo, arrayNo, frameNo):
        width = int(self.worker.core.settings.value('outputWidth'))
        height = int(self.worker.core.settings.value('outputHeight'))
        return self.drawFrame(width, height)

    def drawFrame(self, width, height):
        frame = self.blankFrame(width, height)
        if self.imagePath and os.path.exists(self.imagePath):
            image = Image.open(self.imagePath)
            if self.stretched and image.size != (width, height):
                image = image.resize((width, height), Image.ANTIALIAS)
            if self.scale != 100:
                newHeight = int((image.height / 100) * self.scale)
                newWidth = int((image.width / 100) * self.scale)
                image = image.resize((newWidth, newHeight), Image.ANTIALIAS)
            frame.paste(image, box=(self.xPosition, self.yPosition))
        return frame

    def loadPreset(self, pr, presetName=None):
        super().loadPreset(pr, presetName)
        self.page.lineEdit_image.setText(pr['image'])
        self.page.spinBox_scale.setValue(pr['scale'])
        self.page.spinBox_x.setValue(pr['x'])
        self.page.spinBox_y.setValue(pr['y'])
        self.page.checkBox_stretch.setChecked(pr['stretched'])

    def savePreset(self):
        return {
            'preset': self.currentPreset,
            'image': self.imagePath,
            'scale': self.scale,
            'stretched': self.stretched,
            'x': self.xPosition,
            'y': self.yPosition,
        }

    def pickImage(self):
        imgDir = self.settings.value("backgroundDir", os.path.expanduser("~"))
        filename = QtGui.QFileDialog.getOpenFileName(
            self.page, "Choose Image", imgDir,
            "Image Files (%s)" % " ".join(self.imageFormats))
        if filename:
            self.settings.setValue("backgroundDir", os.path.dirname(filename))
            self.page.lineEdit_image.setText(filename)
            self.update()

    def command(self, arg):
        if not arg.startswith('preset=') and '=' in arg:
            key, arg = arg.split('=', 1)
            if key == 'path' and os.path.exists(arg):
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
        print('Load an image:\n    path=/filepath/to/image.png')
