.. _design:

============
Design Notes
============

This section describes miscellaneous information about the design of payu.


Model and Experiment Layout
===========================

Laboratory Structure
---------------------

An experiment requires that the model executable, configuration, and data files
be staged in the appropriate directories, outlined below:

Control Path
   Configuration files are stored here, and is also the directory where
   ``payu`` is invoked. This is usually the current working directory.

Laboratory Path
   This is the top-level directory for a particular model, and contains the
   model executables, input data, and model output for all experiments using
   this model. The default directory is ``/short/${PROJECT}/${USER}/${MODEL}``.

Herein, ``${LAB}`` refers to the laboratory path.

Executable Path
   Model executables are stored here. The default is ``${LAB}/bin``.

Input Path
   Data files are stored here. The default is ``${LAB}/input``.

Codebase Path (*not currently supported*)
   The sourcecode of the current active executable will be stored in this
   directory. The default is ``${LAB}/codebase``.

Archive Path
   Model output is stored in this directory, separated by experiment. For an
   experiment named ``myrun``, the archived output is stored in
   ``${LAB}/archive/myrun/output000``, ``output001``, ``output002``, etc. and
   restart information is stored in ``restart000``, ``restart001``, etc.

Work Path
   Experiments that are actively running are stored in the work path. For an
   experiment named ``myrun``, the default directory is ``${LAB}/work/myrun``.


Style Guide
===========

These are various unorganised notes on preferred coding style for payu.  While
it's unlikely that every file adheres to this style, it should generally be
adopted where possible.

1. All files should adhere to PEP8 rules.  In particular, no warnings should be
   reported by ``pycodestyle`` using default settings.

2. Docstrings should similarly adhere to PEP257, as reported by ``pydocstyle``.
   (Currently conformance to this rule is admittedly very poor.)

   In particular, ``help()`` should be readable and well-formatted for every
   module and function.

3. Modules should not be renamed.  This is bad::

      import numpy as np

   This is good::

      import numpy

   The reason here is to preserve shorter names for other uses in the code.
   But, as usual, the `HHGP's section on modules`_ explains this better than I
   can within a bullet point list.

   (Also note that this is another rule with poor conformance.)

4. Multiple equivalence checks should use tuples.  This is bad::

      if x == 'a' or x == 'b'

   This is good::

      if x in ('a', 'b')

5. Multiline lists and dicts are double-indented when in per-line format::

      pbs_vars = {
              'LD_LIBRARY_PATH': ':'.join(lib_paths),
              'PYTHONPATH': os.environ['PYTHONPATH'],
      }

   Also true for multiline list comprehensions::

      python_paths = [
              path
              for libdir in lib_paths
              for path in sys.path
              if not path.startswith(libdir)
              and not path.startswith(local_pythonpath)
      ]

.. _`HHGP's section on modules`:
   http://docs.python-guide.org/en/latest/writing/structure/#modules
