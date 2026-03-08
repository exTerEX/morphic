Configuration
=============

morphic is configured through CLI arguments and module-level constants.
There is no configuration file.

Shared Constants
----------------

The shared module defines default thresholds and extensions used by both
the converter and dupfinder modules.

.. list-table:: Key Constants
   :header-rows: 1
   :widths: 35 15 50

   * - Constant
     - Value
     - Description
   * - ``IMAGE_EXTENSIONS``
     - 22 formats
     - ``.jpg``, ``.png``, ``.webp``, ``.tif``, ``.bmp``, ``.heif``, etc.
   * - ``VIDEO_EXTENSIONS``
     - 21 formats
     - ``.mp4``, ``.avi``, ``.mkv``, ``.mov``, ``.webm``, etc.
   * - ``EXCLUDED_FOLDERS``
     - 25 names
     - ``node_modules``, ``.git``, ``__pycache__``, etc.
   * - ``DEFAULT_IMAGE_THRESHOLD``
     - 0.90
     - Similarity threshold for image duplicate detection
   * - ``DEFAULT_VIDEO_THRESHOLD``
     - 0.85
     - Similarity threshold for video duplicate detection
   * - ``DEFAULT_HASH_SIZE``
     - 16
     - Hash size for perceptual hashing
   * - ``DEFAULT_NUM_FRAMES``
     - 10
     - Number of frames extracted from each video
   * - ``DEFAULT_NUM_WORKERS``
     - 4
     - Default worker thread count

GPU Acceleration
----------------

The dupfinder module automatically detects available GPU backends in
this priority order:

1. **CUDA** (via PyTorch) — NVIDIA GPUs
2. **CUDA** (via CuPy) — NVIDIA GPUs (fallback)
3. **ROCm** (via PyTorch) — AMD GPUs
4. **OpenCL** (via PyOpenCL) — Any OpenCL-capable GPU
5. **CPU** — Multiprocessing fallback (always available)

Install optional extras to enable GPU support:

.. code-block:: bash

   uv sync --extra cuda    # NVIDIA
   uv sync --extra rocm    # AMD
   uv sync --extra opencl  # OpenCL
