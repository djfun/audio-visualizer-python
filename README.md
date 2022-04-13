audio-visualizer-python
=======================
**We need a good name that is not as generic as "audio-visualizer-python"!**

This is a little GUI tool which creates an audio visualization video from an input audio file. Different components can be added and layered to change the resulting video and add images, videos, gradients, text, etc. Encoding options can be changed with a variety of different output containers.

Projects can be created from the GUI and used in commandline mode for easy automation of video production. Create a template project named `template` with your typical visualizers and watermarks, and add text to the top layer from commandline:
`avp template -c 99 text "title=Episode 371" -i /this/weeks/audio.ogg -o out`

For more information use `avp --help` or for help with a particular component use `avp -c 0 componentName help`.

The program works on Linux, macOS, and Windows. If you encounter problems running it or have other bug reports or features that you wish to see implemented, please fork the project and submit a pull request and/or file an issue on this project.

Dependencies
------------
Python 3.10, FFmpeg 4.4.1, PyQt5 (Qt v5.15.3), Pillow-SIMD, NumPy

**Note:** Pillow may be used as a drop-in replacement for Pillow-SIMD if problems are encountered installing. However this will result in much slower video export times. For help installing Pillow-SIMD, see the [Pillow installation guide](http://pillow.readthedocs.io/en/3.1.x/installation.html).

Installation
------------
### Manual installation on Ubuntu 22.04
* Install ffmpeg: `sudo apt install ffmpeg`
* Install pip: `sudo apt install python3-pip`
* Install PyQt5: `sudo apt install python3-pyqt5`
* Install dependencies to compile Pillow-SIMD: `sudo apt install python3-dev libtiff5-dev libjpeg8-dev zlib1g-dev libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python-tk`
* Download audio-visualizer-python from this repository and run `pip3 install .` in this directory
* Run the program with `avp` or `python3 -m avpython`
* (Optional Note) If using a virtual environmennt, PyQt5 doesn't seem to work when installed from the setup.py. You can use `--system-site-packages --copies` to copy the system site-packages into your venv


### Manual installation on Windows
* **Warning:** [Compiling Pillow is difficult on Windows](http://pillow.readthedocs.io/en/3.1.x/installation.html#building-on-windows) and required for the best experience.
* Download and install Python 3.6 from [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/)
* Add Python to your system PATH (it will ask during the installation process).
* Brave treacherous valley of getting prerequisites to [compile Pillow on Windows](https://www.pypkg.com/pypi/pillow-simd/f/winbuild/README.md). This is necessary because binary builds for Pillow-SIMD are not available.
* **Alternative:** install Pillow instead of Pillow-SIMD, for which binaries *are* available. However this will result in much slower video export times.
* Open command prompt and run: `pip install pyqt5 numpy pillow-simd`
* Download and install ffmpeg from [https://www.ffmpeg.org/download.html](https://www.ffmpeg.org/download.html). You can use the static builds.
* Add ffmpeg to your system PATH, too. [How to edit the PATH on Windows.](https://www.java.com/en/download/help/path.xml)

Download audio-visualizer-python from this repository and run it from the command line with `python main.py`.

### Manual installation on macOS

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
pip3 install pillow
pip3 install numpy
```

Download audio-visualizer-python from this repository and run it with `python3 main.py`.

Example
-------
You can find an example video here:
[Youtube: A day in spring](https://www.youtube.com/watch?v=-M3jR1NuJHM)

License
-------
audio-visualizer-python is licensed under the MIT license.
