from PIL import ImageEnhance, ImageFilter, ImageChops
from PyQt6.QtGui import QColor, QFont
from PyQt6 import QtGui, QtCore, QtWidgets
import os
import logging

from ..component import Component
from ..toolkit.frame import FramePainter, PaintColor

log = logging.getLogger("AVP.Components.Text")


class Component(Component):
    name = "Title Text"
    version = "1.0.1"

    def widget(self, *args):
        super().widget(*args)
        self.title = "Text"
        self.alignment = 1
        self.titleFont = QFont()
        self.fontSize = self.height / 13.5

        self.page.comboBox_textAlign.addItem("Left")
        self.page.comboBox_textAlign.addItem("Middle")
        self.page.comboBox_textAlign.addItem("Right")
        self.page.comboBox_textAlign.setCurrentIndex(int(self.alignment))
        self.page.spinBox_fontSize.setValue(int(self.fontSize))
        self.page.lineEdit_title.setText(self.title)
        self.page.pushButton_center.clicked.connect(self.centerXY)

        self.page.fontComboBox_titleFont.currentFontChanged.connect(
            self._sendUpdateSignal
        )
        # The QFontComboBox must be connected directly to the Qt Signal
        # which triggers the preview to update.
        # This unfortunately makes changing the font into a non-undoable action.
        # Must be something broken in the conversion to a ComponentAction

        self.trackWidgets(
            {
                "textColor": self.page.lineEdit_textColor,
                "title": self.page.lineEdit_title,
                "alignment": self.page.comboBox_textAlign,
                "fontSize": self.page.spinBox_fontSize,
                "xPosition": self.page.spinBox_xTextAlign,
                "yPosition": self.page.spinBox_yTextAlign,
                "fontStyle": self.page.comboBox_fontStyle,
                "stroke": self.page.spinBox_stroke,
                "strokeColor": self.page.lineEdit_strokeColor,
                "shadow": self.page.checkBox_shadow,
                "shadX": self.page.spinBox_shadX,
                "shadY": self.page.spinBox_shadY,
                "shadBlur": self.page.spinBox_shadBlur,
            },
            colorWidgets={
                "textColor": self.page.pushButton_textColor,
                "strokeColor": self.page.pushButton_strokeColor,
            },
            relativeWidgets=[
                "xPosition",
                "yPosition",
                "fontSize",
                "stroke",
                "shadX",
                "shadY",
                "shadBlur",
            ],
        )
        self.centerXY()

    def update(self):
        self.titleFont = self.page.fontComboBox_titleFont.currentFont()
        if self.page.checkBox_shadow.isChecked():
            self.page.label_shadX.setHidden(False)
            self.page.spinBox_shadX.setHidden(False)
            self.page.spinBox_shadY.setHidden(False)
            self.page.label_shadBlur.setHidden(False)
            self.page.spinBox_shadBlur.setHidden(False)
        else:
            self.page.label_shadX.setHidden(True)
            self.page.spinBox_shadX.setHidden(True)
            self.page.spinBox_shadY.setHidden(True)
            self.page.label_shadBlur.setHidden(True)
            self.page.spinBox_shadBlur.setHidden(True)

    def centerXY(self):
        self.setRelativeWidget("xPosition", 0.5)
        self.setRelativeWidget("yPosition", 0.521)

    def getXY(self):
        """Returns true x, y after considering alignment settings"""
        fm = QtGui.QFontMetrics(self.titleFont)
        text_width = fm.boundingRect(self.title).width()
        x = self.pixelValForAttr("xPosition")

        if self.alignment == 1:  # Middle
            offset = int(text_width / 2)
        elif self.alignment == 2:  # Right
            offset = text_width
        else:
            raise ValueError(f"Alignment value {self.alignment} unknown")

        x -= offset

        return x, self.yPosition

    def loadPreset(self, pr, *args):
        super().loadPreset(pr, *args)

        font = QFont()
        font.fromString(pr["titleFont"])
        self.page.fontComboBox_titleFont.setCurrentFont(font)

    def savePreset(self):
        saveValueStore = super().savePreset()
        saveValueStore["titleFont"] = self.titleFont.toString()
        return saveValueStore

    def previewRender(self):
        return self.addText(self.width, self.height)

    def properties(self):
        props = ["static"]
        if not self.title:
            props.append("error")
        return props

    def error(self):
        return "No text provided."

    def frameRender(self, frameNo):
        return self.addText(self.width, self.height)

    def addText(self, width, height):
        font = self.titleFont
        font.setPixelSize(self.fontSize)
        font.setStyle(QFont.Style.StyleNormal)
        font.setWeight(QFont.Weight.Normal)
        font.setCapitalization(QFont.Capitalization.MixedCase)
        if self.fontStyle == 1:
            font.setWeight(QFont.Weight.DemiBold)
        if self.fontStyle == 2:
            font.setWeight(QFont.Weight.Bold)
        elif self.fontStyle == 3:
            font.setStyle(QFont.Style.StyleItalic)
        elif self.fontStyle == 4:
            font.setWeight(QFont.Weight.Bold)
            font.setStyle(QFont.Style.StyleItalic)
        elif self.fontStyle == 5:
            font.setStyle(QFont.Style.StyleOblique)
        elif self.fontStyle == 6:
            font.setCapitalization(QFont.Capitalization.SmallCaps)

        image = FramePainter(width, height)
        x, y = self.getXY()
        log.debug("Text position translates to %s, %s", x, y)
        if self.stroke > 0:
            outliner = QtGui.QPainterPathStroker()
            outliner.setWidth(self.stroke)
            path = QtGui.QPainterPath()
            if self.fontStyle == 6:
                # PathStroker ignores smallcaps so we need this weird hack
                path.addText(x, y, font, self.title[0])
                fm = QtGui.QFontMetrics(font)
                newX = x + fm.boundingRect(self.title[0]).width()
                strokeFont = self.page.fontComboBox_titleFont.currentFont()
                strokeFont.setCapitalization(QFont.Capitalization.SmallCaps)
                strokeFont.setPixelSize(int((self.fontSize / 7) * 5))
                strokeFont.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 139)
                path.addText(newX, y, strokeFont, self.title[1:])
            else:
                path.addText(x, y, font, self.title)
            path = outliner.createStroke(path)
            image.setPen(QtCore.Qt.PenStyle.NoPen)
            image.setBrush(PaintColor(*self.strokeColor))
            image.drawPath(path)

        image.setFont(font)
        image.setPen(self.textColor)
        image.drawText(x, y, self.title)

        # turn QImage into Pillow frame
        frame = image.finalize()
        if self.shadow:
            shadImg = ImageEnhance.Contrast(frame).enhance(0.0)
            shadImg = shadImg.filter(ImageFilter.GaussianBlur(self.shadBlur))
            shadImg = ImageChops.offset(shadImg, self.shadX, self.shadY)
            shadImg.paste(frame, box=(0, 0), mask=frame)
            frame = shadImg

        return frame

    def commandHelp(self):
        print("Enter a string to use as centred white text:")
        print('    "title=User Error"')
        print("Specify a text color:\n    color=255,255,255")
        print("Set custom x, y position:\n    x=500 y=500")

    def command(self, arg):
        if "=" in arg:
            key, arg = arg.split("=", 1)
            if key == "color":
                self.page.lineEdit_textColor.setText(arg)
                return
            elif key == "size":
                self.page.spinBox_fontSize.setValue(int(arg))
                return
            elif key == "x":
                self.page.spinBox_xTextAlign.setValue(int(arg))
                return
            elif key == "y":
                self.page.spinBox_yTextAlign.setValue(int(arg))
                return
            elif key == "title":
                self.page.lineEdit_title.setText(arg)
                return
        super().command(arg)
