audio-visualizer-python
=======================

This is a little GUI tool which creates an audio visualization video from an input audio.
You can also give it a background image and set a title text.

I have tested the program on Linux (Ubuntu 16.04) and Windows (Windows 7), it should also work on Mac OS X. If you encounter problems
running it or have other bug reports or features, that you wish to see implemented, please fork the project and send me a pull request and/or file an issue on this project.

I also need a good name that is not as generic as "audio-visualizer-python"!

Dependencies
------------
You need Python 3, PyQt4, PIL (or Pillow), numpy and the program ffmpeg, which is used to read the audio and render the video.

Installation
------------
### Manual installation on Ubuntu
* Get all the python stuff: `sudo apt install python3 python3-pyqt4 python3-pil python3-numpy`
* If you have PyQt5 installed, get pillow (at least version 3.3.0) from pip: `apt install python3-pip; pip3 install pillow`
* Get ffmpeg/avconv:
You can either use `avconv` from the standard repositories (package `libav-tools`) or get `ffmpeg` from the [website](http://ffmpeg.org/) or from a PPA (e.g. [https://launchpad.net/~jon-severinsson/+archive/ubuntu/ffmpeg](https://launchpad.net/~jon-severinsson/+archive/ubuntu/ffmpeg). The program does automatically detect if you don't have the ffmpeg binary and tries to use avconv instead.

Download audio-visualizer-python from this repository and run it with `python3 main.py`.

### Manual installation on Windows
* Download and install Python 3.4 from [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/)
* Download and install PyQt4 for Python 3.4 and Qt4 from [http://www.riverbankcomputing.co.uk/software/pyqt/download](http://www.riverbankcomputing.co.uk/software/pyqt/download)
* Download and install numpy from [http://www.scipy.org/scipylib/download.html](http://www.scipy.org/scipylib/download.html). There is an installer available, make sure to get the one for Python 3.4
* Download and install Pillow from [https://pypi.python.org/pypi/Pillow/3.3.0](https://pypi.python.org/pypi/Pillow/3.3.0)
* Download and install ffmpeg from [https://www.ffmpeg.org/download.html](https://www.ffmpeg.org/download.html). You can use the static builds.
* Add ffmpeg to your system PATH environment variable.

Download audio-visualizer-python from this repository and run it from the command line with `C:\Python34\python.exe main.py`.

### Manual installation on macOS

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
