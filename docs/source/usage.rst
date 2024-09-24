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

Using a git repository for the experiment
-----------------------------------------

It is recommended to use the git_ version control system for the payu 
*control directory*. This allows the experiment to be easily copied via 
cloning. There is inbuilt support in payu for an experiment runlog which 
uses git to track changes to configuration files between experiment runs. There are payu commands 
for creating and moving between git branches so multiple related experiments 
can be run from the same control directory.

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


Clone experiment
----------------

Cloning is the best way to copy an experiment as it guarantees that only the 
required files are copied to a new control directory, and maintains a link 
to the original experiment through the shared git history. To clone the 
repository, you can use ``payu clone``. This is a wrapper around ``git clone`` 
which additionally creates or updates the metadata file which gets copied to 
the experiment archive directory (see :ref:`usage-metadata`).
For example::
    
      mkdir -p ${HOME}/${MODEL}
      cd ${HOME}/${MODEL}
      payu clone ${REPOSITORY} my_expt
      cd my_expt

Where ``${REPOSITORY}`` is the git URL or path of the repository to clone from, 
for example, https://github.com/payu-org/mom-example.git.

To clone and checkout an existing git branch, use the ``-B/--branch`` flag and
specify the branch name::

      payu clone --branch ${EXISTING_BRANCH} ${REPOSITORY} my_expt

To create and checkout a new git branch use ``-b/--new-branch`` and specify a
new branch name::

      payu clone --new-branch ${NEW_BRANCH} ${REPOSITORY} my_expt

To create a new git branch starting from a tag or commit, use ``-s/--start-point``
flag::

      payu clone -b ${NEW_BRANCH} -s {COMMIT_HASH|TAG} ${REPOSITORY} my_expt

To see more configuration options for ``payu clone``, 
run:: 

      payu clone --help

As an alternative to creating and checking out branches with ``payu clone``, 
``payu checkout`` can be used instead (see :ref:`usage-metadata`). 


Create experiment
-----------------

If a suitable experiment does not already exist it will have to be
created manually:

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

Once the laboratory has been created and the experiment has been configured, as 
an optional step you can check that the paths have been correctly specified by 
running::

    payu  setup

This creates the temporary ``work`` directory and is done automatically when
the model is run. If there any errors in the configuration, such as incorrect 
or missing paths, these can be fixed. ``payu`` will not run the model if there 
is an existing ``work`` directory, so this must be removed (see :ref:`Cleaning up`).

The ``setup`` command will also generate manifest files in the ``manifest``
directory. The manifest files track the executable, input and restart files used
in each run. When running at NCI the manifest file must be present as it is
scanned for storage points in order to correctly specify the argument to the
```-l storage=``` option when submitting a PBS job.

It is possible to create an experiment configuration such that the input
and executable manifests are correct if the experiment is run on the same
system. In such a case the ``manifest`` options need to be set correctly
to always reuse those manifests and it should be possible to run the 
experiment immediately.

Once you are satisfied the configuration is correct, and there is no existing
```work``` directory, run the experiment by typing the following::

   payu run

This will run the model once and store the output in the ```archive``` directory.

Optionally if there is an existing ``work`` directory the ``-f/--force`` flag 
will automatically ``sweep`` any existing ``work`` directory::

   payu run -f

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

If you have instructed ``payu`` to run for a number of resubmits but for some
reason need to stop a run after the current run has completed create a file
called ``stop_run`` in the control directory. 

It is possible to require that a run reproduce an existing run using the 
``-r/--reproduce`` flag:

  payu run -r

When this invoked all the manifests are read in and hashes checked for consistency
and only if all executables, inputs and restart files are unchanged will the run
proceed. As the restart files are read directly from the manifests which are written
before the previous run completed, by definition a restart run will not look for 
or use any restart files that are more recent.

The reproduce option can be useful to be able to re-run a simulation for the 
purposes of checking reproducibility when compute infrastructure changes, or when
spinning off a perturbation run to ensure consistency with a control run before
applying modifications.

To run from an existing model run, also called a warm start, set the
``restart`` option to point to the folder containing the restart files
from a previous matching experiment.

If restart pruning configuration has changed, there may be warnings if 
many restarts will be pruned as a result. If this is desired, at the next 
run use ``-F/--force-prune-restarts`` flag:

  payu run --force-prune-restarts


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
collate output from run ``K``, type the following::

   payu collate -i K

