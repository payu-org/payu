.. _usage:

=====
Usage
=====

This document outlines the basic procedure to setup and run an experiment with
payu.


Setting up the laboratory
=========================

Before running an experiment, you must first set up the *laboratory* for the
associated numerical model if it does not already exist.

First, check the list of supported models::

   payu list

This shows the keyword for each supported model.


Manual setup
------------

Currently, the automated setup and build routines have some bugs that need
fixing, so most users will have to set up the laboratory manually.

1. Create a directory for the laboratory to reside. The default directory path
   is shown below::

      mkdir -p /short/${PROJECT}/${USER}/${MODEL}

   where ``${MODEL}`` is from the list of supported models. For example, if
   your username is ``abc123`` and you are in ``v45``, then the default
   laboratory directory for the MOM ocean model would be
   ``/short/v45/abc123/mom``.

2. Create subdirectories for the model binaries and input fields::

      cd /short/${PROJECT}/${USER}/${MODEL}
      mkdir bin input

3. Compile a model and copy its executable into the ``bin`` directory::

      cp /path/to/exec bin/exec

   You will want to give the executable a unique name.

4. Create or gather any input data files into an input subdirectory::

      mkdir input/my_data
      cp /path/to/data input/my_data/

   You will want a unique name for each input directory.

5. Return to the home directory and create a *control directory*.


Automatic setup
---------------

*This is currently not working, but the intended process is outlined here.*

To initialise the model laboratory, type::

   payu init model

where ``model`` is the model name from ``payu list``. This will create the
laboratory directory tree, get the source code, and build the model under its
default configuration.


Running your experiment
=======================
