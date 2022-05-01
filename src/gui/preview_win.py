from PyQt5 import QtCore, QtGui, QtWidgets
import logging

log = logging.getLogger('AVP.Gui.PreviewWindow')


class PreviewWindow(QtWidgets.QLabel):
    '''
        Paints the preview QLabel in MainWindow and maintains the aspect ratio
        when the window is resized.
    '''
    def __init__(self, parent, img):
        super().__init__()
        self.parent = parent
        self.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        self.pixmap = QtGui.QPixmap(img)

    def paintEvent(self, event):
        size = self.size()
        painter = QtGui.QPainter(self)
        point = QtCore.QPoint(0, 0)
        scaledPix = self.pixmap.scaled(
            size,
            QtCore.Qt.KeepAspectRatio,
            transformMode=QtCore.Qt.SmoothTransformation)

        # start painting the label from left upper corner
        point.setX(int((size.width() - scaledPix.width())/2))
        point.setY(int((size.height() - scaledPix.height())/2))
        painter.drawPixmap(point, scaledPix)

    def changePixmap(self, img):
        self.pixmap = QtGui.QPixmap(img)
        self.repaint()

    def mousePressEvent(self, event):
        if self.parent.encoding:
            return

        i = self.parent.listWidget_componentList.currentRow()
        if i >= 0:
            component = self.parent.core.selectedComponents[i]
            if not hasattr(component, 'previewClickEvent'):
                return
            pos = (event.x(), event.y())
            size = (self.width(), self.height())
            butt = event.button()
            log.info('Click event for #%s: %s button %s' % (
                i, pos, butt))
            component.previewClickEvent(
                pos, size, butt
            )

    @QtCore.pyqtSlot(str)
    def threadError(self, msg):
        self.parent.showMessage(
            msg=msg,
            icon='Critical',
            parent=self
        )
        log.info('%', repr(self.parent))
