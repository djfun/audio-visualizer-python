+from setuptools import setup, find_packages
  		  
 -# Dependencies are automatically detected, but it might need		 +setup(name='audio_visualizer_python',
 -# fine tuning.		 +      version='1.0',
 -buildOptions = dict(packages = [], excludes = [		 +      description='a little GUI tool to render visualization \
 -  "apport",		 +                   videos of audio files',
 -  "apt",		 +      license='MIT',
 -  "ctypes",		 +      url='https://github.com/djfun/audio-visualizer-python',
 -  "curses",		 +      packages=find_packages(),
 -  "distutils",		 +      package_data={
 -  "email",		 +          'src': ['*'],
 -  "html",		 +      },
 -  "http",		 +      install_requires=['pillow-simd', 'numpy', ''],
 -  "json",		 +      entry_points={
 -  "xmlrpc",		 +          'gui_scripts': [
 -  "nose"		 +              'audio-visualizer-python = avpython.main:main'
 -  ], include_files = ["main.ui"])		 +          ]
 -		 +      }
 -import sys		 +      )