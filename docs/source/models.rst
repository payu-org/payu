.. _models:

==============
Model Drivers
==============

This section describes the model drivers that are currently supported by payu. 
Each model driver is built based on the common model driver class and customises the model-specific configuration and file paths.

The model driver is called in various steps of the payu experiment workflow (see :ref:`experiment-steps`).
It is responsible for the following common tasks:

- setting up the directory structures for the experiment,
- linking the model executable, input and restart files to the work directory,
- defining the required and optional configuration files for the model, which will be copied into the work directory,
- modifying the configuration files as required,
- carrying out model-specific checks before the run,
- identifying the files to be archived and where they should be archived.

There are two categories of model drivers: solo models and coupled models.
Coupled models contain multiple submodels, and each submodel is configured individually in the model driver. 



ACCESS-OM2 
============

Type: Coupled model

Submodels: 

- atmosphere (YATM), 
- ocean (MOM5), 
- sea ice (CICE5)

This section introduces necessary information of how ACCESS-OM2 model driver organises the workflow and file paths,
in the order of setup, running and archiving an experiment.


Setup
------

Configuration files
^^^^^^^^^^^^^^^^^^^

A table of the required and optional configuration files for each submodel is shown below. 

.. list-table:: Model Configuration Files
   :header-rows: 1

   * - Model
     - Required config files
     - Optional config files
   * - ACCESS-OM2
     - - accessom2.nml
       - namcouple
     - -
   * - YATM
     - - atm.nml
       - forcing.json
     - -
   * - MOM5
     - - data_table
       - diag_table
       - field_table
       - input.nml
     - - blob_diag_table
       - mask_table
       - ocean_mask_table
   * - CICE5
     - - cice_in.nml
       - input_ice.nml
       - input_ice_gfdl.nml
       - input_ice_monin.nml
     - -

Directory structure 
^^^^^^^^^^^^^^^^^^^^

An expected control directory structure for access-om2 is shown as below.
::
    
    access-om2/
    ├── accessom2.nml
    ├── atmosphere/
    │   ├── atm.nml
    │   └── forcing.json
    ├── ocean/
    │   ├── data_table
    │   ├── diag_table
    │   ├── field_table
    │   └── input.nml
    ├── ice/
    │   ├── cice_in.nml
    │   ├── input_ice_gfdl.nml
    │   ├── input_ice_monin.nml
    │   └── input_ice.nml
    └── manifests/
        ├── exe.yaml
        ├── input.yaml
        └── restart.yaml


Setting up work directory
^^^^^^^^^^^^^^^^^^^^^^^^^

The model driver will create a work directory with subdirectories for each submodel. 
The configuration files mentioned above will be copied into the corresponding subdirectories in the work directory, 
and the model driver will modify the configuration files as required.
The model executable, input and restart files will be linked into the work subdirectories.

The details vary between submodels and coupled model drivers.
In general, input, output and restart locations are defined for each submodel.
Input files are static files that are independent of the model run and restart files, if they are available.
Output files are the files that are generated during the model run, and will be archived after the run.
Restart files are the files that capture the model state at a particular time, 
and can be used to restart the model run from that time.


