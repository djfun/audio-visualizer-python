audio-visualizer-python
=======================

This is a little GUI tool which creates an audio visualization video from an input audio file. Different components can be added and layered to change the resulting video and add images, videos, gradients, text, etc. The component setup can be saved as a Project and exporting can be automated using commandline options.

The program works on Linux (Ubuntu 16.04), Windows (Windows 7), and Mac OS X. If you encounter problems running it or have other bug reports or features that you wish to see implemented, please fork the project and send me a pull request and/or file an issue on this project.

I also need a good name that is not as generic as "audio-visualizer-python"!

Dependencies
------------
Python 3, PyQt5, pillow-simd, numpy, and ffmpeg 3.3

Installation
------------
### Manual installation on Ubuntu 16.04
* Install pip: `sudo apt-get install python3-pip`
* Install [prerequisites to compile Pillow](http://pillow.readthedocs.io/en/3.1.x/installation.html#building-on-linux):`sudo apt-get install python3-dev python3-setuptools libtiff5-dev libjpeg8-dev zlib1g-dev libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python-tk`
* Prerequisites on **Fedora**:`sudo dnf install python3-devel redhat-rpm-config libtiff-devel libjpeg-devel libzip-devel freetype-devel lcms2-devel libwebp-devel tcl-devel tk-devel`
* Install dependencies from PyPI: `sudo pip3 install pyqt5 numpy pillow-simd`
* Install `ffmpeg` from the [website](http://ffmpeg.org/) or from a PPA (e.g. [https://launchpad.net/~jonathonf/+archive/ubuntu/ffmpeg-3](https://launchpad.net/~jonathonf/+archive/ubuntu/ffmpeg-3)). NOTE: `ffmpeg` in the standard repos is too old (v2.8). Old versions and `avconv` may be used but full functionality is only guaranteed with `ffmpeg` 3.3 or higher.

Download audio-visualizer-python from this repository and run it with `python3 main.py`.

### Manual installation on Windows
* **Not Recommended.** [Compiling Pillow is difficult on Windows](http://pillow.readthedocs.io/en/3.1.x/installation.html#building-on-windows) and required for a manual installation.
* Download and install Python 3.6 from [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/)
* Add Python to your system PATH (it will ask during the installation process).
* Brave treacherous valley of getting prerequisites to [compile Pillow on Windows](https://www.pypkg.com/pypi/pillow-simd/f/winbuild/README.md). This is necessary because binary builds for Pillow-SIMD are not available.
* **Alternative:** install Pillow instead of Pillow-SIMD, for which binaries *are* available. However this will result in much slower video export times.
* Open command prompt and run: `pip install pyqt5 numpy pillow-simd`
* Download and install ffmpeg from [https://www.ffmpeg.org/download.html](https://www.ffmpeg.org/download.html). You can use the static builds.
* Add ffmpeg to your system PATH, too. [How to edit the PATH on Windows.](https://www.java.com/en/download/help/path.xml)

Download audio-visualizer-python from this repository and run it from the command line with `python main.py`.

### Manual installation on macOS [Outdated]

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
