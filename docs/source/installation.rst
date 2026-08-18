Installation
============

Requirements
------------

SeaSenseLib requires Python 3.10 or later and depends on several scientific Python packages, all of which are installed automatically by ``pip``:

* **Core data handling**: xarray, pandas, numpy, scipy
* **File format support**: netcdf4, pycnv, pyrsktools, seabirdscientific, mhkit (with the ``dolfyn`` extra, for Nortek/RDI raw data)
* **Scientific computing**: gsw (Gibbs SeaWater library), pint (units)
* **Plotting**: matplotlib

You do not need to install these individually — they come with SeaSenseLib.

If you are new to Python, first check that Python 3.10+ is available:

.. code-block:: bash

   python3 --version

If it reports a version below 3.10 (or the command is not found), install a current Python from `python.org <https://www.python.org/downloads/>`_ or via a distribution such as Miniconda (see below) before continuing.

Install from PyPI
-----------------

The easiest way to install SeaSenseLib is using pip:

.. code-block:: bash

   pip install seasenselib

This will install SeaSenseLib and all required dependencies.

Using conda or mamba
--------------------

Many oceanographers manage Python with Anaconda/Miniconda (``conda``) or its faster drop-in replacement ``mamba``. SeaSenseLib is not yet published on conda-forge, so you create a conda environment and then install SeaSenseLib into it with ``pip``:

.. code-block:: bash

   # with conda
   conda create -n seasenselib python=3.11
   conda activate seasenselib
   pip install seasenselib

   # or with mamba (same commands, faster solver)
   mamba create -n seasenselib python=3.11
   mamba activate seasenselib
   pip install seasenselib

Installing with ``pip`` inside an activated conda environment is expected and supported here. Do not run ``conda install seasenselib`` — the package is not on any conda channel and that command will fail.

Development Installation
------------------------

If you want to contribute to the project or modify the code, follow these steps:

1. **Clone the repository:**

   .. code-block:: bash

      git clone https://github.com/ocean-uhh/seasenselib.git
      cd seasenselib

2. **Create and activate a virtual environment:**

   On Linux/macOS:

   .. code-block:: bash

      python3 -m venv venv
      source venv/bin/activate

   On Windows (CMD):

   .. code-block:: bat

      python -m venv venv
      venv\Scripts\activate.bat

   On Windows (PowerShell):

   .. code-block:: powershell

      python -m venv venv
      venv\Scripts\Activate.ps1

3. **Install in development mode:**

   .. code-block:: bash

      pip install --upgrade pip setuptools wheel
      pip install -e ".[dev]"

   This installs SeaSenseLib in "editable" mode (changes to the source take effect immediately without reinstalling). The ``[dev]`` part is an optional dependency group that adds tools needed only for development — pytest (running tests), sphinx, nbsphinx, myst-parser and the RTD theme (building these docs), plus build and twine (packaging). A plain ``pip install -e .`` skips those.

   The same editable install works inside a conda/mamba environment: activate the environment first, then run the ``pip install -e ".[dev]"`` command.

**Using the conda environment file:**

For development with conda, the repository provides an ``environment.yml`` that creates an environment named ``seasenselib`` with Python (3.10–3.13), ``gsw``, ``pandoc``, and all runtime and development dependencies:

.. code-block:: bash

   conda env create -f environment.yml
   conda activate seasenselib
   pip install -e .

The environment file installs the dependencies but not SeaSenseLib itself, so the final ``pip install -e .`` installs the package in editable mode from the repository root.

Alternative Installation Methods
--------------------------------

**Using Makefile (requires pipenv):**

If you have pipenv installed, you can use the provided Makefile:

.. code-block:: bash

   make setup
   make install

**Manual dependency installation:**

If you prefer to manage dependencies manually:

.. code-block:: bash

   pip install -r requirements.txt
   pip install -e .

Verify Installation
-------------------

Test that the installation works correctly:

**Test the command-line interface:**

.. code-block:: bash

   seasenselib --help

This should display the available commands and options.

**Test the Python library:**

.. code-block:: python

   import seasenselib
   from seasenselib.readers import SbeCnvReader
   print("SeaSenseLib installed successfully!")

**Run the test suite (development installation only):**

.. code-block:: bash

   python -m pytest tests/

(``python -m unittest discover tests/`` also works if you prefer the standard library test runner.)

Troubleshooting
---------------

**Common Issues:**

1. **Missing dependencies**: If you encounter import errors, ensure all dependencies are installed:

   .. code-block:: bash

      pip install -r requirements.txt

2. **Permission errors**: On some systems, you may need to use ``pip install --user`` to install packages in your user directory.

3. **Python version**: Ensure you're using Python 3.10 or later:

   .. code-block:: bash

      python --version

4. **Virtual environment issues**: If you're having trouble with virtual environments, try deactivating and recreating:

   .. code-block:: bash

      deactivate
      rm -rf venv
      python3 -m venv venv
      source venv/bin/activate

**Getting Help:**

If you encounter installation issues:

* Check the `GitHub Issues <https://github.com/ocean-uhh/seasenselib/issues>`_ for similar problems
* Create a new issue with details about your system and the error message
* Include the output of ``pip list`` and ``python --version``
