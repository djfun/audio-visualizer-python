# audio-visualizer-python
**We need a good name that is not as generic as "audio-visualizer-python"!**

This is a little GUI tool which creates an audio visualization video from an input audio file. Different components can be added and layered to change the resulting video and add images, videos, gradients, text, etc. Encoding options can be changed with a variety of different output containers.

Projects can be created from the GUI and used in commandline mode for easy automation of video production. For more information use `avp --help` or for help with a particular component use `avp -c 0 componentName help`.

The program works on Linux, macOS, and Windows. If you encounter problems running it or have other bug reports or features that you wish to see implemented, please fork the project and submit a pull request and/or file an issue on this project. To gather extra information to help us debug the problem, run `avp --test` and include the text file it creates.


# Examples
## What the app creates
* **[YouTube: A day in spring](https://www.youtube.com/watch?v=-M3jR1NuJHM)**

## Graphical version demo
* [YouTube: Audio Visualizer demonstration](https://www.youtube.com/watch?v=EVt2ckQs1Yg)

## Commandline snippets
* Create a simple visualization: `avp -c 0 classic -i something.mp3 -o output.mp4`
* Create the same visualization but with split layout and more extreme fluctuations: `avp -c 0 classic layout=split scale=40 -i something.mp3 -o output.mp4`
* Create a template project named `template` with your typical visualizers and watermarks using the GUI, then add text to the top layer from commandline: `avp template -c 99 text "title=Episode 371" -i /this/weeks/audio.ogg -o output.mp4`


# Dependencies
* Python 3.10
* FFmpeg 4.4.1
* PyQt5 (Qt v5.15.3)
* Pillow
* NumPy
* Pytest


# Installation
* On any platform, you may wish to install the app within an isolated Python environment so it doesn't affect other Python packages on your system. An easy way to do this is by using [Pipx](https://pypi.org/project/pipx/), which works similarly to Pip but automatically handles isolation.
* If you have problems running the `avp` command, try using `python -m avp` instead. (Note: python is called python3 on some systems.)


## Manual installation on Ubuntu 22.04
* Install dependencies: `sudo apt install ffmpeg python3-pip python3-pyqt5`
* Download this repo and run `pip install .` in this directory (or use `pipx` for isolation)
* Run the program with `avp` or `python3 -m avp`


## Manual installation on Windows
* Install Python from the Windows Store
* Add Python to your system PATH (it should ask during the installation process)
* Download this repo (extract from zip if needed)
* Download and install [FFmpeg](https://www.ffmpeg.org/download.html). Use the GPL-licensed static builds.
* Add FFmpeg to the system PATH as well (program will then work anywhere)
  * Alternatively, copy ffmpeg.exe into the folder that you want to run the program within
* Open command prompt, `cd` into the repo directory, and run: `pip install .` (or use `pipx` for isolation)
* Now run `avp` or `python -m avp` from a command prompt window to start the app


## Manual installation on macOS
* **[Outdated]**: No one has updated these instructions for a while.
* Install [Homebrew](http://brew.sh/)
* Use the following commands to install the needed dependencies:
```
brew install python3
brew install ffmpeg --with-fdk-aac --with-ffplay --with-freetype --with-libass --with-libquvi --with-libvorbis --with-libvpx --with-opus --with-x265
brew install qt
brew install sip --with-python3
brew install pyqt --with-python3
pip3 install --upgrade pip
```
* Download this repository and install it using Pip: `pip3 install .` (or use `pipx` for isolation)
* Start the app with `avp` or `python3 -m avp`


# Faster Export Times
* [Pillow-SIMD](https://github.com/uploadcare/pillow-simd) may be used as a drop-in replacement for Pillow if you desire faster video export times, but it must be compiled from source. For help installing dependencies to compile Pillow-SIMD, see the [Pillow installation guide](http://pillow.readthedocs.io/en/3.1.x/installation.html).
* **Warning:** [Compiling from source is difficult on Windows](http://pillow.readthedocs.io/en/3.1.x/installation.html#building-on-windows).


# Keyboard Shortcuts
| Key Combo                 | Effect                                             |
| ------------------------- | -------------------------------------------------- |
| Ctrl+S                    | Save Current Project                               |
| Ctrl+A                    | Save Project As...                                 |
| Ctrl+O                    | Open Project                                       |
| Ctrl+N                    | New Project (prompts to save current project)      |
| Ctrl+Z                    | Undo                                               |
| Ctrl+Shift+Z _or_ Ctrl+Y  | Redo                                               |
| Ctrl+T _or_ Insert        | Add Component                                      |
| Ctrl+R _or_ Delete        | Remove Component                                   |
| Ctrl+Space                | Focus Component List                               |
| Ctrl+Shift+S              | Save Component Preset                              |
| Ctrl+Shift+C              | Remove Preset from Component                       |
| Ctrl+Up                   | Move Selected Component Up                         |
| Ctrl+Down                 | Move Selected Component Down                       |
| Ctrl+Home                 | Move Selected Component to Top                     |
| Ctrl+End                  | Move Selected Component to Bottom                  |
| Ctrl+Shift+U              | Open Undo History                                  |
| Ctrl+Shift+F              | Show FFmpeg Command                                |
| Ctrl+Alt+Shift+R          | Force redraw preview (must use `--debug`)          |
| Ctrl+Alt+Shift+A          | Dump MainWindow data into log (must use `--debug`) |


# License
Source code of audio-visualizer-python is licensed under the MIT license.

Some dependencies of this application are under the GPL license. When packaged with these dependencies, audio-visualizer-python may also be under the terms of this GPL license.