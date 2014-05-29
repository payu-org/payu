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

``queue:`` (*Default:* ``normal``)
   The PBS queue to submit your job. Equivalent to ``qsub -q QUEUE``.

``project:`` (*Default:* ``$PROJECT``)
   The project from which to submit the model (and deduct CPU hours).
   Equivalent to ``qsub -P PROJECT``. The default value is the current
   ``$PROJECT`` environment variable. Note that ``project`` is used as part of
   the default configuration for various laboratory filepaths.

``jobname:`` (*Default: Control directory name*)
   The name of the job as it appears in the PBS queue. If no name is provided,
   then it uses the name of the experiment's control directory.

``ncpus:``
   The number of CPUs used during model simulation. Usually equivalent to
   ``qsub -l ncpus=N``. This is the number passed on to ``mpirun`` during model
   execution.

   Although it usually matches the CPU request, the actual request
   may be larger if ``npernode`` is being used.

``npernode:``
   The number of CPUs used per node. This settings is passed on to ``mpirun``
   during model execution. In most cases, this is converted into an
   equivalent ``npersocket`` configuration.

   This setting may be needed in cases where a node is unable to efficiently
   use all of its CPUs, such as performance issues related to NUMA.

``mem:`` (*Default: 31GiB per node*)
   Amount of memory required for the job. Equivalent to ``qsub -l mem=MEM``.
   The default value requests (almost) all of the nodes' memory for jobs using
   multiple nodes.

   In general, it is good practice to keep this number as low
   as possible.

``walltime:``
   The amount of time required to run an individual job, specified as
   ``hh:mm:ss``. Equivalent to ``qsub -l walltime=TIME``. Jobs with shorter
   walltimes will generally run before jobs with longer walltimes.

``priority:``
   Job priority setting. Equivalent to ``qsub -p PRIORITY``.

``qsub_flags:``
   This is a generic configuration marker for any unsupported qsub flags. It
   will appear be used in any payu calls to ``qsub``.


Collation
---------

Collation scheduling can be configured independently of model runs. Currently,
all collation jobs are single CPU jobs and are not parallelised.

``collate_queue:`` (*Default:* ``copyq``)
   PBS queue used for collation jobs

``collate_walltime:``
   Time required for output collation

``collate_mem:``
   Memory required for output collation


Model
-----

These settings are part of general model execution, including OpenMPI
configuration.

``model:`` (*Default: Parent directory of control directory*)
   The model (or coupled model configuration) used in the experiment. This
   model name must be one of the supported models shown in ``payu list``.

   If no model name is provided, then it will attempt to infer the model based
   on the parent directory of the experiment. For example, if we run our
   experiment in ``~/mom/bowl1``, then ``mom`` will be used as the model type.
   However, it is generally better to specify the model type.

``submodels:``
   If one is running a coupled model containing several submodels, then each
   model is configured individually within a ``submodel`` namespace, such as in
   the example below.

   TODO

``exe:``

``input:``

``shortpath:`` (*Default:* ``/short/${PROJECT}``)
   The top-level directory for general scratch space, where laboratories and
   model output are stored. Users who run from multiple projects will generally
   want to set this explicitly.

``user:`` (*Default:* ``${USER}``)
   The username used to construct the laboratory paths. It is generally
   recommended that laboratories be stored under username, so this setting is
   usually not necessary (nor recommended).

``laboratory:`` (*Default:* ``/short/${PROJECT}/${USER}/${MODEL}``)
   The top-level directory for the model laboratory, where the codebase, model
   executables, input fields, running jobs, and archived output are stored.
   This is generally not configured.

``control:`` (*Default: current directory*)
   The control path for the experiment. The default setting is the current
   working directory, and is generally not configured.

``experiment:``

``restart_freq:``


Postprocessing
==============

``collate:``

``userscripts``

``postscripts``


Miscellaneous
=============

``debug``

``mpirun``

``ompi``

``stacksize``

``repeat``


Deprecated settings
===================

``core2iaf``
