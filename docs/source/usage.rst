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
simultaneously that can share common executables and input data. It also 
allows the flexibility to have the relatively small control directories
in a location that is continuously backed up.

Setting up the laboratory
=========================

Before running an experiment, you must first set up the *laboratory* for the
associated numerical model if it does not already exist.

First, check the list of supported models::

   payu list

This shows the keyword for each supported model.

Automatic setup
---------------

To initialise the model laboratory, type::

   payu init -m model

where ``model`` is the model name from ``payu list``. This will create the
laboratory directory tree.

Automatic compilation of models is no longer supported.

Manual setup
------------

If the automated approach does not work you will have to set up the laboratory 
manually.

1. Create a directory for the laboratory to reside. The default directory path
   is shown below:

   .. code:: sh

      mkdir -p /scratch/${PROJECT}/${USER}/${MODEL}

   where ``${MODEL}`` is from the list of supported models. For example, if
   your username is ``abc123`` and your default project is ``v45``, then the
   default laboratory directory for the MOM ocean model would be
   ``/scratch/v45/abc123/mom``.

2. Create subdirectories for the model binaries and input fields::

      cd /scratch/${PROJECT}/${USER}/${MODEL}
      mkdir bin input

Populate laboratory directories
-------------------------------

1. Compile a model and copy its executable into the ``bin`` directory in the laboratory::

      cp /path/to/exec bin/exec

   You will want to give the executable a unique name.

2. Create or gather any input data files into an subdirectory in the input directory in the 
   laboratory::

      mkdir input/my_data
      cp /path/to/data input/my_data/

   You will want a unique name for each input directory.

Create experiment
-----------------

The payu control directory is maintained under version control using 
git_ so existing experiments can be cloned. This is the best way to copy
an experiment as it guarantees that only the required files are copied
to a new control directory, and maintains a link to the original 
experiment through the shared git history.

For example::
    
      mkdir -p ${HOME}/${MODEL}
      cd ${HOME}/${MODEL}
      git clone https://github.com/payu-org/mom-example.git my_expt
      cd my_expt

To create an experiment manually:

1. Return to the home directory and create a *control directory*::

      mkdir -p ${HOME}/${MODEL}/my_expt
      cd ${HOME}/${MODEL}/my_expt

   Although the example control directory here is in the user's home directory,
   they can be placed anywhere and there is no predefined location.

2. Populate the control directory. 

   Copy any input text files in the control directory::

      cp /path/to/configs ${HOME}/${MODEL}/my_expt

   Configure the experiment in a ``config.yaml`` file, such as the one shown
   below for MOM::

      # Scheduler settings
      queue: normal
      ncpus: 1
      walltime: 10:00
      jobname: bowl1

      # Model settings
      model: mom
      shortpath: /scratch/v45
      exe: fms_MOM_solo.x
      input: bowl1

      # Postprocessing
      collate:
          walltime: 10:00
          mem: 1GB

   See the :ref:`config` section for more details.


.. _git: https://git-scm.com
   


Running your experiment
=======================

Once the laboratory has been created and the experiment has been configured, you
can check that the paths have been correctly specified by running::

    payu  setup

This creates the temporary ``work`` directory and is done automatically when
the model is run. If there any errors these can be fixed. ``payu`` will not
run the model if there is an existing ``work`` directory, so this must be
removed like so::

    payu sweep

The ``setup`` command will also generate manifest files in the ``manifest``
directory. The manifest files track the executable, input and restart files used
in each run. When running at NCI the manifest file must be present as it is
scanned for storage points in order to correctly specify the argument to the
```-l storage=``` option when submitting a PBS job.

Once you are satisfied the configuration is correct, and there is no existing
```work``` directory, run the experiment by typing the following::

   payu run

This will run the model once and store the output in the ```archive``` directory.

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


Cleaning up 
===========

If you experiment crashes or fails for any reason, then payu will usually abort
and keep any remaining files in the ``work`` and control directories.

To clean up a failed job and prepare it for resubmission, use the ``sweep``
command::

   payu sweep

This will delete the contents of ``work`` and move any model and scheduler logs
into a ``pbs_logs`` directory.  Any model output in ``archive`` will not be
deleted.


Deleting an experiment archive
------------------------------

If you also want to delete all runs from an experiment in the ``archive``, 
use the ``--hard`` flag::

   payu sweep --hard

**This will delete your runs** and can potentially erase months of work, so
use it with caution.

Hard sweeps will only delete the run output for your particular experiment.
Other experiment runs will not be harmed by this command.


Postprocessing
==============

Model output in parallel jobs is sometimes divided across several files, which
can be inconvenient for analysis. Payu offers a ``collate`` subcommand to
collate these separated files into a single file. This is only necessary, and 
supported, for some models.

For most jobs, collation is called automatically. But if you need to manually
collate the ``K``\ th run, type the following::

   payu collate -i K

Alternatively you can directly specify a directory name::

  payu collate -d dir_name

This is useful when the data files have been moved out of the payu
directory structure, or if you need to collate restart files, which is
necessary when changing processor layout.
