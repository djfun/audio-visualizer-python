import sys
import os


__version__ = "2.3.0"


if getattr(sys, "frozen", False):
    # frozen
    wd = os.path.dirname(sys.executable)
else:
    # unfrozen
    wd = os.path.dirname(os.path.realpath(__file__))
