Installation
============

Requirements
------------

SeaSenseLib requires Python 3.7 or later and depends on several scientific Python packages:

* **Core dependencies**: xarray, pandas, numpy, matplotlib
* **File format support**: netcdf4, pycnv, pyrsktools
* **Scientific computing**: scipy, gsw (Gibbs SeaWater library)

Install from PyPI
-----------------

The easiest way to install SeaSenseLib is using pip:

.. code-block:: bash

   pip install seasenselib

This will install SeaSenseLib and all required dependencies.

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

   This installs SeaSenseLib in "editable" mode along with development dependencies like pytest and sphinx.

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

   python -m unittest discover tests/

Troubleshooting
---------------

**Common Issues:**

1. **Missing dependencies**: If you encounter import errors, ensure all dependencies are installed:

   .. code-block:: bash

      pip install -r requirements.txt

2. **Permission errors**: On some systems, you may need to use ``pip install --user`` to install packages in your user directory.

3. **Python version**: Ensure you're using Python 3.7 or later:

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