from cx_Freeze import setup, Executable
import sys
import os

from setup import __version__


deps = [os.path.join('src', p) for p in os.listdir('src') if p]
deps.append('ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg')

buildOptions = dict(
    excludes=[
        "apport",
        "apt",
        "curses",
        "distutils",
        "email",
        "html",
        "http",
        "xmlrpc",
        "nose",
        'tkinter',
    ],
    includes=[
        "encodings",
        "json",
        "filecmp",
        "numpy.core._methods",
        "numpy.lib.format",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "PyQt5.uic",
        "PIL.Image",
        "PIL.ImageQt",
        "PIL.ImageDraw",
        "PIL.ImageEnhance",
    ],
    include_files=deps,
)

base = 'Win32GUI' if sys.platform == 'win32' else None

executables = [
    Executable(
        'src/main.py',
        base=base,
        targetName='audio-visualizer-python'
    ),
]


setup(
    name='audio-visualizer-python',
    version=__version__,
    description='GUI tool to render visualization videos of audio files',
    options=dict(build_exe=buildOptions),
    executables=executables
)
