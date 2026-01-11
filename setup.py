from setuptools import setup, find_packages
from importlib import import_module
from os import path
import re


def getTextFromFile(filename, fallback):
    try:
        with open(
            path.join(path.abspath(path.dirname(__file__)), filename), encoding="utf-8"
        ) as f:
            output = f.read()
    except Exception:
        output = fallback
    return output


PACKAGE_NAME = "avp"
SOURCE_DIRECTORY = "src"
SOURCE_PACKAGE_REGEX = re.compile(rf"^{SOURCE_DIRECTORY}")
PACKAGE_DESCRIPTION = "Create audio visualization videos from a GUI or commandline"


avp = import_module(SOURCE_DIRECTORY)
source_packages = find_packages(include=[SOURCE_DIRECTORY, f"{SOURCE_DIRECTORY}.*"])
proj_packages = [
    SOURCE_PACKAGE_REGEX.sub(PACKAGE_NAME, name) for name in source_packages
]


setup(
    name="audio_visualizer_python",
    version=avp.__version__,
    url="https://github.com/djfun/audio-visualizer-python",
    license="MIT",
    description=PACKAGE_DESCRIPTION,
    author=getTextFromFile("AUTHORS", "djfun, tassaron"),
    long_description=getTextFromFile("README.md", PACKAGE_DESCRIPTION),
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3 :: Only",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Video :: Non-Linear Editor",
    ],
    keywords=[
        "visualizer",
        "visualization",
        "commandline video",
        "video editor",
        "ffmpeg",
        "podcast",
    ],
    packages=proj_packages,
    package_dir={PACKAGE_NAME: SOURCE_DIRECTORY},
    include_package_data=True,
    install_requires=[
        "Pillow",
        "PyQt6",
        "numpy",
        "pytest",
        "pytest-qt",
    ],
    entry_points={
        "console_scripts": [f"avp = {PACKAGE_NAME}.__main__:main"],
    },
)
