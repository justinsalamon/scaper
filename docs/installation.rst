.. _installation:

Installation instructions
=========================

Non-python dependencies
-----------------------
Scaper has one non-python dependency:
- FFmpeg: https://ffmpeg.org/

If you are installing Scaper on Windows, you will also need:
- SoX: http://sox.sourceforge.net/

If you are installing on Linux/macOS, the SoX dependency is taken care of via 
[SoxBindings](https://github.com/pseeth/soxbindings).

On macOS ffmpeg can be installed using `homebrew <https://brew.sh/>`_:

>>> brew install ffmpeg

On linux you can use your distribution's package manager, e.g. on Ubuntu (15.04 "Vivid Vervet" or newer):

>>> sudo apt-get install ffmpeg

NOTE: on earlier versions of Ubuntu `ffmpeg may point to a Libav binary <http://stackoverflow.com/a/9477756/2007700>`_
which is not the correct binary. If you are using anaconda, you can install the correct version by calling:

>>> conda install -c conda-forge ffmpeg

Otherwise, you can `obtain a static binary from the ffmpeg website <https://ffmpeg.org/download.html>`_.

On Windows you can use the provided installation binaries:

- SoX: https://sourceforge.net/projects/sox/files/sox/
- FFmpeg: https://ffmpeg.org/download.html#build-windows

Installing Scaper
-----------------
The simplest way to install ``scaper`` is by using ``pip``, which will also install the required dependencies if needed.
To install ``scaper`` using ``pip``, simply run

>>> pip install scaper

To install the latest version of scaper from source:

1. Clone or pull the lastest version:

>>> git clone git@github.com:justinsalamon/scaper.git

2. Install using pip to handle python dependencies:

>>> cd scaper
>>> pip install -e .
