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

+------------------------+--------------------------------------+----------------------------------+
| Model                  | Required                             | Optional                         |
|                        | config files                         | config files                     |
+========================+======================================+==================================+
| ACCESS-OM2             | accessom2.nml                        | -                                |
|                        | namcouple                            |                                  |
+------------------------+--------------------------------------+----------------------------------+
| YATM                   | atm.nml,                             | -                                |
|                        | forcing.json                         |                                  |
+------------------------+--------------------------------------+----------------------------------+
| MOM5                   | data_table,                          | blob_diag_table,                 |
|                        | diag_table,                          | mask_table,                      |
|                        | field_table,                         | ocean_mask_table                 |
|                        | input.nml                            |                                  |
+------------------------+--------------------------------------+----------------------------------+
| CICE5                  | cice_in.nml,                         | -                                |
|                        | input_ice.nml,                       |                                  |
|                        | input_ice_gfdl.nml,                  |                                  |
|                        | input_ice_monin.nml                  |                                  |
+------------------------+--------------------------------------+----------------------------------+

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

+------------------------+--------------------------------------+
| File type              | Location                             |
+========================+======================================+
| Input files            | ``${WORK}/INPUT/``                   |
+------------------------+--------------------------------------+
| Restart files          | ``${WORK}/RESTART/``                 |
+------------------------+--------------------------------------+


YATM
"""""""

The input files are linked to static data files from previous model outputs.
__FIX_ME__: provide more details about how ``forcing.json`` works.

The input, output and restart file locations are defined as below:

+------------------------+--------------------------------------+
| File type              | Location                             |
+========================+======================================+
| Input files            | ``${WORK}/atmosphere/INPUT/``        |
+------------------------+--------------------------------------+


MOM5
"""""""

The input, output and restart file locations are defined as below:

+------------------------+--------------------------------------+
| File type              | Location                             |
+========================+======================================+
| Input files            | ``${WORK}/ocean/INPUT/``             |
+------------------------+--------------------------------------+
| Output files           | ``${WORK}/ocean/``                   |
+------------------------+--------------------------------------+
| Restart files          | ``${WORK}/ocean/RESTART/``           |
+------------------------+--------------------------------------+


CICE5
"""""""

The restart files are copied (instead of linked) into the work directory, from the previous run, if it exists.
This is because the CICE5 model will modify the restart files during the run, 
and we want to keep the original restart files unchanged for the previous runs. 
The input, output and restart file locations are defined as below:

+------------------------+--------------------------------------+
| File type              | Location                             |
+========================+======================================+
| Input files            | ``${WORK}/ice/RESTART/``             |
+------------------------+--------------------------------------+
| Output files           | ``${WORK}/ice/OUTPUT/``              |
+------------------------+--------------------------------------+
| Restart files          | ``${WORK}/ice/RESTART/``             |
+------------------------+--------------------------------------+




Set model run length
^^^^^^^^^^^^^^^^^^^^

The model run length are set in the ``accessom2.nml`` configuration file.

__FIX_ME__: provide more details about how the run length is set in the namelist file.



Running
---------

ACCESS-OM2 requires three executables to run, each for the atmosphere, ocean and sea ice submodels.



- multiple exe and links

- model-specific checks

- where files get saved during the run

- how current model time is tracked



Archive
-------

- what files get archived and where


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
