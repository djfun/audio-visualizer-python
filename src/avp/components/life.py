from PyQt6 import QtCore, QtWidgets
from PyQt6.QtGui import QUndoCommand
from PIL import Image, ImageDraw, ImageEnhance, ImageChops, ImageFilter, ImageOps
import os
from copy import copy
import math
import logging


from ..component import Component
from ..toolkit.frame import BlankFrame, scale, addShadow
from ..toolkit.visualizer import createSpectrumArray


log = logging.getLogger("AVP.Component.Life")


class Component(Component):
    name = "Conway's Game of Life"
    version = "2.0.1"

    def widget(self, *args):
        super().widget(*args)
        self.scale = 32
        self.updateGridSize()
        # The initial grid: a "Queen Bee Shuttle"
        # https://conwaylife.com/wiki/Queen_bee_shuttle
        self.startingGrid = set(
            [
                (3, 11),
                (3, 12),
                (4, 11),
                (4, 12),
                (8, 11),
                (9, 10),
                (9, 12),
                (10, 9),
                (10, 13),
                (11, 10),
                (11, 11),
                (11, 12),
                (12, 8),
                (12, 9),
                (12, 13),
                (12, 14),
                (23, 10),
                (23, 11),
                (24, 10),
                (24, 11),
            ]
        )

        # Amount of 'bleed' (off-canvas coordinates) on each side of the grid
        self.bleedSize = 40

        self.page.pushButton_pickImage.clicked.connect(self.pickImage)
        self.trackWidgets(
            {
                "tickRate": self.page.spinBox_tickRate,
                "scale": self.page.spinBox_scale,
                "color": self.page.lineEdit_color,
                "shapeType": self.page.comboBox_shapeType,
                "shadow": self.page.checkBox_shadow,
                "customImg": self.page.checkBox_customImg,
                "showGrid": self.page.checkBox_showGrid,
                "image": self.page.lineEdit_image,
                "kaleidoscope": self.page.checkBox_kaleidoscope,
                "sensitivity": self.page.spinBox_sensitivity,
            },
            colorWidgets={
                "color": self.page.pushButton_color,
            },
        )
        self.shiftButtons = (
            self.page.toolButton_up,
            self.page.toolButton_down,
            self.page.toolButton_left,
            self.page.toolButton_right,
        )

        def shiftFunc(i):
            def shift():
                self.shiftGrid(i)

            return shift

        shiftFuncs = [shiftFunc(i) for i in range(len(self.shiftButtons))]
        for i, widget in enumerate(self.shiftButtons):
            widget.clicked.connect(shiftFuncs[i])
        self.page.spinBox_scale.setValue(self.scale)
        self.page.spinBox_scale.valueChanged.connect(self.updateGridSize)

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

    def shiftGrid(self, d):
        action = ShiftGrid(self, d)
        self.parent.undoStack.push(action)

    def update(self):
        self.updateGridSize()

        # Hide/show widgets depending on state of "custom image" checkbox
        if self.page.checkBox_customImg.isChecked():
            self.page.label_color.setVisible(False)
            self.page.lineEdit_color.setVisible(False)
            self.page.pushButton_color.setVisible(False)
            self.page.label_shape.setVisible(False)
            self.page.comboBox_shapeType.setVisible(False)
            self.page.label_image.setVisible(True)
            self.page.lineEdit_image.setVisible(True)
            self.page.pushButton_pickImage.setVisible(True)
        else:
            self.page.label_color.setVisible(True)
            self.page.lineEdit_color.setVisible(True)
            self.page.pushButton_color.setVisible(True)
            self.page.label_shape.setVisible(True)
            self.page.comboBox_shapeType.setVisible(True)
            self.page.label_image.setVisible(False)
            self.page.lineEdit_image.setVisible(False)
            self.page.pushButton_pickImage.setVisible(False)

        # Disable audio sensitivity spinbox if not relevant
        if (
            self.page.comboBox_shapeType.currentIndex() < 4
            or self.page.checkBox_customImg.isChecked()
        ):
            self.page.spinBox_sensitivity.setEnabled(True)
        else:
            self.page.spinBox_sensitivity.setEnabled(False)

        # Disable arrow buttons to shift the grid if the grid is empty
        enabled = len(self.startingGrid) > 0
        for widget in self.shiftButtons:
            widget.setEnabled(enabled)

    def previewClickEvent(self, pos, size, button):
        pos = (
            math.ceil((pos[0] / size[0]) * self.gridWidth) - 1,
            math.ceil((pos[1] / size[1]) * self.gridHeight) - 1,
        )
        action = ClickGrid(self, pos, button)
        self.parent.undoStack.push(action)

    def updateGridSize(self):
        w, h = self.core.resolutions[-1].split("x")
        self.gridWidth = int(int(w) / self.scale)
        self.gridHeight = int(int(h) / self.scale)
        self.pxWidth = math.ceil(self.width / self.gridWidth)
        self.pxHeight = math.ceil(self.height / self.gridHeight)

    def previewRender(self):
        image = self.drawGrid(self.startingGrid, self.color)
        image = self.addKaleidoscopeEffect(image)
        if self.shadow:
            image = addShadow(image, 5.00, -2, 2)
        image = self.addGridLines(image)
        return image

    def preFrameRender(self, *args, **kwargs):
        super().preFrameRender(*args, **kwargs)
        self.tickGrids = {0: self.startingGrid}
        if self.sensitivity == 0:
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

    def properties(self):
        if self.customImg and (not self.image or not os.path.exists(self.image)):
            return ["error"]
        return ["pcm"] if self.sensitivity > 0 else []

    def error(self):
        return "No image selected to represent life."

    def frameRender(self, frameNo):
        tick = math.floor(frameNo / self.tickRate)

        # Compute grid evolution on this frame if it hasn't been computed yet
        if tick not in self.tickGrids:
            self.tickGrids[tick] = self.gridForTick(tick)
        grid = self.tickGrids[tick]

        # Delete old evolution data which we shouldn't need anymore
        if tick - 60 in self.tickGrids:
            del self.tickGrids[tick - 60]

        # Fade difference between previous and current grid
        previousGrid = self.tickGrids.get(tick - 1, set())
        newColor = self.color
        if not self.customImg:
            r, g, b = self.color
            decay = 255 / self.tickRate
            decayAmount = int(decay * (frameNo % self.tickRate))
            decayColor = (
                r,
                g,
                b,
                255 - decayAmount,
            )
            newColor = (r, g, b, min(255, decayAmount * 2))
            previousGridImage = self.drawGrid(
                previousGrid,
                decayColor,
                (
                    None
                    if (not self.customImg and self.shapeType > 3)
                    or self.sensitivity < 1
                    else self.spectrumArray[frameNo * self.sampleSize]
                ),
            )
        image = self.drawGrid(
            grid,
            newColor,
            (
                None
                if (not self.customImg and self.shapeType > 3) or self.sensitivity < 1
                else self.spectrumArray[frameNo * self.sampleSize]
            ),
            grid.intersection(previousGrid),
        )
        if not self.customImg:
            image = Image.alpha_composite(previousGridImage, image)
        image = self.addKaleidoscopeEffect(image)
        if self.shadow:
            image = addShadow(image, 5.00, -2, 2)
        image = self.addGridLines(image)
        return image

    def addGridLines(self, frame):
        if not self.showGrid:
            return frame

        drawer = ImageDraw.Draw(frame)
        w, h = scale(0.05, self.width, self.height, int)
        for x in range(self.pxWidth, self.width, self.pxWidth):
            drawer.rectangle(
                ((x, 0), (x + w, self.height)),
                fill=self.color,
            )
        for y in range(self.pxHeight, self.height, self.pxHeight):
            drawer.rectangle(
                ((0, y), (self.width, y + h)),
                fill=self.color,
            )
        return frame

    def addKaleidoscopeEffect(self, frame):
        if not self.kaleidoscope:
            return frame

        flippedImage = frame.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        frame.paste(flippedImage, (0, 0), mask=flippedImage)

        flippedImage = frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        frame.paste(flippedImage, (0, 0), mask=flippedImage)

        return frame

    def drawGrid(self, grid, color, spectrumData=None, didntChange=None):
        frame = BlankFrame(self.width, self.height)
        if didntChange is None:
            # this set would contain cell coords that did not change
            # between the previous grid tick and this one
            didntChange = set()

        def drawCustomImg():
            try:
                img = Image.open(self.image)
            except Exception:
                return
            img = img.resize(
                (
                    (self.pxWidth + audioMorphWidth),
                    (self.pxHeight + audioMorphHeight),
                ),
                Image.Resampling.LANCZOS,
            )
            frame.paste(
                img,
                box=(
                    (drawPtX - (audioMorphWidth * 2)),
                    (drawPtY - (audioMorphHeight * 2)),
                ),
            )

        def drawShape(x, y):
            drawer = ImageDraw.Draw(frame)
            rect = (
                (drawPtX - audioMorphWidth, drawPtY - audioMorphHeight),
                (
                    drawPtX + self.pxWidth + audioMorphWidth,
                    drawPtY + self.pxHeight + audioMorphHeight,
                ),
            )
            shape = self.page.comboBox_shapeType.currentText().lower()
            thisCellColor = color if (x, y) not in didntChange else (*color[:3], 255)

            # Rectangle
            if shape == "rectangle":
                drawer.rectangle(rect, fill=thisCellColor)

            # Elliptical
            elif shape == "elliptical":
                drawer.ellipse(rect, fill=thisCellColor)

            tenthX, tenthY = scale(10, self.pxWidth, self.pxHeight, int)
            smallerShape = (
                (
                    drawPtX + tenthX + int(tenthX / 4) - int(audioMorphWidth / 2),
                    drawPtY + tenthY + int(tenthY / 2) - int(audioMorphHeight / 2),
                ),
                (
                    drawPtX
                    + self.pxWidth
                    - tenthX
                    - int(tenthX / 4)
                    + int(audioMorphWidth / 2),
                    drawPtY
                    + self.pxHeight
                    - (tenthY + int(tenthY / 2))
                    + int(audioMorphHeight / 2),
                ),
            )
            outlineShape = (
                (
                    drawPtX + int(tenthX / 4) - audioMorphWidth,
                    drawPtY + int(tenthY / 2) - audioMorphHeight,
                ),
                (
                    drawPtX + self.pxWidth - int(tenthX / 4) + audioMorphWidth,
                    drawPtY + self.pxHeight - int(tenthY / 2) + audioMorphHeight,
                ),
            )
            # Circle
            if shape == "circle":
                drawer.ellipse(outlineShape, fill=thisCellColor)
                drawer.ellipse(smallerShape, fill=(0, 0, 0, 0))

            # Lilypad
            elif shape == "lilypad":
                drawer.pieslice(smallerShape, 290, 250, fill=thisCellColor)

            # Pie
            elif shape == "pie":
                drawer.pieslice(outlineShape, 35, 320, fill=thisCellColor)

            hX, hY = scale(50, self.pxWidth, self.pxHeight, int)  # halfline
            tX, tY = scale(33, self.pxWidth, self.pxHeight, int)  # thirdline
            qX, qY = scale(20, self.pxWidth, self.pxHeight, int)  # quarterline

            # Path
            if shape == "path":
                drawer.ellipse(rect, fill=thisCellColor)
                rects = {
                    direction: False
                    for direction in (
                        "up",
                        "down",
                        "left",
                        "right",
                    )
                }
                for cell in self.nearbyCoords(x, y):
                    if cell not in grid:
                        continue
                    if cell[0] == x:
                        if cell[1] < y:
                            rects["up"] = True
                        if cell[1] > y:
                            rects["down"] = True
                    if cell[1] == y:
                        if cell[0] < x:
                            rects["left"] = True
                        if cell[0] > x:
                            rects["right"] = True

                for direction, rect in rects.items():
                    if rect:
                        if direction == "up":
                            sect = (
                                (drawPtX, drawPtY),
                                (drawPtX + self.pxWidth, drawPtY + hY),
                            )
                        elif direction == "down":
                            sect = (
                                (drawPtX, drawPtY + hY),
                                (
                                    drawPtX + self.pxWidth,
                                    drawPtY + self.pxHeight,
                                ),
                            )
                        elif direction == "left":
                            sect = (
                                (drawPtX, drawPtY),
                                (drawPtX + hX, drawPtY + self.pxHeight),
                            )
                        elif direction == "right":
                            sect = (
                                (drawPtX + hX, drawPtY),
                                (
                                    drawPtX + self.pxWidth,
                                    drawPtY + self.pxHeight,
                                ),
                            )
                        drawer.rectangle(sect, fill=thisCellColor)

            # Duck
            elif shape == "duck":
                duckHead = (
                    (drawPtX + qX, drawPtY + qY),
                    (drawPtX + int(qX * 3), drawPtY + int(tY * 2)),
                )
                duckBeak = (
                    (drawPtX + hX, drawPtY + qY),
                    (drawPtX + self.pxWidth + qX, drawPtY + int(qY * 3)),
                )
                duckWing = ((drawPtX, drawPtY + hY), rect[1])
                duckBody = (
                    (drawPtX + int(qX / 4), drawPtY + int(qY * 3)),
                    (drawPtX + int(tX * 2), drawPtY + self.pxHeight),
                )
                drawer.ellipse(duckBody, fill=thisCellColor)
                drawer.ellipse(duckHead, fill=thisCellColor)
                drawer.pieslice(duckWing, 130, 200, fill=thisCellColor)
                drawer.pieslice(duckBeak, 145, 200, fill=thisCellColor)

            # Peace
            elif shape == "peace":
                line = (
                    (
                        drawPtX + hX - int(tenthX / 2),
                        drawPtY + int(tenthY / 2),
                    ),
                    (
                        drawPtX + hX + int(tenthX / 2),
                        drawPtY + self.pxHeight - int(tenthY / 2),
                    ),
                )
                drawer.ellipse(outlineShape, fill=thisCellColor)
                drawer.ellipse(smallerShape, fill=(0, 0, 0, 0))
                drawer.rectangle(line, fill=thisCellColor)

                def slantLine(difference):
                    return (
                        (drawPtX + difference),
                        (drawPtY + self.pxHeight - qY),
                    ), (
                        (drawPtX + hX),
                        (drawPtY + hY),
                    )

                drawer.line(slantLine(qX), fill=thisCellColor, width=tenthX)
                drawer.line(
                    slantLine(self.pxWidth - qX), fill=thisCellColor, width=tenthX
                )

        for x, y in grid:
            drawPtX = x * self.pxWidth
            if drawPtX > self.width or drawPtX + self.pxWidth < 0:
                continue
            drawPtY = y * self.pxHeight
            if drawPtY > self.height or drawPtY + self.pxHeight < 0:
                continue

            audioMorphWidth = (
                0 if spectrumData is None else int(spectrumData[(drawPtX % 63) * 4] / 4)
            )
            audioMorphHeight = (
                0 if spectrumData is None else int(spectrumData[(drawPtY % 63) * 4] / 4)
            )
            if self.customImg:
                drawCustomImg()
            else:
                drawShape(x, y)

        return frame

    def gridForTick(self, tick):
        """
        Given a tick number over 0, returns a new grid (a set of tuples).
        This must compute the previous ticks' grids if not already computed
        """
        if tick - 1 not in self.tickGrids:
            self.tickGrids[tick - 1] = self.gridForTick(tick - 1)

        lastGrid = self.tickGrids[tick - 1]

        def neighbours(x, y):
            return {cell for cell in self.nearbyCoords(x, y) if cell in lastGrid}

        newGrid = set()
        # Copy cells from the previous grid if they have 2 or 3 neighbouring cells
        # and if they are within the grid or its bleed area (off-canvas area)
        for x, y in lastGrid:
            if (
                -self.bleedSize > x > self.gridWidth + self.bleedSize
                or -self.bleedSize > y > self.gridHeight + self.bleedSize
            ):
                continue
            surrounding = len(neighbours(x, y))
            if surrounding == 2 or surrounding == 3:
                newGrid.add((x, y))

        # Find positions around living cells which must be checked for reproduction
        potentialNewCells = {
            coordTup
            for origin in lastGrid
            for coordTup in list(self.nearbyCoords(*origin))
        }
        # Check for reproduction
        for x, y in potentialNewCells:
            if (x, y) in newGrid:
                # Ignore non-empty cell
                continue
            surrounding = len(neighbours(x, y))
            if surrounding == 3:
                newGrid.add((x, y))

        return newGrid

    def savePreset(self):
        pr = super().savePreset()
        pr["GRID"] = sorted(self.startingGrid)
        return pr

    def loadPreset(self, pr, *args):
        self.startingGrid = set(pr["GRID"])
        if self.startingGrid:
            for widget in self.shiftButtons:
                widget.setEnabled(True)
        super().loadPreset(pr, *args)

    def nearbyCoords(self, x, y):
        yield x + 1, y + 1
        yield x + 1, y - 1
        yield x - 1, y + 1
        yield x - 1, y - 1
        yield x, y + 1
        yield x, y - 1
        yield x + 1, y
        yield x - 1, y


