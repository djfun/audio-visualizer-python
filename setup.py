from setuptools import setup
import os


def package_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join('..', path, filename))
    return paths


setup(
    name='audio_visualizer_python',
    version='2.0.0',
    description='A little GUI tool to create audio visualization " \
        "videos out of audio files',
    license='MIT',
    url='https://github.com/djfun/audio-visualizer-python',
    packages=[
        'avpython',
        'avpython.components'
    ],
    package_dir={'avpython': 'src'},
    package_data={
        'avpython': package_files('src'),
    },
    install_requires=['olefile', 'Pillow-SIMD', 'PyQt5', 'numpy'],
    entry_points={
        'gui_scripts': [
            'avp = avpython.main:main'
        ],
    }
)
