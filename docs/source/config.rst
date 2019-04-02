.. _config:

===========================
Configuring your experiment
===========================

This section outlines the configuration of an individual experiment, which is
stored in the ``config.yaml`` file.

Configuration files are written in the YAML_ file format. YAML allows us to
store and configure both individual fields as well as higher data structures,
such as lists and dictionaries. Data can also be encapsulated in larger
structures. This is indicated by whitespace in the file, which is significant
in YAML.

.. _YAML: http://www.yaml.org/


Configuration Settings
======================

Scheduler
---------

These settings are primarily used by the PBS scheduler.

``queue`` (*Default:* ``normal``)
   The PBS queue to submit your job. Equivalent to ``qsub -q QUEUE``.

``project`` (*Default:* ``$PROJECT``)
   The project from which to submit the model (and deduct CPU hours).
   Equivalent to ``qsub -P PROJECT``. The default value is the current
   ``$PROJECT`` environment variable. Note that ``project`` is used as part of
   the default configuration for various laboratory filepaths.

``jobname`` (*Default: Control directory name*)
   The name of the job as it appears in the PBS queue. If no name is provided,
   then it uses the name of the experiment's control directory.

``ncpus``
   The number of CPUs used during model simulation. Usually equivalent to
   ``qsub -l ncpus=N``. This is the number passed on to ``mpirun`` during model
   execution.

   Although it usually matches the CPU request, the actual request
   may be larger if ``npernode`` is being used.

``npernode``
   The number of CPUs used per node. This settings is passed on to ``mpirun``
   during model execution. In most cases, this is converted into an
   equivalent ``npersocket`` configuration.

   This setting may be needed in cases where a node is unable to efficiently
   use all of its CPUs, such as performance issues related to NUMA.

``mem`` (*Default: 31GiB per node*)
   Amount of memory required for the job. Equivalent to ``qsub -l mem=MEM``.
   The default value requests (almost) all of the nodes' memory for jobs using
   multiple nodes.

   In general, it is good practice to keep this number as low as possible.

``walltime``
   The amount of time required to run an individual job, specified as
   ``hh:mm:ss``. Equivalent to ``qsub -l walltime=TIME``.

   Jobs with shorter walltimes will generally be prioritised ahead of jobs with
   longer walltimes.

``priority``
   Job priority setting. Equivalent to ``qsub -p PRIORITY``.

``umask`` (*Default: 027*)
   Default permission mask ("umask") for new files created during model
   execution. Nonzero values will disable specific permissions, following
   standard octal notation.

   The first digit should be a zero when using standard octal format.

``qsub_flags``
   This is a generic configuration marker for any unsupported qsub flags. This
   setting is applied to any ``qsub`` calls.


Collation
---------

Collation scheduling can be configured independently of model runs. Currently,
all collation jobs are single CPU jobs and are not parallelised.

``collate_queue`` (*Default:* ``copyq``)
   PBS queue used for collation jobs.

``collate_walltime``
   Time required for output collation.

``collate_mem``
   Memory required for output collation.

``collate_ignore``
   Ignore these files during collation. This can either be a single filename or
   a list of filenames. Only FMS models (MOM, GOLD) support this setting.

``collate_flags``
   Specify the flags passed to the collation program.
   Only FMS models (MOM, GOLD) support this setting.

Model
-----

These settings are part of general model execution, including OpenMPI
configuration.

``model`` (*Default: Parent directory of control directory*)
   The model (or coupled model configuration) used in the experiment. This
   model name must be one of the supported models shown in ``payu list``.

   If no model name is provided, then it will attempt to infer the model based
   on the parent directory of the experiment. For example, if we run our
   experiment in ``~/mom/bowl1``, then ``mom`` will be used as the model type.
   However, it is generally better to specify the model type.

``shortpath`` (*Default:* ``/short/${PROJECT}``)
   The top-level directory for general scratch space, where laboratories and
   model output are stored. Users who run from multiple projects will generally
   want to set this explicitly.

``input``
   Listing of the directories containing model input fields, linked to the
   experiment during setup. This can either be the name of a directory in the
   laboratory's ``input`` directory::

      input: core_inputs

   the absolute path of an external directory::

      input: /short/v45/core_input/iaf/

   or a list of input directories::

      input:
         - year_100_restarts
         - core_inputs

   If there are multiple files in each directory with the same name, then the
   earlier directory of the list takes precedence.

``exe``
   Binary executable for the model. This can either be a filename in the
   laboratory's ``bin`` directory, or an absolute filepath. Various model
   drivers typically define their own default executable names.

