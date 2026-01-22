# Audio Visualizer Python

**We need a good name that is not as generic as "audio-visualizer-python"!**

This is a little GUI tool which creates an audio visualization video from an input audio file. Different components can be added and layered to change the resulting video and add images, videos, gradients, text, etc. Encoding options can be changed with a variety of different output containers.

The program works on **Linux**, **macOS**, and **Windows**. If you encounter problems running it or have other bug reports or features that you wish to see implemented, please fork the project and submit a pull request and/or file an [issue](https://github.com/djfun/audio-visualizer-python/issues) on this project.

## Screenshots & Videos

[![Screenshot of AVP running on Windows](/screenshot.png?raw=true)](https://tassaron.com/img/avp/screenshot-v2.0.0.png)

### A video created by this app

- **[YouTube: A day in spring](https://www.youtube.com/watch?v=-M3jR1NuJHM)** 🎥

### Video demonstration of the app features

- [YouTube: Audio Visualizer Python v2.0.0 demonstration](https://www.youtube.com/watch?v=EVt2ckQs1Yg) 🎥

## Installation on Linux

### System dependencies

- Install FFmpeg:
    - On Ubuntu: `sudo apt install ffmpeg`
    - On Arch: `sudo pacman -S ffmpeg`
- If using X11 (Ubuntu 24.04 default):
    - `sudo apt install libxcb-cursor0`

### Using pipx

- **This is a good method if you just want to use the program**
- Install `pipx` tool if you don't have it:
    - On Ubuntu: `sudo apt install pipx`
    - On Arch: `sudo pacman -S python-pipx`
- Run `pipx ensurepath` then close and reopen the terminal
- Install latest stable version: `pipx install audio-visualizer-python`
- Run this program with `avp` or `python -m avp` from terminal

### Using a Python virtual environment

- **This is a good method if you want to edit the code**
- Make a virtual environment: `python -m venv .venv`
- Activate it: `source .venv/bin/activate`
- Install uv: `pip install uv`
- Install this program: `uv sync` in this directory
- Run program with `avp` or `python -m avp`

## Installation on Windows

- Install Python from the Windows Store
- Add Python to your system PATH (it should ask during the installation process)
    - [PATH](<https://en.wikipedia.org/wiki/PATH_(variable)>) is where your computer looks for programs
- Download and install [FFmpeg](https://www.ffmpeg.org/download.html). Use the GPL-licensed static builds.
- Add FFmpeg to the system PATH as well (program will then work anywhere)
    - Alternatively, copy ffmpeg.exe into the folder that you want to run the program within
- Open command prompt and run `pip install audio-visualizer-python`
- Now run `avp` or `python -m avp` from a command prompt window to start the app

## Installation on macOS

- We need help writing instructions for macOS, but the program should work in theory.

## [Keyboard Shortcuts](https://github.com/djfun/audio-visualizer-python/wiki/Keyboard-Shortcuts)

| Key Combo                | Effect                                        |
| ------------------------ | --------------------------------------------- |
| Ctrl+S                   | Save Current Project                          |
| Ctrl+A                   | Save Project As...                            |
| Ctrl+O                   | Open Project                                  |
| Ctrl+N                   | New Project (prompts to save current project) |
| Ctrl+Z                   | Undo                                          |
| Ctrl+Shift+Z _or_ Ctrl+Y | Redo                                          |
| Ctrl+T _or_ Insert       | Add Component                                 |
| Ctrl+R _or_ Delete       | Remove Component                              |
| Ctrl+Space               | Focus Component List                          |
| Ctrl+Shift+S             | Save Component Preset                         |
| Ctrl+Shift+C             | Remove Preset from Component                  |
| Ctrl+Up                  | Move Selected Component Up                    |
| Ctrl+Down                | Move Selected Component Down                  |
| Ctrl+Home                | Move Selected Component to Top                |
| Ctrl+End                 | Move Selected Component to Bottom             |
| Ctrl+Shift+U             | Open Undo History                             |
| Ctrl+Shift+F             | Show FFmpeg Command                           |

## Using Commandline Interface

Projects can be created with the GUI then loaded from the commandline for easy automation of video production. Some components have commandline options for extra customization, and you can save "presets" with settings to load if the commandline option doesn't exist.

### Example Command

- Create a video with a grey "classic visualizer", background image, and text:
    - `avp -c 0 image path=src/tests/data/test.jpg -c 1 classic color=180,180,180 -c 2 text "title=Episode 371" -i src/tests/data/test.ogg -o output.mp4`
- [See more about commandline mode in the wiki!](https://github.com/djfun/audio-visualizer-python/wiki/Commandline-Mode)

## Developer Information

### Dependencies

- Python 3.12 or higher
- FFmpeg 4.4.1 or higher
- PyQt6 6.10.2
- Pillow 12.1.0
- NumPy 2.4.1

### Running Automatic Tests
Run unit and integration tests with `pytest`.
  * First you will need to install with `pip install pytest pytest-qt`
  * You may omit the slowest test with `pytest -k "not commandline_export"`

### Installing from TestPyPI
Because some dependencies (namely numpy) are not always on TestPyPI, you must specify when installing that these dependencies should come from the real PyPI.
* `pip install -i https://test.pypi.org/simple/ audio-visualizer-python==x.x.x --extra-index-url https://pypi.org/simple numpy`

### Getting Faster Export Times

- [Pillow-SIMD](https://github.com/uploadcare/pillow-simd) may be used as a drop-in replacement for Pillow if you desire faster video export times, but it must be compiled from source. For help installing dependencies to compile Pillow-SIMD, see the [Pillow installation guide](https://pillow.readthedocs.io/en/stable/installation/building-from-source.html).

### Developing a New Component

- Information for developing a component is in our wiki: [How a Component Works](https://github.com/djfun/audio-visualizer-python/wiki/How-a-Component-Works)
- File an issue on GitHub if you need help fitting your visualizer into our component system; we would be happy to collaborate

## License

Source code of audio-visualizer-python is licensed under the MIT license.

Some dependencies of this application are under the GPL license. When packaged with these dependencies, audio-visualizer-python may also be under the terms of this GPL license.
