Development
===========

Setting up
----------

Clone the repository and install dependencies:

.. code-block:: bash

   git clone https://github.com/andreassagen/morphic.git
   cd morphic
   uv sync --dev

Project Layout
--------------

.. code-block:: text

   morphic/
   ├── src/morphic/
   │   ├── __init__.py          # Package root, version
   │   ├── shared/              # Constants, utils, thumbnails, file browser
   │   │   ├── constants.py
   │   │   ├── utils.py
   │   │   ├── file_browser.py
   │   │   └── thumbnails.py
   │   ├── converter/           # Format conversion engine
   │   │   ├── constants.py
   │   │   ├── converter.py
   │   │   └── scanner.py
   │   ├── dupfinder/           # Duplicate detection
   │   │   ├── accelerator.py
   │   │   ├── images.py
   │   │   ├── videos.py
   │   │   └── scanner.py
   │   └── frontend/            # Flask web UI
   │       ├── app.py
   │       ├── routes_shared.py
   │       ├── routes_converter.py
   │       ├── routes_dupfinder.py
   │       ├── templates/
   │       └── static/
   ├── tests/                   # pytest test suite (395+ tests)
   ├── docs/                    # Sphinx documentation
   ├── pyproject.toml
   └── Makefile

Running Tests
-------------

.. code-block:: bash

   # Run all tests
   make test

   # Run with coverage report
   make coverage

   # Run a specific test file
   uv run pytest tests/test_shared_utils.py -v

Linting & Formatting
---------------------

.. code-block:: bash

   # Lint with ruff + pyright
   make lint

   # Auto-format
   make format

Building Documentation
----------------------

.. code-block:: bash

   make docs
   # Output is in docs/_build/html/

Architecture
------------

morphic follows a modular architecture with three main modules that share
a common set of constants and utilities via ``morphic.shared``:

**morphic.shared**
   Common constants (file extensions, thresholds), utility functions
   (file scanning, formatting), native folder browser dialog, and
   thumbnail generation.

**morphic.converter**
   File format conversion engine. Uses Pillow for images and ffmpeg
   (subprocess) for videos. The scanner discovers files and determines
   compatible target formats.

**morphic.dupfinder**
   Duplicate detection via perceptual hashing. Images are hashed with
   ``imagehash.phash``. Videos have frames extracted and hashed individually.
   A GPU accelerator provides optional CUDA/ROCm/OpenCL acceleration for
   batch operations.

**morphic.frontend**
   Flask web application that provides a unified tabbed interface for both
   modules. Uses blueprints for route organization.
