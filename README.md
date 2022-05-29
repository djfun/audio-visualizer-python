audio-visualizer-python
=======================

This is a little GUI tool which creates an audio visualization video from an input audio.
You can also give it a background image and set a title text.

It works on Linux (Ubuntu 20.04) and Windows (Windows 11). It should also work on macOS. If you encounter problems running it, or have other bug reports or features that you wish to see implemented, please fork the project and make a pull request and/or file an issue on this project.

We also need a good name that is not as generic as "audio-visualizer-python"!

Dependencies
------------
You need Python 3, PyQt5, Pillow, NumPy and the program FFmpeg, which is used to read the audio and render the video.

Installation
------------
### Manual installation on Ubuntu 20.04
* Get all the python stuff: `sudo apt install python3 python3-pyqt5 python3-pil python3-numpy`
* Get FFmpeg: `sudo apt install ffmpeg`

Download audio-visualizer-python from this repository and run it with `python3 main.py`.

### Manual installation on Windows 11
* Download and install Python 3 from the Windows Store
* Download and install FFmpeg from [https://www.ffmpeg.org/download.html](https://www.ffmpeg.org/download.html). You can use the static builds.
* Add FFmpeg to your system PATH environment variable.
* Use pip to install dependencies: `pip install pyqt5 pillow numpy`

Download audio-visualizer-python from this repository and run it from the command line with `python.exe main.py`.

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
