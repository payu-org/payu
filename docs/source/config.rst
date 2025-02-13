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
   The PBS queue to submit your job. Equivalent to ``qsub -q queue``.

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

   Although it usually matches the CPU request, the actual request may be
   larger if ``npernode`` is being used.

``ncpureq``
   Hard override for the number of cpus used in the PBS submit. This is useful
   when the number of CPUs used in the ``mpirun`` command is not the same as
   the number of cpus required. For example, when running an OpenMP only model
   like ``qgcm``, set ``ncpus=1``, and then set ``ncpureq`` to the number of
   threads required to run the model.

``npernode``
   The number of CPUs used per node. This settings is passed on to ``mpirun``
   during model execution. In most cases, this is converted into an equivalent
   ``npersocket`` configuration.

   This setting may be needed in cases where a node is unable to efficiently
   use all of its CPUs, such as performance issues related to NUMA.

``mem`` (*Default: 192GiB per node*)
   Amount of memory required for the job. Equivalent to ``qsub -l mem=MEM``.
   The default value requests (almost) all of the nodes' memory for jobs using
   multiple nodes.

   In general, it is good practice to keep this number as low as possible.

``platform``
   Set platform specific defaults. Available sub options:
       ``nodemem``
          Override default memory per node. Used when memory not specified to
          calculate memory request
       ``nodesize``
          Override default ncpus per node. Used to calculate ncpus to fully
          utilise nodes regardless of requested number of cpus

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

``jobfs``
   The maximum amount of local disk available to the job on the hosting compute nodes. 
   If this is missing in the submission, the value is set to 100 MiB. 
   The `jobfs` allocation in a multiple-node jobs will be distributed equally among every nodes.
   See `NCI jobfs documentation`_ and the `CLEX blog`_ for details.

``storage``
   On the NCI system gadi all storage mount points must be specified, except
   ``/home`` and ``/scratch/$PROJECT``. By default payu will scan all relevant
   configuration paths and manifests for filepaths that are stored on mounts
   that begin with ``/scratch`` or ``/g/data``, and add the correct storage
   flags to the ``qsub`` submission. In cases where payu cannot determine all
   the required storage points automatically they can be specified using the
   ``storage`` option. Each key is a storage mount point descriptor, and
   contains an array of project code values::

      storage:
            gdata:
                  - x00
                  - a15
            scratch:
                  - zz3

.. _`NCI jobfs documentation`: https://opus.nci.org.au/spaces/Help/pages/236881349/PBS+Directives...#PBSDirectives...--ljobfs=%3C10GB%3E
.. _`CLEX blog`: https://coecms.github.io/posts/2022-11-10-jobfs.html

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

``shortpath`` (*Default:* ``/scratch/${PROJECT}``)
   The top-level directory for general scratch space, where laboratories and
   model output are stored. Users who run from multiple projects will generally
   want to set this explicitly.

``input``
   Listing of the directories containing model input fields, linked to the
   experiment during setup. This can either be the name of a directory in the
   control directory or in laboratory's ``input`` directory::

      input: core_inputs

   the absolute path of an external directory::

      input: /scratch/v45/core_input/iaf/

   or a list of input directories::

      input:
         - year_100_restarts
         - core_inputs
         - /scratch/v45/core_input/iaf/

   If there are files in each directory with the same name, then the earlier
   directory of the list takes precedence.

``exe``
   Binary executable for the model. This can be a filename or an absolute
   filepath. If it's a filename, it needs be found in either the laboratory's
   ``bin`` directory, or in paths added to ``$PATH`` by loaded environment
   modules (see configuring :ref:`modules<configuring-modules>` for how to load
   modules).
   Various model drivers typically define their own default executable names.

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
   Specifies the rate of saved restart files. This rate can be either an 
   integer or date-based. For the default rate of 5, we
   keep the restart files for every fifth run (``restart000``, ``restart005``,
   ``restart010``, etc.). To save all restart files, set ``restart_freq: 1``.

   If ``restart_history`` is not configured, intermediate restarts are not 
   deleted until a permanently archived restart has been produced. 
   For example, if we have just completed run ``11``, then
   we keep ``restart000``, ``restart005``, ``restart010``, and ``restart011``.
   Restarts 11 through 14 are not deleted until ``restart015`` has been saved.
   
   To use a date-based restart frequency, specify a number with a time unit.
   The supported time units are  ``YS`` - year-start, ``MS`` - month-start,
   ``W`` - week, ``D`` - day, ``H`` - hour, ``T`` - minute and ``S`` - second.
   For example, ``restart_freq: 10YS`` would save earliest restart of the year,
   10 years from the last permanently archived restart's datetime.

   Please note that currently, only ACCESS-ESM1.5, ACCESS-OM2, ACCESS-OM3, MOM5 
   , MOM6 and UM7 models support date-based restart frequency, as it depends on the payu 
   model driver being able to parse restarts files for a datetime.

