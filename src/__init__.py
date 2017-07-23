import sys
import os


if getattr(sys, 'frozen', False):
    # frozen
    wd = os.path.dirname(sys.executable)
else:
    # unfrozen
    wd = os.path.dirname(os.path.realpath(__file__))

# make relative imports work when using /src as a package
sys.path.insert(0, wd)
