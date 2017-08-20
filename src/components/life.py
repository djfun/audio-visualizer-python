from PyQt5 import QtGui, QtCore, QtWidgets
from PIL import Image, ImageDraw, ImageEnhance, ImageChops, ImageFilter
import os
import math

from component import Component
from toolkit.frame import BlankFrame, scale


class Component(Component):
    name = 'Conway\'s Game of Life'
    version = '1.0.0'

    def widget(self, *args):
        super().widget(*args)
        self.scale = 32
        self.updateGridSize()
        self.startingGrid = set()
        self.page.pushButton_pickImage.clicked.connect(self.pickImage)
        self.trackWidgets({
            'tickRate': self.page.spinBox_tickRate,
            'scale': self.page.spinBox_scale,
            'color': self.page.lineEdit_color,
            'shapeType': self.page.comboBox_shapeType,
            'shadow': self.page.checkBox_shadow,
            'customImg': self.page.checkBox_customImg,
            'showGrid': self.page.checkBox_showGrid,
            'image': self.page.lineEdit_image,
        }, colorWidgets={
            'color': self.page.pushButton_color,
        })
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
            self.page, "Choose Image", imgDir,
            "Image Files (%s)" % " ".join(self.core.imageFormats))
        if filename:
            self.settings.setValue("componentDir", os.path.dirname(filename))
            self.mergeUndo = False
            self.page.lineEdit_image.setText(filename)
            self.mergeUndo = True

    def shiftGrid(self, d):
        def newGrid(Xchange, Ychange):
            return {
                (x + Xchange, y + Ychange)
                for x, y in self.startingGrid
            }

        if d == 0:
            newGrid = newGrid(0, -1)
        elif d == 1:
            newGrid = newGrid(0, 1)
        elif d == 2:
            newGrid = newGrid(-1, 0)
        elif d == 3:
            newGrid = newGrid(1, 0)
        self.startingGrid = newGrid
        self._sendUpdateSignal()

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
        enabled = (len(self.startingGrid) > 0)
        for widget in self.shiftButtons:
            widget.setEnabled(enabled)
        super().update()

    def previewClickEvent(self, pos, size, button):
        pos = (
            math.ceil((pos[0] / size[0]) * self.gridWidth) - 1,
            math.ceil((pos[1] / size[1]) * self.gridHeight) - 1
        )
        if button == 1:
            self.startingGrid.add(pos)
        elif button == 2:
            self.startingGrid.discard(pos)

    def updateGridSize(self):
        w, h = self.core.resolutions[-1].split('x')
        self.gridWidth = int(int(w) / self.scale)
        self.gridHeight = int(int(h) / self.scale)
        self.pxWidth = math.ceil(self.width / self.gridWidth)
        self.pxHeight = math.ceil(self.height / self.gridHeight)

    def previewRender(self):
        return self.drawGrid(self.startingGrid)

    def preFrameRender(self, *args, **kwargs):
        super().preFrameRender(*args, **kwargs)
        self.progressBarSetText.emit("Computing evolution...")
        self.tickGrids = {0: self.startingGrid}
        tick = 0
        for frameNo in range(
                self.tickRate, self.audioArrayLen, self.sampleSize
                ):
            if self.parent.canceled:
                break
            if frameNo % self.tickRate == 0:
                tick += 1
                self.tickGrids[tick] = self.gridForTick(tick)

                # update progress bar
                progress = int(100*(frameNo/self.audioArrayLen))
                if progress >= 100:
                    progress = 100
                pStr = "Computing evolution: "+str(progress)+'%'
                self.progressBarSetText.emit(pStr)
                self.progressBarUpdate.emit(int(progress))

    def properties(self):
        if self.customImg and (
                not self.image or not os.path.exists(self.image)
                ):
            return ['error']
        return []

    def error(self):
        return "No image selected to represent life."

    def frameRender(self, frameNo):
        tick = math.floor(frameNo / self.tickRate)
        grid = self.tickGrids[tick]
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
                (drawPtX + self.pxWidth, drawPtY + self.pxHeight)
            )
            shape = self.page.comboBox_shapeType.currentText().lower()

            # Rectangle
            if shape == 'rectangle':
                drawer.rectangle(rect, fill=self.color)

            # Elliptical
            elif shape == 'elliptical':
                drawer.ellipse(rect, fill=self.color)

            tenthX, tenthY = scale(10, self.pxWidth, self.pxHeight, int)
            smallerShape = (
                (drawPtX + tenthX + int(tenthX / 4),
                    drawPtY + tenthY + int(tenthY / 2)),
                (drawPtX + self.pxWidth - tenthX - int(tenthX / 4),
                    drawPtY + self.pxHeight - (tenthY + int(tenthY / 2)))
            )
            outlineShape = (
                (drawPtX + int(tenthX / 4),
                    drawPtY + int(tenthY / 2)),
                (drawPtX + self.pxWidth - int(tenthX / 4),
                    drawPtY + self.pxHeight - int(tenthY / 2))
            )
            # Circle
            if shape == 'circle':
                drawer.ellipse(outlineShape, fill=self.color)
                drawer.ellipse(smallerShape, fill=(0, 0, 0, 0))

            # Lilypad
            elif shape == 'lilypad':
                drawer.pieslice(smallerShape, 290, 250, fill=self.color)

            # Pac-Man
            elif shape == 'pac-man':
                drawer.pieslice(outlineShape, 35, 320, fill=self.color)

            hX, hY = scale(50, self.pxWidth, self.pxHeight, int)  # halfline
            tX, tY = scale(33, self.pxWidth, self.pxHeight, int)  # thirdline
            qX, qY = scale(20, self.pxWidth, self.pxHeight, int)  # quarterline

            # Path
            if shape == 'path':
                drawer.ellipse(rect, fill=self.color)
                rects = {
                    direction: False
                    for direction in (
                        'up', 'down', 'left', 'right',
                    )
                }
                for cell in nearbyCoords(x, y):
                    if cell not in grid:
                        continue
                    if cell[0] == x:
                        if cell[1] < y:
                            rects['up'] = True
                        if cell[1] > y:
                            rects['down'] = True
                    if cell[1] == y:
                        if cell[0] < x:
                            rects['left'] = True
                        if cell[0] > x:
                            rects['right'] = True

                for direction, rect in rects.items():
                    if rect:
                        if direction == 'up':
                            sect = (
                                (drawPtX, drawPtY),
                                (drawPtX + self.pxWidth, drawPtY + hY)
                            )
                        elif direction == 'down':
                            sect = (
                                (drawPtX, drawPtY + hY),
                                (drawPtX + self.pxWidth,
                                    drawPtY + self.pxHeight)
                            )
                        elif direction == 'left':
                            sect = (
                                (drawPtX, drawPtY),
                                (drawPtX + hX,
                                    drawPtY + self.pxHeight)
                            )
                        elif direction == 'right':
                            sect = (
                                (drawPtX + hX, drawPtY),
                                (drawPtX + self.pxWidth,
                                    drawPtY + self.pxHeight)
                            )
                        drawer.rectangle(sect, fill=self.color)

            # Duck
            elif shape == 'duck':
                duckHead = (
                    (drawPtX + qX, drawPtY + qY),
                    (drawPtX + int(qX * 3), drawPtY + int(tY * 2))
                )
                duckBeak = (
                    (drawPtX + hX, drawPtY + qY),
                    (drawPtX + self.pxWidth + qX,
                        drawPtY + int(qY * 3))
                )
                duckWing = (
                    (drawPtX, drawPtY + hY),
                    rect[1]
                )
                duckBody = (
                    (drawPtX + int(qX / 4), drawPtY + int(qY * 3)),
                    (drawPtX + int(tX * 2), drawPtY + self.pxHeight)
                )
                drawer.ellipse(duckBody, fill=self.color)
                drawer.ellipse(duckHead, fill=self.color)
                drawer.pieslice(duckWing, 130, 200, fill=self.color)
                drawer.pieslice(duckBeak, 145, 200, fill=self.color)

            # Peace
            elif shape == 'peace':
                line = ((
                    drawPtX + hX - int(tenthX / 2), drawPtY + int(tenthY / 2)),
                    (drawPtX + hX + int(tenthX / 2),
                        drawPtY + self.pxHeight - int(tenthY / 2))
                )
                drawer.ellipse(outlineShape, fill=self.color)
                drawer.ellipse(smallerShape, fill=(0, 0, 0, 0))
                drawer.rectangle(line, fill=self.color)

                def slantLine(difference):
                    return (
                        (drawPtX + difference),
                        (drawPtY + self.pxHeight - qY)
                    ),
                    (
                        (drawPtX + hX),
                        (drawPtY + hY)
                    )

                drawer.line(
                    slantLine(qX),
                    fill=self.color,
                    width=tenthX
                )
                drawer.line(
                    slantLine(self.pxWidth - qX),
                    fill=self.color,
                    width=tenthX
                )

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
                    ((x, 0),
                        (x + w, self.height)),
                    fill=self.color,
                )
            for y in range(self.pxHeight, self.height, self.pxHeight):
                drawer.rectangle(
                    ((0, y),
                        (self.width, y + h)),
                    fill=self.color,
                )

        return frame

    def gridForTick(self, tick):
        '''Given a tick number over 0, returns a new grid set of tuples'''
        lastGrid = self.tickGrids[tick - 1]

        def neighbours(x, y):
            return {
                cell for cell in nearbyCoords(x, y)
                if cell in lastGrid
            }

        newGrid = set()
        for x, y in lastGrid:
            surrounding = len(neighbours(x, y))
            if surrounding == 2 or surrounding == 3:
                newGrid.add((x, y))
        potentialNewCells = {
            coordTup for origin in lastGrid
            for coordTup in list(nearbyCoords(*origin))
        }
        for x, y in potentialNewCells:
            if (x, y) in newGrid:
                continue
            surrounding = len(neighbours(x, y))
            if surrounding == 3:
                newGrid.add((x, y))

        return newGrid

    def savePreset(self):
        pr = super().savePreset()
        pr['GRID'] = sorted(self.startingGrid)
        return pr

    def loadPreset(self, pr, *args):
        self.startingGrid = set(pr['GRID'])
        if self.startingGrid:
            for widget in self.shiftButtons:
                widget.setEnabled(True)
        super().loadPreset(pr, *args)


def nearbyCoords(x, y):
    yield x + 1, y + 1
    yield x + 1, y - 1
    yield x - 1, y + 1
    yield x - 1, y - 1
    yield x, y + 1
    yield x, y - 1
    yield x + 1, y
    yield x - 1, y
