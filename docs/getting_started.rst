Getting Started
===============

Installation
------------

Install morphic using `uv <https://docs.astral.sh/uv/>`_:

.. code-block:: bash

   uv sync --dev

Or with pip:

.. code-block:: bash

   pip install -e .

Quick Start
-----------

Launch the web interface:

.. code-block:: bash

   morphic

This opens a tabbed web UI on ``http://127.0.0.1:8000`` with two modules:

**Converter tab**
   Scan folders for media files and batch-convert between formats.
   Supports 22 image formats and 21 video formats.

**Dupfinder tab**
   Find duplicate images and videos using perceptual hashing.
   Supports GPU acceleration (CUDA, ROCm, OpenCL) when available.

Pre-populate a folder:

.. code-block:: bash

   morphic --folder /path/to/media

Requirements
------------

- Python 3.10+
- ``ffmpeg`` on ``PATH`` (for video conversion)
- Optional: NVIDIA/AMD GPU for accelerated duplicate detection

Optional GPU extras:

.. code-block:: bash

   # NVIDIA CUDA
   uv sync --extra cuda

   # AMD ROCm
   uv sync --extra rocm

   # OpenCL
   uv sync --extra opencl
