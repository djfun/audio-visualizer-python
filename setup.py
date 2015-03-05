from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need
# fine tuning.
buildOptions = dict(packages = [], excludes = [
  "apport",
  "apt",
  "ctypes",
  "curses",
  "distutils",
  "email",
  "html",
  "http",
  "json",
  "xmlrpc",
  "nose"
  ], include_files = ["main.ui"])

import sys
base = 'Win32GUI' if sys.platform=='win32' else None

executables = [
    Executable('main.py', base=base, targetName = 'audio-visualizer-python')
]

setup(name='audio-visualizer-python',
      version = '1.0',
      description = 'a little GUI tool to render visualization videos of audio files',
      options = dict(build_exe = buildOptions),
      executables = executables)