ACCESS-OM2
""""""""""

``accessom2_restart.nml`` is linked to the restart namelist file in the previous run, if it exists.
This file captures the forcing current date and experiment current date.
``namcouple`` is a configuration file for the OASIS coupler.
__FIX_ME__: provide more details about how the coupling configuration file works.
The input, output and restart file locations are defined as below:

.. list-table::
   :header-rows: 1

   * - File type
     - Location
   * - Input files
     - ``${WORK}/INPUT/``
   * - Restart files
     - ``${WORK}/RESTART/``



YATM
"""""""

The input files are linked to static data files from previous model outputs.
__FIX_ME__: provide more details about how ``forcing.json`` works.

The input, output and restart file locations are defined as below:

.. list-table::
   :header-rows: 1

   * - File type
     - Location
   * - Input files
     - ``${WORK}/atmosphere/INPUT/``



MOM5
"""""""

The input, output and restart file locations are defined as below:

.. list-table::
   :header-rows: 1

   * - File type
     - Location
   * - Input files
     - ``${WORK}/ocean/INPUT/``
   * - Output files
     - ``${WORK}/ocean/``
   * - Restart files
     - ``${WORK}/ocean/RESTART/``


CICE5
"""""""

The restart files are copied (instead of linked) into the work directory, from the previous run, if it exists.
This is because the CICE5 model will modify the restart files during the run, 
and we want to keep the original restart files unchanged for the previous runs. 
The input, output and restart file locations are defined as below:

.. list-table::
   :header-rows: 1

   * - File type
     - Location
   * - Input files
     - ``${WORK}/ice/RESTART/``
   * - Output files
     - ``${WORK}/ice/OUTPUT/``
   * - Restart files
     - ``${WORK}/ice/RESTART/``



Set model run length
^^^^^^^^^^^^^^^^^^^^

The model run length are set in the ``accessom2.nml`` configuration file.

__FIX_ME__: provide more details about how the run length is set in the namelist file.



Running
---------

ACCESS-OM2 requires three executables to run, each for the atmosphere, ocean and sea ice submodels.
The model driver reads the modules specified in the config file and use them for loading model executables.
A symlink is created for each executable inside the work directory, 
pointing to the actual executable file defined in the config file.
Users can specify the name of executable for each submodel in the config file.
An example of each executable name is shown below.

.. list-table::
   :header-rows: 1

   * - Submodel
     - Executable
   * - Atmosphere
     - ``yatm.exe``
   * - Ocean
     - ``mom5_access_om``
   * - Sea ice
     - ``cice_auscom_360x300_24x1_24p.exe``

During the model run, the output files of each submodel are stored under different subdirecoties of the work directory.

.. list-table::
   :header-rows: 1

   * - Submodel
     - File type: Store location during run
   * - Atmosphere
     - -
   * - Ocean
     - - Output files: ``${WORK}/ocean/``
       - Restart files: ``${WORK}/ocean/RESTART/``
   * - Sea ice
     - - Output files: ``${WORK}/ice/OUTPUT/``
       - Restart files: ``${WORK}/ice/RESTART/``

The current model time is tracked in file ${WORK}/atmosphere/log/matmxx.pe00000.log by key ``cur_exp-datetime``.

__ASK_AIDAN__: I am not sure if there is any model-specific checks.


Archive
-------

When the model run is completed and archive is set to true, 
the model driver will move files from the work directory to the archive directory 
(e.g., /scratch/${PROJECT}/${USER}/archive/${CONTROL-Branch-UUID}).
Meanwhile, the work directory and symlink are removed.
The table below shows the source files and their corresponding archive locations.

.. list-table::
   :header-rows: 1

   * - Submodel
     - File Source
     - Archive Location
   * - Global
     - - ``${WORK}/accessom2_restart.nml``
       - ``${WORK}/${submodel}/INPUT/``
     - - ``${ARCHIVE}/restart00N/accessom2_restart.nml``
       - Removed
   * - Atmosphere
     - - ``${WORK}/atmosphere/``
     - - ``${ARCHIVE}/output00N/atmosphere/``
   * - Ocean
     - - Output files in ``${WORK}/ocean/``
       - ``${WORK}/ocean/RESTART/``
     - - ``${ARCHIVE}/output00N/ocean/``
       - ``${ARCHIVE}/restart00N/ocean/``
   * - Sea ice
     - - ``${WORK}/ice/OUTPUT/``
       - ``${WORK}/ice/RESTART/``
     - - ``${ARCHIVE}/output00N/ice/``
       - ``${ARCHIVE}/restart00N/ice/``

ACCESS-OM3
============




ACCESS-ESM1.5 
==============





ACCESS-ESM1.6 
==============




MOM5
====




MOM6
====



UM model
========




CICE5
=====