``restart_history``
    Specifies how many of the most recent restart files to retain regardless of 
    ``restart_freq``.

*The following model-based tags are typically not configured*

``user`` (*Default:* ``${USER}``)
   The username used to construct the laboratory paths. It is generally
   recommended that laboratories be stored under username, so this setting is
   usually not necessary (nor recommended).

``laboratory`` (*Default:* ``/scratch/${PROJECT}/${USER}/${MODEL}``)
   The top-level directory for the model laboratory, where the codebase, model
   executables, input fields, running jobs, and archived output are stored.

``control`` (*Default: current directory*)
   The control path for the experiment. The default setting is the path of the
   current working directory.

``experiment``
   The experiment name used for archival. This will override the experiment
   name generated using metadata and existing archives 
   (see :ref:`usage-metadata`).

Manifests
---------

payu automatically generates and updates manifest files. See :ref:`manifests`
section for details.

``reproduce``
      These options allow fine-grained control of manifest checking to enable
      reproducible experiments. The default value is the value of the global
      ``reproduce`` flag, which is set using a command line argument and
      defaults to *False*. These options **override** the global ``reproduce``
      flag. If set to *True* payu will refuse to run if the MD5 hashes in the
      relevant manifest do not match.

      ``exe`` (*Default: global reproduce flag*)
            Enforce executable reproducibility.

      ``input`` (*Default: global reproduce flag*)
            Enforce input file reproducibility.

      ``restart`` (*Default: global reproduce flag*)
            Enforce restart file reproducibility.

``ignore`` (*Default: .\**):
      List of ``glob`` patterns which match files to ignore when scanning input
      directories. This is an array, so multiple patterns can be specified on
      multiple lines. The default is *.\** which ignores all hidden files on a
      POSIX filesystem.


Archiving
---------

``archive``
      On completion of a model run, payu moves model output, restart, and log
      files from the temporary work area to the experiment archive directory.
      The following settings control the steps taken during the archive step:

      ``enable`` (*Default:* ``True``)
            Flag to enable/disable the archive step. If ``False`` all output, restart,
            and log files will remain in the work directory, and any collation, post-processing,
            and syncing will not be run.
      ``compress_logs`` (*Default:* ``True``)
            Compress model log files into a tarball. Currently only implemented for CICE4.


Collation
---------

Collation scheduling can be configured independently of model runs. Not all
models support, or indeed require, collation. Collation is currently supported
for MITgcm and any of the FMS based models (MOM, GOLD, SIS).

The collate process joins a number of smaller files which contain different
parts of the model grid together into target output files.

Parallelisation of collation is supported for FMS based models using threaded
multiprocessing. Collation time can be reduced if there are multiple target
collate files. The magnitude of the collation time reduction depends a great
deal on the time taken to collate each target file, the number of such files,
and the number of cpus used. It is difficult to say a priori what settings are
optimal: some experimentation may be necessary.

There is also experimental support for MPI parallelisation when using
mppnccombine-fast_

.. _mppnccombine-fast: https://github.com/coecms/mppnccombine-fast

Collate options are specified as sub-options within a separate ``collate``
namespace:

``enable`` (*Default: True*)
   Flag to enable/disable collation

``queue`` (*Default:* ``copyq``)
   PBS queue used for collation jobs.

``walltime``
   Time required for output collation.

``mem`` (*Default:* ``2GB``)
   Memory required for output collation.

FMS based model only options:

``ncpus``
   Number of cpus used for collation.

``ignore``
   Ignore these target files during collation. This can either be a single
   filename or a list of filenames.

``flags``
   Specify the flags passed to the collation program. Defaults depend on value
   of ``mpi`` flag

