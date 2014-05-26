.. _usage:

=====
Usage
=====

This document outlines the basic procedure to setup and run an experiment with
payu.


Overview
========

The general layout of a payu-supported experiment consists of two directories:

* The *laboratory*, which contains the executable, input files, actively
  running experiments, and archived model output, and the

* The *control directory*, where the experiment is configured and run.

This separation allows us to run multiple self-resubmitting experiments
simultaneously that can share common executables and input data.


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
   is shown below:

   .. code:: sh

      mkdir -p /short/${PROJECT}/${USER}/${MODEL}

   where ``${MODEL}`` is from the list of supported models. For example, if
   your username is ``abc123`` and your default project is ``v45``, then the
   default laboratory directory for the MOM ocean model would be
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

5. Return to the home directory and create a *control directory*::

      mkdir -p ${HOME}/${MODEL}/my_expt
      cd ${HOME}/${MODEL}/my_expt

   Although the example control directory here is in the user's home directory,
   they can be placed anywhere and there is no predefined location.

6. Copy any input text files


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