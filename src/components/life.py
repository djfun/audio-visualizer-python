from PyQt6 import QtGui, QtCore, QtWidgets
from PyQt6.QtGui import QUndoCommand
from PIL import Image, ImageDraw, ImageEnhance, ImageChops, ImageFilter
import os
import math
import logging


from ..component import Component
from ..toolkit.frame import BlankFrame, scale


log = logging.getLogger("AVP.Component.Life")


class Component(Component):
    name = "Conway's Game of Life"
    version = "1.0.0"

    def widget(self, *args):
        super().widget(*args)
        self.scale = 32
        self.updateGridSize()
        # The initial grid: a "Queen Bee Shuttle"
        # https://conwaylife.com/wiki/Queen_bee_shuttle
        self.startingGrid = set(
            [
                (3, 7),
                (3, 8),
                (4, 7),
                (4, 8),
                (8, 7),
                (9, 6),
                (9, 8),
                (10, 5),
                (10, 9),
                (11, 6),
                (11, 7),
                (11, 8),
                (12, 4),
                (12, 5),
                (12, 9),
                (12, 10),
                (23, 6),
                (23, 7),
                (24, 6),
                (24, 7),
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
        return self.drawGrid(self.startingGrid)

    def preFrameRender(self, *args, **kwargs):
        super().preFrameRender(*args, **kwargs)
        self.tickGrids = {0: self.startingGrid}

    def properties(self):
        if self.customImg and (not self.image or not os.path.exists(self.image)):
            return ["error"]
        return []

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
        return self.drawGrid(grid)

    def drawGrid(self, grid):
        frame = BlankFrame(self.width, self.height)

        def drawCustomImg():
            try:
                img = Image.open(self.image)
            except Exception:
                return
            img = img.resize((self.pxWidth, self.pxHeight), Image.ANTIALIAS)
            frame.paste(img, box=(drawPtX, drawPtY))

        def drawShape():
            drawer = ImageDraw.Draw(frame)
            rect = (
                (drawPtX, drawPtY),
                (drawPtX + self.pxWidth, drawPtY + self.pxHeight),
            )
            shape = self.page.comboBox_shapeType.currentText().lower()

            # Rectangle
            if shape == "rectangle":
                drawer.rectangle(rect, fill=self.color)

            # Elliptical
            elif shape == "elliptical":
                drawer.ellipse(rect, fill=self.color)

            tenthX, tenthY = scale(10, self.pxWidth, self.pxHeight, int)
            smallerShape = (
                (
                    drawPtX + tenthX + int(tenthX / 4),
                    drawPtY + tenthY + int(tenthY / 2),
                ),
                (
                    drawPtX + self.pxWidth - tenthX - int(tenthX / 4),
                    drawPtY + self.pxHeight - (tenthY + int(tenthY / 2)),
                ),
            )
            outlineShape = (
                (drawPtX + int(tenthX / 4), drawPtY + int(tenthY / 2)),
                (
                    drawPtX + self.pxWidth - int(tenthX / 4),
                    drawPtY + self.pxHeight - int(tenthY / 2),
                ),
            )
            # Circle
            if shape == "circle":
                drawer.ellipse(outlineShape, fill=self.color)
                drawer.ellipse(smallerShape, fill=(0, 0, 0, 0))

            # Lilypad
            elif shape == "lilypad":
                drawer.pieslice(smallerShape, 290, 250, fill=self.color)

            # Pie
            elif shape == "pie":
                drawer.pieslice(outlineShape, 35, 320, fill=self.color)

            hX, hY = scale(50, self.pxWidth, self.pxHeight, int)  # halfline
            tX, tY = scale(33, self.pxWidth, self.pxHeight, int)  # thirdline
            qX, qY = scale(20, self.pxWidth, self.pxHeight, int)  # quarterline

            # Path
            if shape == "path":
                drawer.ellipse(rect, fill=self.color)
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
                        drawer.rectangle(sect, fill=self.color)

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
                drawer.ellipse(duckBody, fill=self.color)
                drawer.ellipse(duckHead, fill=self.color)
                drawer.pieslice(duckWing, 130, 200, fill=self.color)
                drawer.pieslice(duckBeak, 145, 200, fill=self.color)

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
                drawer.ellipse(outlineShape, fill=self.color)
                drawer.ellipse(smallerShape, fill=(0, 0, 0, 0))
                drawer.rectangle(line, fill=self.color)

                def slantLine(difference):
                    return (
                        (drawPtX + difference),
                        (drawPtY + self.pxHeight - qY),
                    ), (
                        (drawPtX + hX),
                        (drawPtY + hY),
                    )

                drawer.line(slantLine(qX), fill=self.color, width=tenthX)
                drawer.line(slantLine(self.pxWidth - qX), fill=self.color, width=tenthX)

        for x, y in grid:
            drawPtX = x * self.pxWidth
            if drawPtX > self.width:
                continue
            drawPtY = y * self.pxHeight
            if drawPtY > self.height:
                continue

            if self.customImg:
                drawCustomImg()
            else:
                drawShape()

        if self.shadow:
            shadImg = ImageEnhance.Contrast(frame).enhance(0.0)
            shadImg = shadImg.filter(ImageFilter.GaussianBlur(5.00))
            shadImg = ImageChops.offset(shadImg, -2, 2)
            shadImg.paste(frame, box=(0, 0), mask=frame)
            frame = shadImg
        if self.showGrid:
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
