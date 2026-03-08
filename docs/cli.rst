Command-Line Interface
======================

morphic
-------

.. code-block:: text

   usage: morphic [-h] [--host HOST] [--port PORT] [--folder FOLDER]
                  [--debug] [--no-browser]

   Morphic — media format converter & duplicate finder

Options
^^^^^^^

``--host HOST``
   Host to bind to. Default: ``127.0.0.1``.

``--port PORT``
   Port to listen on. Default: ``8000``.

``--folder FOLDER``
   Pre-populate the folder path in the UI.

``--debug``
   Enable Flask debug mode with auto-reload.

``--no-browser``
   Don't auto-open the browser on start.

Examples
^^^^^^^^

.. code-block:: bash

   # Default: open browser on http://127.0.0.1:8000
   morphic

   # Custom port, no auto-open
   morphic --port 9000 --no-browser

   # Pre-select a folder
   morphic --folder ~/Pictures

   # Debug mode
   morphic --debug

Running as a module
^^^^^^^^^^^^^^^^^^^

You can also run morphic as a Python module:

.. code-block:: bash

   python -m morphic.frontend
