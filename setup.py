from cx_Freeze import setup, Executable
import sys

# Dependencies are automatically detected, but it might need
# fine tuning.

buildOptions = dict(
    packages=[],
    excludes=[
        "apport",
        "apt",
        "curses",
        "distutils",
        "email",
        "html",
        "http",
        "xmlrpc",
        "nose"
    ],
    include_files=[
        "mainwindow.ui",
        "presetmanager.ui",
        "background.png",
        "encoder-options.json",
        "components/"
    ],
    includes=[
        'numpy.core._methods',
        'numpy.lib.format'
    ]
)


base = 'Win32GUI' if sys.platform == 'win32' else None

executables = [
    Executable(
        'main.py',
        base=base,
        targetName='audio-visualizer-python'
    )
]


setup(
    name='audio-visualizer-python',
    version='1.0',
    description='GUI tool to render visualization videos of audio files',
    options=dict(build_exe=buildOptions),
    executables=executables
)
