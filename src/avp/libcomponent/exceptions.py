import time
import sys
import logging

from ..toolkit import formatTraceback


log = logging.getLogger("AVP.ComponentHandler")


class ComponentError(RuntimeError):
    """Gives the MainWindow a traceback to display, and cancels the export."""

    prevErrors = []
    lastTime = time.time()

    def __init__(self, caller, name, msg=None):
        if msg is None and sys.exc_info()[0] is not None:
            msg = str(sys.exc_info()[1])
        else:
            msg = "Unknown error."
        log.error("ComponentError by %s's %s: %s" % (caller.name, name, msg))

        # Don't create multiple windows for quickly repeated messages
        if len(ComponentError.prevErrors) > 1:
            ComponentError.prevErrors.pop()
        ComponentError.prevErrors.insert(0, name)
        curTime = time.time()
        if (
            name in ComponentError.prevErrors[1:]
            and curTime - ComponentError.lastTime < 1.0
        ):
            return
        ComponentError.lastTime = time.time()

        if sys.exc_info()[0] is not None:
            string = "%s component (#%s): %s encountered %s %s: %s" % (
                caller.__class__.name,
                str(caller.compPos),
                name,
                (
                    "an"
                    if any(
                        [
                            sys.exc_info()[0].__name__.startswith(vowel)
                            for vowel in ("A", "I", "U", "O", "E")
                        ]
                    )
                    else "a"
                ),
                sys.exc_info()[0].__name__,
                str(sys.exc_info()[1]),
            )
            detail = formatTraceback(sys.exc_info()[2])
        else:
            string = name
            detail = "Attributes:\n%s" % (
                "\n".join([m for m in dir(caller) if not m.startswith("_")])
            )

        super().__init__(string)
        caller.lockError(string)
        caller._error.emit(string, detail)
