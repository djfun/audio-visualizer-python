from PyQt4 import QtGui

class Component:
    def __str__(self):
        return self.__doc__

    def version(self):
        # change this number to identify new versions of a component
        return 1
        
    def preFrameRender(self, **kwargs):
        for var, value in kwargs.items():
            exec('self.%s = value' % var)

    def pickColor(self):
        color = QtGui.QColorDialog.getColor()
        if color.isValid():
            RGBstring = '%s,%s,%s' % (str(color.red()), str(color.green()), str(color.blue()))
            btnStyle = "QPushButton { background-color : %s; outline: none; }" % color.name()
            return RGBstring, btnStyle
        else:
            return None, None

    def RGBFromString(self, string):
       ''' turns an RGB string like "255, 255, 255" into a tuple '''
       try:
         tup = tuple([int(i) for i in string.split(',')])
         if len(tup) != 3:
            raise ValueError
         for i in tup:
            if i > 255 or i < 0:
               raise ValueError
         return tup
       except:
         return (255, 255, 255)

    '''
    ### Reference methods for creating a new component
    ### (Inherit from this class and define these)
    
    def widget(self, parent):
        self.parent = parent
        page = uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'example.ui'))
        # connect widgets signals
        self.page = page
        return page

    def update(self):
        # read widget values
        self.parent.drawPreview()
        
    def previewRender(self, previewWorker):
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        image = Image.new("RGBA", (width, height), (0,0,0,0))
        return image
        
    def frameRender(self, moduleNo, frameNo):
        width = int(self.worker.core.settings.value('outputWidth'))
        height = int(self.worker.core.settings.value('outputHeight'))
        image = Image.new("RGBA", (width, height), (0,0,0,0))
        return image

    def loadPreset(self, presetDict):
        # update widgets using a preset dict
        
    def savePreset(self):
        return {}
        
    def cancel(self):
        self.canceled = True

    def reset(self):
        self.canceled = False
    '''