``exe``
   Binary executable for the collate program. This can be either a filename in
   the laboratory's ``bin`` directory, or an absolute filepath.

``restart`` (*Defaut: False*)
   Collate restart files from previous run.

``mpi``
   Use mpi parallelism and mppnccombine-fast_.

``glob``
   When ``mpi`` is ``True`` attempt to generate an equivalent glob string for
   the list of files being collated to avoid issues with limits on the number
   of arguments for an command being run using MPI

``threads`` (*Default:* 1)
   When ``mpi`` is ``True`` it is also possible to still use multiple threads
   by specifying this option. The number of cpus used for each collation thread
   is then ``ncpus / nthreads``


User Processing
--------------

``userscripts``
   Configure userscripts or subcommands to run at various :ref:`stages<experiment-steps>` of
   a payu submission. Inputs can be either script names (``some_script.sh``) or
   individual subcommands (``echo "some_data" > input.nml``, ``qsub
   some_script.sh``). Userscripts are run within the same PBS job as the model 
   execution unless the script starts a new PBS job. Userscripts therefore have
   the same compute, storage and network access as the model. The exceptions to 
   this are when ``payu setup`` is called directly, then the relevant userscripts 
   will run on the login node, and the ``sync`` userscript, which runs in the 
   ``sync`` job.

   Specific stages are defined below:

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

   ``error``
      User-defined command to be called if model does not run correctly and
      returns an error code. Useful for automatic error postmortem.
   
   ``sync``
      User-defined command to be called at the start of the ``sync`` PBS job. 
      This is useful for any post-processing before syncing files to a remote 
      archive. Note these scripts are only run if automatic syncing is enabled 
      or if payu sync is run manually.

``postscript``
   This is an older, less user-friendly, method to submit a script after ``payu`` 
   has completed all steps that might alter the output directory. e.g. collation.
   Unlike the ``userscripts``, it does not support user commands. These scripts 
   are always re-submitted via ``qsub``.

``sync`` 
   Sync archive to a remote directory using rsync. Make sure that the 
   configured path to sync output to, i.e. ``path``, is the correct location 
   before enabling automatic syncing or before running ``payu sync``.

   If postscript is also configured, the latest output and restart files will
   not be automatically synced after a run.

   ``enable`` (*Default:* ``False``):
      Controls whether or not a sync job is submitted either after the archive or 
      collation job, if collation is enabled.

   ``queue`` (*Default:* ``copyq``)
      PBS queue used to submit the sync job.

   ``walltime`` (*Default:* ``10:00:00``)
      Time required to run the job.

   ``mem`` (*Default:* ``2GB``)
      Memory required for the job. 

   ``ncpus`` (*Default:* ``1``)
      Number of ncpus required for the job.

   ``path``
      Destination path to sync archive outputs to. This must be a unique 
      absolute path for your experiment, otherwise, outputs will be 
      overwritten.

   ``restarts`` (*Default:* ``False``)
      Sync permanently archived restarts, which are determined by 
      ``restart_freq``.

   ``rsync_flags`` (*Default:* ``-vrltoD --safe-links``)
      Additional flags to add to rsync commands used for syncing files.

   ``exclude``
      Patterns to exclude from rsync commands. This is equivalent to rsync's 
      ``--exclude PATTERN``. This can be a single pattern or a list of
      patterns. If a pattern includes any special characters,
      e.g. ``.*+?|[]{}()``, it will need to be quoted. For example::
         
         exclude:
            - 'iceh.????-??-??.nc'
            - '*-IN-PROGRESS'

   ``exclude_uncollated`` (*Default:* ``True`` if collation is enabled)
      Flag to exclude uncollated files from being synced. This is equivalent 
      to adding ``--exclude *.nc.*``.

   ``extra_paths``
      List of ``glob`` patterns which match extra paths to sync to remote 
      archive. This can be a single pattern or a list of patterns. 
      Note that these paths will be protected against any local delete options.

   ``remove_local_files`` (*Default:* ``False``)
      Remove local files once they are successfully synced to the remote 
      archive. Files in protected paths will not be deleted. Protected paths 
      include the ``extra_paths`` (if defined), last output, the last saved 
      restart (determined by ``restart_freq``), and any subsequent restarts.
    
   ``remove_local_dirs`` (*Default:* ``False``)
      Remove local directories once a directory has been successfully synced. 
      This will delete any files in local directories that were excluded from
      syncing. Similarly to ``remove_local_files``, protected paths will not be 
      deleted.

   ``runlog`` (*Default:* ``True``)
      Create or update a bare git repository clone of the run history, called 
      ``git-runlog``, in the remote archive directory.

