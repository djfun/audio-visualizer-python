class Core:
    '''A very complicated class for tracking settings'''


def init(settings):
    global Core
    for classvar, val in settings.items():
        setattr(Core, classvar, val)


def cancel():
    global Core
    Core.canceled = True


def reset():
    global Core
    Core.canceled = False
