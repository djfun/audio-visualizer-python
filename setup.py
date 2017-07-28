from setuptools import setup
import os


__version__ = '2.0.0.rc2'


def package_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join('..', path, filename))
    return paths


setup(
    name='audio_visualizer_python',
    version=__version__,
    url='https://github.com/djfun/audio-visualizer-python/tree/feature-newgui',
    license='MIT',
    description='Create audio visualization videos from a GUI or commandline',
    long_description="Create customized audio visualization videos and save "
        "them as Projects to continue editing later. Different components can "
        "be added and layered to add visualizers, images, videos, gradients, "
        "text, etc. Use Projects created in the GUI with commandline mode to "
        "automate your video production workflow without any complex syntax.",
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Multimedia :: Video :: Non-Linear Editor',
    ],
    keywords=[
        'visualizer', 'visualization', 'commandline video',
        'video editor', 'ffmpeg', 'podcast'
    ],
    packages=[
        'avpython',
        'avpython.toolkit',
        'avpython.components'
    ],
    package_dir={'avpython': 'src'},
    package_data={
        'avpython': package_files('src'),
    },
    install_requires=['Pillow-SIMD', 'PyQt5', 'numpy'],
    entry_points={
        'gui_scripts': [
            'avp = avpython.main:main'
        ],
    }
)