Experiment Tracking
-------------------

``runlog``
   Automatically commits changes to configuration files and manifests in the 
   *control directory* when the model runs. This creates a git runlog of the 
   history of the experiment.

   ``enable`` (*Default:* ``True``)
   Flag to enable/disable runlog.

``metadata``
   Generates and updates metadata files and unique experiment IDs (UUIDs). For more details, see 
   :ref:`usage-metadata`.

   ``enable`` (*Default:* ``True``)
      Flag to enable/disable creating/updating metadata files and UUIDs.
      If set to False, the experiment name used for archival is either the
      control directory name or the configured ``experiment`` name.

   ``model`` (*Default: The configured model value*)
      Model name used when generating metadata for new experiments.

Miscellaneous
=============

``restart``
   Specify the full path to a restart directory from which to start the run.
   This is known as a "warm start". This option has no effect if there is an
   existing restart directory in ``archive``, and so does not **have** to be
   removed for subsequent submissions.

``debug`` (*Default:* ``False``)
   Enable the debugger for any ``mpirun`` jobs. Equivalent to ``mpirun
   --debug``. At NCI this defaults to a Totalview session. This will probably
   only work for interactive sessions.

``mpi``
   Override default MPI module and add MPI command line arguments.

   ``runcmd`` (*Default:* ``mpirun``)
      Specify command to invoke MPI executables.

   ``modulepath``
      Set path for environment module to find and load MPI module.

   ``module``
      Override default MPI module version. Default is determined dynamically
      by inspecting the model executables. 

   ``flags``
      Set command line arguments (flags) to the ``mpirun`` call of the
      model. This setting supports both single lines and a list of input
      arguments. Example shown below::

         mpi:
            flags:
               - -mca mpi_preconnect_mpi 1   # Enable preconnecting
               - -mca mtl ^mxm               # Disable MXM acceleration
               - -mca coll ^fca              # Disable FCA acceleration


``mpirun`` (**Deprecated**)
   Replicates ``mpi`` ``flags`` above.

``env``
   Enable any environment variables required by ``mpirun`` during execution,
   such as ``OMPI_MCA_coll``. The following example below disables "matching
   transport layer" and "collective algorithm" components::

      env:
         OMPI_MCA_coll: ''
         OMPI_MCA_mtl: ''

``stacksize``
   Set the stacksize for each process in kiB. ``unlimited`` is also a valid
   setting (and typically required for many models).

   *Note:* ``unlimited`` *works without any issues, but explicit stacksize
   values may not be correctly communicated across compute nodes.*

``runspersub``
   Define the maximum number of runs per PBS job submit. The default is 1. 
   The actual number of runs per PBS submit will be the minimum of 
   ``runspersub`` and the total number of runs set with the ``-n`` 
   command-line flag. 

``repeat``
   Ignore any restart files and repeat the initial run upon resubmission. This
   is generally only used for testing purposes, such as bit reproducibility.

.. _configuring-modules:
``modules``
   Specify lists of environment modules and/or directories
   to load/use at the start of the PBS job, for example::

      modules:
         use:
            - /path/to/module/directory
         load:
            - netcdf-c-4.9.0
            - parallel-netcdf-1.12.3
            - xerces-c-3.2.3

   As environment modules can be used to determine model executable paths,
   the modules loaded are required to be unique. This means modules should be
   specified with a version, and modules of the same name and version
   should not be found in multiple module directories.
   If the modules require `module use` in order to be found, this command can also be run
   prior to `payu run` instead of listing the directory under the `use` option,
   e.g.::

      module use /path/to/module/directory
      payu run

``payu_minimum_version``
   Specify the minimum version of payu required to run the configuration.
   At the start of experiment setup, payu checks whether its current version
   is an earlier version, and if so, payu will refuse to run.
   This is useful for models that require features that are in later versions
   of payu.
   Note that this check will only run with payu versions later than `1.1.5`.
