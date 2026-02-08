import os
import logging
from PyQt6 import QtCore

from .exceptions import ComponentError
from ..toolkit import connectWidget
from ..toolkit.frame import BlankFrame

log = logging.getLogger("AVP.ComponentHandler")


class ComponentMetaclass(type(QtCore.QObject)):
    """
    Checks the validity of each Component class and mutates some attrs.
    E.g., takes only major version from version string & decorates methods
    """

    def initializationWrapper(func):
        def initializationWrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception:
                try:
                    raise ComponentError(self, "initialization process")
                except ComponentError:
                    return

        return initializationWrapper

    def renderWrapper(func):
        def renderWrapper(self, *args, **kwargs):
            try:
                log.verbose(
                    "### %s #%s renders a preview frame ###",
                    self.__class__.name,
                    str(self.compPos),
                )
                return func(self, *args, **kwargs)
            except Exception as e:
                try:
                    if e.__class__.__name__.startswith("Component"):
                        raise
                    else:
                        raise ComponentError(self, "renderer")
                except ComponentError:
                    return BlankFrame()

        return renderWrapper

    def commandWrapper(func):
        """Intercepts the command() method to check for global args"""

        def commandWrapper(self, arg):
            if arg.startswith("preset="):
                _, preset = arg.split("=", 1)
                path = os.path.join(self.core.getPresetDir(self), preset)
                if not os.path.exists(path):
                    print('Couldn\'t locate preset "%s"' % preset)
                    quit(1)
                else:
                    print('Opening "%s" preset on layer %s' % (preset, self.compPos))
                    self.core.openPreset(path, self.compPos, preset)
                    # Don't call the component's command() method
                    return
            else:
                return func(self, arg)

        return commandWrapper

    def propertiesWrapper(func):
        """Intercepts the usual properties if the properties are locked."""

        def propertiesWrapper(self):
            if self._lockedProperties is not None:
                return self._lockedProperties
            else:
                try:
                    return func(self)
                except Exception:
                    try:
                        raise ComponentError(self, "properties")
                    except ComponentError:
                        return []

        return propertiesWrapper

    def errorWrapper(func):
        """Intercepts the usual error message if it is locked."""

        def errorWrapper(self):
            if self._lockedError is not None:
                return self._lockedError
            else:
                return func(self)

        return errorWrapper

    def loadPresetWrapper(func):
        """Wraps loadPreset to handle the self.openingPreset boolean"""

        class openingPreset:
            def __init__(self, comp):
                self.comp = comp

            def __enter__(self):
                self.comp.openingPreset = True

            def __exit__(self, *args):
                self.comp.openingPreset = False

        def presetWrapper(self, *args):
            with openingPreset(self):
                try:
                    return func(self, *args)
                except Exception:
                    try:
                        raise ComponentError(self, "preset loader")
                    except ComponentError:
                        return

        return presetWrapper

    def updateWrapper(func):
        """
        Calls _preUpdate before every subclass update().
        Afterwards, for non-user updates, calls _autoUpdate().
        For undoable updates triggered by the user, calls _userUpdate()
        """

        class wrap:
            def __init__(self, comp, auto):
                self.comp = comp
                self.auto = auto

            def __enter__(self):
                self.comp._preUpdate()

            def __exit__(self, *args):
                if (
                    self.auto
                    or self.comp.openingPreset
                    or not hasattr(self.comp.parent, "undoStack")
                ):
                    log.verbose("Automatic update")
                    self.comp._autoUpdate()
                else:
                    log.verbose("User update")
                    self.comp._userUpdate()

        def updateWrapper(self, **kwargs):
            auto = kwargs["auto"] if "auto" in kwargs else False
            with wrap(self, auto):
                try:
                    return func(self)
                except Exception:
                    try:
                        raise ComponentError(self, "update method")
                    except ComponentError:
                        return

        return updateWrapper

    def widgetWrapper(func):
        """Connects all widgets to update method after the subclass's method"""

        class wrap:
            def __init__(self, comp):
                self.comp = comp

            def __enter__(self):
                pass

            def __exit__(self, *args):
                for widgetList in self.comp._allWidgets.values():
                    for widget in widgetList:
                        log.verbose("Connecting %s", str(widget.__class__.__name__))
                        connectWidget(widget, self.comp.update)

        def widgetWrapper(self, *args, **kwargs):
            auto = kwargs["auto"] if "auto" in kwargs else False
            with wrap(self):
                try:
                    return func(self, *args, **kwargs)
                except Exception:
                    try:
                        raise ComponentError(self, "widget creation")
                    except ComponentError:
                        return

        return widgetWrapper

    def __new__(cls, name, parents, attrs):
        if "ui" not in attrs:
            # Use module name as ui filename by default
            attrs["ui"] = (
                "%s.ui" % os.path.splitext(attrs["__module__"].split(".")[-1])[0]
            )

        decorate = (
            "names",  # Class methods
            "error",
            "audio",
            "properties",  # Properties
            "preFrameRender",
            "previewRender",
            "loadPreset",
            "command",
            "update",
            "widget",
        )

        # Auto-decorate methods
        for key in decorate:
            if key not in attrs:
                continue
            if key in ("names"):
                attrs[key] = classmethod(attrs[key])
            elif key in ("audio"):
                attrs[key] = property(attrs[key])
            elif key == "command":
                attrs[key] = cls.commandWrapper(attrs[key])
            elif key == "previewRender":
                attrs[key] = cls.renderWrapper(attrs[key])
            elif key == "preFrameRender":
                attrs[key] = cls.initializationWrapper(attrs[key])
            elif key == "properties":
                attrs[key] = cls.propertiesWrapper(attrs[key])
            elif key == "error":
                attrs[key] = cls.errorWrapper(attrs[key])
            elif key == "loadPreset":
                attrs[key] = cls.loadPresetWrapper(attrs[key])
            elif key == "update":
                attrs[key] = cls.updateWrapper(attrs[key])
            elif key == "widget" and parents[0] != QtCore.QObject:
                attrs[key] = cls.widgetWrapper(attrs[key])

        # Turn version string into a number
        try:
            if "version" not in attrs:
                log.error(
                    "No version attribute in %s. Defaulting to 1",
                    attrs["name"],
                )
                attrs["version"] = 1
            else:
                attrs["version"] = int(attrs["version"].split(".")[0])
        except ValueError:
            log.critical(
                "%s component has an invalid version string:\n%s",
                attrs["name"],
                str(attrs["version"]),
            )
        except KeyError:
            log.critical("%s component has no version string.", attrs["name"])
        else:
            return super().__new__(cls, name, parents, attrs)
        quit(1)
