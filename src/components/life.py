from PyQt5 import QtGui, QtCore, QtWidgets
from PIL import ImageDraw, ImageEnhance, ImageChops, ImageFilter
import os
import math

from component import Component
from toolkit.frame import BlankFrame, FramePainter


class Component(Component):
    name = 'Conway\'s Game of Life'
    version = '1.0.0a'

    def widget(self, *args):
        super().widget(*args)
        self.scale = 32
        self.updateGridSize()
        self.startingGrid = {}
        self.trackWidgets({
            'tickRate': self.page.spinBox_tickRate,
            'scale': self.page.spinBox_scale,
            'color': self.page.lineEdit_color,
            'shapeType': self.page.comboBox_shapeType,
            'shadow': self.page.checkBox_shadow,
        }, colorWidgets={
            'color': self.page.pushButton_color,
        })
        self.page.spinBox_scale.setValue(self.scale)

    def update(self):
        self.updateGridSize()
        super().update()

    def previewClickEvent(self, pos, size, button):
        pos = (
            math.ceil((pos[0] / size[0]) * self.gridWidth) - 1,
            math.ceil((pos[1] / size[1]) * self.gridHeight) - 1
        )
        if button == 1:
            self.startingGrid[pos] = True
        elif button == 2 and pos in self.startingGrid:
            self.startingGrid.pop(pos)

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
                self.tickRate, len(self.completeAudioArray), self.sampleSize
                ):
            if frameNo % self.tickRate == 0:
                tick += 1
                self.tickGrids[tick] = self.gridForTick(tick)

                # update progress bar
                progress = int(100*(frameNo/len(self.completeAudioArray)))
                if progress >= 100:
                    progress = 100
                pStr = "Computing evolution: "+str(progress)+'%'
                self.progressBarSetText.emit(pStr)
                self.progressBarUpdate.emit(int(progress))

    def frameRender(self, frameNo):
        tick = math.floor(frameNo / self.tickRate)
        grid = self.tickGrids[tick]
        return self.drawGrid(grid)

    def drawGrid(self, grid):
        frame = BlankFrame(self.width, self.height)
        drawer = ImageDraw.Draw(frame)

        for x, y in grid:
            drawPtX = x * self.pxWidth
            drawPtY = y * self.pxHeight
            rect = (
                (drawPtX, drawPtY),
                (drawPtX + self.pxWidth, drawPtY + self.pxHeight)
            )
            if self.shapeType == 0:
                drawer.rectangle(rect, fill=self.color)
            elif self.shapeType == 1:
                drawer.ellipse(rect, fill=self.color)
            elif self.shapeType == 2:
                drawer.pieslice(rect, 290, 250, fill=self.color)
            elif self.shapeType == 3:
                drawer.pieslice(rect, 20, 340, fill=self.color)

        if self.shadow:
            shadImg = ImageEnhance.Contrast(frame).enhance(0.0)
            shadImg = shadImg.filter(ImageFilter.GaussianBlur(5.00))
            shadImg = ImageChops.offset(shadImg, -2, 2)
            shadImg.paste(frame, box=(0, 0), mask=frame)
            frame = shadImg
        return frame

    def gridForTick(self, tick):
        '''Given a tick number over 0, returns a new grid dict of tuples'''
        lastGrid = self.tickGrids[tick - 1]

        def nearbyCoords(x, y):
            yield x + 1, y + 1
            yield x + 1, y - 1
            yield x - 1, y + 1
            yield x - 1, y - 1
            yield x, y + 1
            yield x, y - 1
            yield x + 1, y
            yield x - 1, y

        def neighbours(x, y):
            nearbyCells = [
                lastGrid.get(cell) for cell in nearbyCoords(x, y)
            ]
            return [
                nearbyCell for nearbyCell in nearbyCells
                if nearbyCell is not None
            ]

        newGrid = {}
        for x, y in lastGrid:
            surrounding = len(neighbours(x, y))
            if surrounding == 2 or surrounding == 3:
                newGrid[(x, y)] = True
        potentialNewCells = set([
            coordTup for origin in lastGrid
            for coordTup in list(nearbyCoords(*origin))
        ])
        for x, y in potentialNewCells:
            if (x, y) in newGrid:
                continue
            surrounding = len(neighbours(x, y))
            if surrounding == 3:
                newGrid[(x, y)] = True

        return newGrid

    def savePreset(self):
        pr = super().savePreset()
        pr['GRID'] = self.startingGrid
        return pr

    def loadPreset(self, pr, *args):
        super().loadPreset(pr, *args)
        self.startingGrid = pr['GRID']
