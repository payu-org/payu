How OM2 driver is set up in payu (User-focused)
===============================================

Overview
--------

This document describes the structure and workflow of ACCESS-OM2 
model drivers in Payu, focusing on user-facing behaviour 
rather than implementation details.

The ACCESS-OM2 modelling system can be viewed as a three-level hierarchy: 
a base model class providing shared infrastructure, 
two sub-models (MOM5 and CICE5) implementing individual physical components, 
and the coupled ACCESS-OM2 model that orchestrates each component into 
a complete configuration.

.. _base_model:

Base Model Class
-----------------

The base model class provides a common interface and shared functionality 
for all specific models in payu. 
It initialises model attributes including model name, configurations, control flags, 
file paths, etc.

While setting up, the base model class:

- creates the work directory and subdirectories, including input, restart and output directories,  
- copies the configuration files from the control directory into work directory,
- makes symlinks to the executable, input, and restart files in the work directory,  
- updates the tracking manifests.  

At the archive stage, the base model class removes all symlinks created, 
empty files and directories from the work directory.

The directory structure is organised as:

::

    Control/                     # Control directory
    |---- archive/               # A symlink to archived model output and restarts
                                 # (usually linked to /scratch/${PROJECT}/${USER}/${Model}/${archive}/)
    |---- manifests/             # Model manifests directory
    |---- configuration files    # configuration files
    |---- metadata.yaml          # a metadata file
    |---- work/                  # Temporary working directory when model is running and before archive

In the archive directory, experiments are organised as:

::

    archive/
    |---- metadata.yaml
    |---- output00N/      # Output directories storing output and manifests of each run
    |---- restart00N/     # Directory storing restart files
    |---- payu_jobs/      # Directory storing job files of each run
            |---- 0         # Sub-directory named after run number


.. _mom5:

MOM5: Modular Ocean Model Version 5
------------------------------------

MOM5 driver is built based on the base model class in payu. 
It inherits from both `fms` (:ref:`fsm`) and `mixin` (:ref:`mixin`), adding extra features.

Configurations
~~~~~~~~~~~~~~

MOM5 requires configuration files: ``data_table``, ``diag_table``, ``field_table``, and ``input.nml``.

Optional configuration files are ``blob_diag_table``, ``mask_table``, and ``ocean_mask_table``.

Runtime Workflow
~~~~~~~~~~~~~~~~

MOM5 sets up the runtime by reading the ``ocean_solo_nml`` section in ``input.nml``. 
The runtime can be set in units of years, months, days, and seconds.

The time step is configured through ``dt_ocean`` in the ``ocean_solo_nml`` section of ``input.nml``.

.. _cice5:

CICE5: Sea-Ice Model Version 5 
------------------------------

CICE5 is a sea-ice model that inherits from the base CICE class 
and provides more detailed restart datetime configuration.

Configuration files
~~~~~~~~~~~~~~~~~~~

CICE5 requires configuration files: ``cice_in.nml``, ``input_ice.nml``, ``input_ice_gfdl.nml``, ``input_ice_monin.nml``.

Runtime Workflow
~~~~~~~~~~~~~~~~

The time step is set as ``dt`` (in seconds) in the ``setup_nml`` section of ``cice_in.nml``.
The number of time steps for the current run (``npt``) can also be configured in the same section.

The CICE base class tracks total runtime using ``dt``, ``npt``, and ``istep0`` 
(total timestep from the initial experiment) in the ``setup_nml`` section of ``cice_in.nml`` from the restart directory.

For CICE5, this runtime calculation is overridden with a non-implement pass, 
since runtime is now stored directly in NetCDF restart files instead of namelists.


ACCESS-OM2: Coupled Ocean–Sea Ice Model Version 2
--------------------------------------------------

ACCESS-OM2 is a coupled ocean–sea ice model consisting of MOM5 ocean model (see :ref:`mom5`), 
CICE5 sea ice model (see :ref:`cice5`), and a file-based atmosphere (YATM). 
All submodels are coupled through OASIS3-MCT v2.0.
It is built based on ACCESS-OM and AusCOM models originally developed by CSIRO (see 
`ACCESS-OM2 GitHub repository <https://github.com/ACCESS-NRI/ACCESS-OM2>`_ for more details).
In payu, the ACCESS-OM2 model driver is built on the base model class (see :ref:`base_model`).
 

Configuration files
~~~~~~~~~~~~~~~~~~~

ACCESS-OM2 requires ``accessom2.nml`` and ``namcouple`` to configure.

Runtime workflow
~~~~~~~~~~~~~~~~

ACCESS-OM2 delegates runtime configuration to each sub-model (MOM5 and CICE5) independently.

Override compared to base model class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ACCESS-OM2 overrides the standard work directory structure:

- work input path: ``${work_path}/INPUT``
- work restart path: ``${work_path}/RESTART``

During archiving, ACCESS-OM2 handles coupling by copying the ``o2i.nc`` file 
from the MOM5 work directory into the CICE5 restart directory.

Note: ACCESS-OM2 only performs setup and archive steps when used as a sub-model (not as a top-level model).


Other related model classes
---------------------------


.. _fms:

Flexible Modelling System (FMS)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
FMS is a framework that provides a common infrastructure for building 
climate models in payu.
It inherits from the base model class (see :ref:`base_model`) and 
provides FMS-specific functionality for setup, archive and collation.
FMS is used for MOM5 and MOM6 ocean model drivers in payu.

Directory Structure
^^^^^^^^^^^^^^^^^^^

The directory structure of an FMS model is organised as:

::
    
    work/                        # Work directory
    |---- INPUT/               # Input data directory
    |---- RESTART/             # Model restart directory

Archive Handling
^^^^^^^^^^^^^^^^

During the archive stage, the FMS model driver remove the ``work/INPUT`` directory,
and move restart files from ``work/RESTART`` directory into the ``archive/restart`` directory.


Collation Handling
^^^^^^^^^^^^^^^^^^

During the collation stage, the FMS model driver uses ``mppnccombine`` tools
to combine distributed restart files into a single NetCDF file.
A mapping between the full hashes of distributed tiles and the collated file is 
stored in the collate job file as ``collate_mapping``.

.. _mixin:

MomMixin
~~~~~~~~

MomMixin is a mixin class that adds specific functionality for 
MOM5 and MOM6 model drivers in payu.
It provideds common methods for handling calendar and datetime extraction from restart files.

MomMixin reads the calendar type from the first line of ``ocean_solo.res`` file.
The calendar type is mapped to the following calendars:

- ``1``: ``360_day`` — 12 months of exactly 30 days each,
- ``2``: ``julian`` — Julian calendar with leap years every 4 years,
- ``3``: ``proleptic_gregorian`` — Gregorian calendar extended backward,
  in time, with leap years every 4 years except for years divisible by
  100 but not by 400
- ``4``: ``noleap`` — 365-day calendar with no leap years,


MomMixin also extracts the restart datetime from the ``ocean_solo.res`` file, 
which is used for tracking runtime and configuring the next run.