``submodels``
   If one is running a coupled model containing several submodels, then each
   model is configured individually within a ``submodel`` namespace, such as in
   the example below for the ACCESS driver::

      model: access
      submodels:
         atmosphere:
            model: matm
            exe: matm_MPI1_nt62.exe
            input: iaf_matm_simon
            ncpus: 1
         ocean:
            model: mom
            exe: fms_MOM_ACCESS_kate.x
            input: iaf_mom
            ncpus: 120
         ice:
            model: cice
            exe: cice_MPI1_6p.exe
            input: iaf_cice
            ncpus: 6
         coupler:
            model: oasis
            input: iaf_oasis
            ncpus: 0

``restart_freq`` (*Default:* ``5``)
   Specifies the rate of saved restart files. For the default rate of 5, we
   keep the restart files for every fifth run (``restart004``, ``restart009``,
   ``restart014``, etc.).

   Intermediate restarts are not deleted until a permanently archived restart
   has been produced. For example, if we have just completed run ``11``, then
   we keep ``restart004``, ``restart009``, ``restart010``, and ``restart011``.
   Restarts 10 through 13 are not deleted until ``restart014`` has been saved.

   ``restart_freq: 1`` saves all restart files.

*The following model-based tags are typically not configured*

``user`` (*Default:* ``${USER}``)
   The username used to construct the laboratory paths. It is generally
   recommended that laboratories be stored under username, so this setting is
   usually not necessary (nor recommended).

``laboratory`` (*Default:* ``/short/${PROJECT}/${USER}/${MODEL}``)
   The top-level directory for the model laboratory, where the codebase, model
   executables, input fields, running jobs, and archived output are stored.

``control`` (*Default: current directory*)
   The control path for the experiment. The default setting is the path of the
   current working directory.

``experiment`` (*Default: current directory*)
   The experiment name used for archival. The default setting uses the
   ``control`` directory name.


Postprocessing
==============

``collate`` (*Default:* ``True``)
   Controls whether or not a collation job is submitted after model execution.

   This is typically ``True``, although individual model drivers will often set the
   default value to ``False`` if collation is unnecessary.

``userscripts``
   Namelist to include separate userscripts or subcommands at various stages of
   a payu submission. Inputs can be either script names (``some_script.sh``) or
   individual subcommands (``echo "some_data" > input.nml``, ``qsub
   some_script.sh``).

   Specific scripts are defined below:

   ``init``
      User-defined command to be called after experiment initialization, but
      before model setup.

   ``setup``
      User-defined command to be called after model setup, but prior to model
      execution.

   ``run``
      User-defined command to be called after model execution but prior to
      model output archive.

   ``archive``
      User-defined command to be called after model archival, but prior to any
      postprocessing operations, such as ``payu collate``.

``postscript``
   This is an older, less user-friendly, method to submit a script after ``payu
   collate`` has completed. Unlike the ``userscripts``, it does not support
   user commands. These scripts are always re-submitted via ``qsub``.


Miscellaneous
=============

``debug`` (*Default:* ``False``)
   Enable the debugger for any ``mpirun`` jobs. Equivalent to ``mpirun
   --debug``. On raijin, this defaults to a Totalview session. This will
   probably only work for interactive sessions.

``mpirun``
   Append any unsupported ``mpirun`` arguments to the ``mpirun`` call of the
   model. This setting supports both single lines and a list of input
   arguments. Example shown below::

      mpirun:
         - -mca mpi_preconnect_mpi 1   # Enable preconnecting
         - -mca mtl ^mxm               # Disable MXM acceleration
         - -mca coll ^fca              # Disable FCA acceleration

``ompi``
   Enable any environment variables required by ``mpirun`` during execution,
   such as ``OMPI_MCA_coll``. The following example below disables "matching
   transport layer" and "collective algorithm" components::

      ompi:
         OMPI_MCA_coll: ''
         OMPI_MCA_mtl: ''

``stacksize``
   Set the stacksize for each process in kiB. ``unlimited`` is also a valid
   setting (and typically required for many models).

   *Note:* ``unlimited`` *works without any issues, but explicit stacksize
   values may not be correctly communicated across raijin nodes.*

``repeat``
   Ignore any restart files and repeat the initial run upon resubmission. This
   is generally only used for testing purposes, such as bit reproducibility.

Deprecated settings
===================

``core2iaf``
   This is used to extract an individual year out of a larger multi-year
   forcing field in the MOM ocean model. However, there is currently no
   performance improvement when using this setting, so it is not recommended
   and is scheduled for deletion.