This will also collate restart ``K-1`` if ``restart: true`` in the ``collate``
section of the configuration file.

Alternatively you can directly specify a directory name::

  payu collate -d dir_name

This is useful when the data files have been moved out of the payu
directory structure, or if you need to collate restart files, which is
necessary when changing processor layout.

To manually sync experiment output files to a remote archive, firstly ensure
that ``path`` in the ``sync`` namespace in ``config.yaml``, 
is correctly configured as it may overwrite any pre-exisiting outputs. 
Then run::

   payu sync

By default ``payu sync`` will not sync the latest restarts that may be pruned 
at a later date. To sync all restarts including the latest restarts, use the 
``--sync-restarts`` flag::

   payu sync  --sync-restarts

.. _usage-metadata:

Metadata and Related Experiments
================================

Metadata files
--------------

Each experiment has a metadata file, called ``metadata.yaml`` in the *control
directory*. This contains high-level metadata about the experiment and uses 
the ACCESS-NRI experiment schema_. An important field is the ``experiment_uuid``
which uniquely identifies the experiment. Payu generates a new UUID when:

* Using payu to clone a pre-existing git_ repository of the *control directory*

* Using payu to create and checkout a new git branch in the *control directory*

* Or, when setting up an experiment run if there is not a pre-existing metadata 
  file, UUID, or experiment ``archive`` directory.

For new experiments, payu may generate some additional metadata fields. This 
includes an experiment name, creation date, contact, and email if defined in 
the git configuration. This also includes parent experiment UUID if starting 
from restarts and the experiment UUID is defined in metadata of the parent directory 
containing the restart.

Once a metadata file is created or updated, it is copied to the directory 
that stores the archived experiment outputs. 

.. _schema: https://github.com/ACCESS-NRI/schema/blob/main/experiment_asset.json

Experiment names
----------------

An experiment name is used to identify the experiment inside the ``work`` and 
``archive`` sub-directories inside the *laboratory*.

The experiment name historically would default to the name of the *control 
directory*. This is still supported for experiments with pre-existing
archived outputs. To support git branches and ensure uniqueness in shared 
archives, the new default behaviour is to add the branch name and a short 
version of the experiment UUID to the name of the *control directory* when 
creating experiment names. 

For example, given a control directory named 
``my_expt`` and a UUID of ``416af8c6-d299-4ee6-9d77-4aefa8a9ebcb``, 
the experiment name would be:

* ``my_expt-perturb-416af8c6`` - if running an experiment on a branch named 
  ``perturb``.

* ``my_expt-416af8c6`` - if the control directory was not a git repository or 
  experiment was run from the ``main`` or ``master`` git branch.

To preserve backwards compatibility, if there's a pre-existing archive under 
the *control directory* name, this will remain the experiment name (e.g. 
``my_expt`` in the above example). Similarly, if the ``experiment`` value is
configured (see :ref:`config`), this will be used for the experiment name.

Switching between related experiments
-------------------------------------

To be able to run related experiments from the same control directory 
using git branches, you can use ``payu checkout`` which is a wrapper around 
``git checkout``. Creating new branches will generate a new UUID, update metadata
files, and create a branch-UUID-aware experiment name in ``archive``. 
Switching branches will change ``work`` and ``archive`` symlinks in the control 
directory to point to directories in *laboratory* if they exist.

To create a git branch for a new experiment, use the ``-b`` flag. 
For example, to create and checkout a new branch called ``perturb1``, run::

      payu checkout -b perturb1

To create a new experiment from an existing branch, specify the branch name 
or a commit hash after the new branch name. For example, 
the following creates a new experiment branch called ``perturb2`` 
that starts from ``perturb1``:: 

      payu checkout -b perturb2 perturb1

To specify a restart path to start from, use the ``--restart``/ ``-r`` flag, 
for example::

      payu checkout -b perturb --restart path/to/restart

Note: This can also be achieved by configuring ``restart`` (see :ref:`config`).

To checkout and switch to an existing branch and experiment, omit the ``-b`` flag. 
For example, the following checks out the ``perturb1`` branch:: 

      payu checkout perturb1

To see more ``payu checkout`` options, run::

      payu checkout --help

For more information on git branches that exist in the control directory 
repository, run::

      payu branch # Display local branches UUIDs
      payu branch --verbose # Display local branches metadata 
      payu branch --remote # Display remote branches UUIDs
