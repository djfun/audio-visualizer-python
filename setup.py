from setuptools import setup, find_packages

setup(name='audio_visualizer_python',
      version='1.0',
      description='a little GUI tool to render visualization \
                   videos of audio files',
      license='MIT',
      url='https://github.com/djfun/audio-visualizer-python',
      packages=find_packages(),
      package_data={
          'avpython': ['main.ui'],
      },
      install_requires=['pillow', 'numpy'],
      entry_points={
          'gui_scripts': [
              'audio-visualizer-python = avpython.main:main'
          ]
      }
      )
