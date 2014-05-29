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

6. Copy any input text files in the control directory::

      cp /path/to/configs ${HOME}/${MODEL}/my_expt

7. Configure the experiment in a ``config.yaml`` file, such as the one shown
   below for MOM::

      # Scheduler settings
      queue: normal
      project: v45
      ncpus: 1
      walltime: 10:00
      jobname: bowl1

      # Model settings
      model: mom
      shortpath: /short/v45
      exe: fms_MOM_solo.x
      input: bowl1

      # Postprocessing
      collate_walltime: 10:00
      collate_mem: 1GB

   See the :ref:`config` section for more details.


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

Once the laboratory has been setup and the experiment has been configured, run
the experiment by typing the following::

   payu run

This will run the model once and store the output in the archive directory.

To continue the simulation from its last point, type ``payu run`` again.

In order to schedule ``N`` successive runs, use the ``-n`` flag::

   payu run -n N

If there are no archived runs, then the model will initialise itself. If the
model has been run ``K`` times, then it will continue from this point and run
``N`` more jobs.

If you need to run (or re-run) the ``K``\ th job, rather than the most recent
run, use the ``-i`` flag::

   payu run -i K

Note that job numbering is 0-based, so that the first run is 0, the second run
is 1, and so on.

Running jobs are stored in laboratory's ``work`` subdirectory, and completed
runs are stored in the ``archive`` subdirectory.


Postprocessing
==============

Model output in parallel jobs is typically divided across several files, which
can be inconvenient for analysis. Payu offers a ``collate`` subcommand to
collate these separated files into a single file.

For most jobs, collation is called automatically. But if you need to manually
collate the ``K``\ th run, type the following::

   payu collate -i K
