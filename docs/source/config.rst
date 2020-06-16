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
   laboratory's ``input`` directory::

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

``laboratory`` (*Default:* ``/scratch/${PROJECT}/${USER}/${MODEL}``)
   The top-level directory for the model laboratory, where the codebase, model
   executables, input fields, running jobs, and archived output are stored.

``control`` (*Default: current directory*)
   The control path for the experiment. The default setting is the path of the
   current working directory.

``experiment`` (*Default: current directory*)
   The experiment name used for archival. The default setting uses the
   ``control`` directory name.


Manifests
---------

payu automatically generates and updates manifest files. See :ref:`manifests`
section for details.

``reproduce``
      These options allow fine-grained control of manifest checking to enable
      reproducible experiments. The default value is the value of the global
      ``reproduce`` flag, which is set using a command line argument and
      defaults to *False*. These options **override** the global ``reproduce``
      flag. If set to *True* payu will refuse to run if the hashes in the
      relevant manifest do not match.

      ``exe`` (*Default: global reproduce flag*)
            Enforce executable reproducibility. If set to *True* will refuse to
            run if hashes do not match.

      ``input`` (*Default: global reproduce flag*)
            Enforce input file reproducibility. If set to *True* will refuse to
            run if hashes do no match. Will not search for any new files.

      ``restart`` (*Default: global reproduce flag*)
            Enforce restart file reproducibility.

``scaninputs`` (*Default: True*)
      Scan input directories for new files. Set to *False* when reproduce input
      is *True*.

      If a manifest file is complete and it is desirable to not add spurious
      files to the manifest but allow existing files to change, setting this
      option to *False* would allow that behaviour.

``ignore`` (*Default: .\**):
      List of ``glob`` patterns which match files to ignore when scanning input
      directories. This is an array, so multiple patterns can be specified on
      multiple lines. The default is *.\** which ignores all hidden files on a
      POSIX filesystem.


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


Postprocessing
--------------

``collate`` (*Default:* ``True``)
   Controls whether or not a collation job is submitted after model execution.

   This is typically ``True``, although individual model drivers will often set
   the default value to ``False`` if collation is unnecessary.

   See above for specific ``collate`` options.

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

   ``error``
      User-defined command to be called if model does not run correctly and
      returns an error code. Useful for automatic error postmortem.

``postscript``
   This is an older, less user-friendly, method to submit a script after ``payu
   collate`` has completed. Unlike the ``userscripts``, it does not support
   user commands. These scripts are always re-submitted via ``qsub``.


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