class ClickGrid(QUndoCommand):
    def __init__(self, comp, pos, button):
        super().__init__("click %s component #%s" % (comp.name, comp.compPos))
        self.comp = comp
        self.pos = [pos]
        if button == QtCore.Qt.MouseButton.RightButton:
            self.button = 2
        else:
            self.button = 1

    def id(self):
        return self.button

    def mergeWith(self, other):
        self.pos.extend(other.pos)
        return True

    def add(self):
        for pos in self.pos[:]:
            self.comp.startingGrid.add(pos)
        self.comp.update(auto=True)

    def remove(self):
        for pos in self.pos[:]:
            self.comp.startingGrid.discard(pos)
        self.comp.update(auto=True)

    def redo(self):
        if self.button == 1:  # Left-click
            self.add()
        elif self.button == 2:  # Right-click
            self.remove()

    def undo(self):
        if self.button == 1:  # Left-click
            self.remove()
        elif self.button == 2:  # Right-click
            self.add()


class ShiftGrid(QUndoCommand):
    def __init__(self, comp, direction):
        super().__init__("change %s component #%s" % (comp.name, comp.compPos))
        self.comp = comp
        self.direction = direction
        self.distance = 1

    def id(self):
        return self.direction

    def mergeWith(self, other):
        self.distance += other.distance
        return True

    def newGrid(self, Xchange, Ychange):
        return {(x + Xchange, y + Ychange) for x, y in self.comp.startingGrid}

    def redo(self):
        if self.direction == 0:
            newGrid = self.newGrid(0, -self.distance)
        elif self.direction == 1:
            newGrid = self.newGrid(0, self.distance)
        elif self.direction == 2:
            newGrid = self.newGrid(-self.distance, 0)
        elif self.direction == 3:
            newGrid = self.newGrid(self.distance, 0)
        self.comp.startingGrid = newGrid
        self.comp._sendUpdateSignal()

    def undo(self):
        if self.direction == 0:
            newGrid = self.newGrid(0, self.distance)
        elif self.direction == 1:
            newGrid = self.newGrid(0, -self.distance)
        elif self.direction == 2:
            newGrid = self.newGrid(self.distance, 0)
        elif self.direction == 3:
            newGrid = self.newGrid(-self.distance, 0)
        self.comp.startingGrid = newGrid
        self.comp._sendUpdateSignal()
