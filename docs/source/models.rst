.. _models:

==============
Model Drivers
==============

This section describes the model drivers that are currently supported by payu. 
Each model driver is based on the common model driver class and customises the model-specific configuration and file paths.

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

- Yet another data-driven atmosphere model (YATM). It keeps track of the current model time, 
  read current atmospheric forcing data and deliver it to the rest of the model via the coupler.
  Technical details and source code are available in the
  `libaccessom2 GitHub repository <https://github.com/ACCESS-NRI/libaccessom2>`_.
- Modular Ocean Model, version 5 (MOM5). Technical details about how to configure the model and 
  how the physics is modelled are available on the 
  `Modular Ocean Model website <https://mom-ocean.github.io>`_.
- Los Alamos Sea Ice Model, version 5 (CICE5). Please see the 
  `CICE5 user's guide <https://cesmcice.readthedocs.io/en/latest/>`_ 
  for more technical details and the physics of the model.

This section introduces necessary information of how the ACCESS-OM2 model driver organises the workflow and file paths,
in the order of setup, running and archiving an experiment.
Technical details about how to configure the ACCESS-OM2 model and how the physics 
is modelled are available on the 
`COSIMA website <https://cosima.org.au/index.php/models/access-om2/>`_.
Instructions  for running ACCESS-NRI supported ACCESS-OM2 configurations are also 
available on `ACCESS-Hive <https://docs.access-hive.org.au/models/run_a_model/run_access-om2/>`_.

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
     -
   * - YATM
     - - atm.nml
       - forcing.json
     -
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
     -

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
Please refer to the 
`OASIS documentation <https://oasis.cerfacs.fr/wp-content/uploads/sites/114/2021/02/GLOBC-TR-oasis3mct_UserGuide3.0_052015.pdf>`_ 
for more technical information.
The input and restart file locations are defined as below:

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

The file-based atmosphere is provided by `libaccessom2 <https://github.com/ACCESS-NRI/libaccessom2>`_
and configured through the ``forcing.json`` file.
Input files are linked to static data files from previous model outputs.

The input files are located as below:

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

The model run length is managed by `libaccessom2 <https://github.com/ACCESS-NRI/libaccessom2>`_ 
through the ``accessom2.nml`` configuration file.
In ``date_manager_nml`` section of ``accessom2.nml``, the run length is
configured in years, months, and seconds. 
Two of these values must be set to zero.


Running
---------

ACCESS-OM2 requires three executables to run, each for the atmosphere, ocean and sea ice submodels.
Users can specify the executable for each submodel in the configuration file. 
If a full path to an executable is specified, payu uses that executable directly. 
If only the excusable name is specified, payu loads the environment modules specified 
in the configuration file, and searches the paths provided by those modules for a matching executable..
A symlink is created for each executable inside the work directory, pointing to the actual 
executable file used for the model run.
An example of the executable names for each submodel is shown below.

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
     -
   * - Ocean
     - - Output files: ``${WORK}/ocean/``
       - Restart files: ``${WORK}/ocean/RESTART/``
   * - Sea ice
     - - Output files: ``${WORK}/ice/OUTPUT/``
       - Restart files: ``${WORK}/ice/RESTART/``

The current model time is tracked in file ``${WORK}/atmosphere/log/matmxx.pe00000.log`` by key ``cur_exp-datetime``.


Archive
-------

When the model run is completed and archive is set to true, 
the model driver will move files from the work directory to the archive directory 
(e.g., ``/scratch/${PROJECT}/${USER}/archive/${CONTROL-Branch-UUID}``).
Meanwhile, the work directory and symlink are removed.
For ACCESS-OM2-specific cases, payu also copies the ocean-to-ice coupler file ``o2i.nc`` 
from the ocean work directory to the sea-ice restart directory.
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


ACCESS-OM3 (AI-drafted)
============

Type: Coupled model

Submodels:

- Data Atmosphere Model (DATM). A prescribed atmospheric data model that reads atmospheric forcing data
  and passes it to the ocean and ice models via the coupler.
- Data Runoff Model (DROF). A data-driven runoff model that provides river discharge to the ocean model.
- Modular Ocean Model, version 6 (MOM). The ocean component uses MOM6, which is the next-generation ocean model
  from GFDL. Please see the `MOM6 documentation <https://github.com/GFDL/MOM6>`_ 
  for more technical details.
- Los Alamos Sea Ice Model, version 6 (CICE). The sea ice component uses CICE6. Please see the
  `CICE documentation <https://cice-consortium.github.io/cice/>`_ for more technical details.

ACCESS-OM3 uses the CESM CMEPS (Community Earth System Model Common Modeling Infrastructure Project System) framework,
which provides a standardized approach to coupled modeling. This section introduces necessary information about how the 
ACCESS-OM3 model driver organizes the workflow and file paths.
Technical details about how to configure the ACCESS-OM3 model are available on the **XX website**.

Setup
------

Configuration files
^^^^^^^^^^^^^^^^^^^

A table of the required and optional configuration files for the coupled model and each component is shown below.

.. list-table:: Model Configuration Files
   :header-rows: 1

   * - Component
     - Required config files
     - Optional config files
   * - Coupler/Driver
     - - drv_in
       - fd.yaml
       - nuopc.runconfig
       - nuopc.runseq
     -
   * - DATM
     - - datm_in
       - datm.streams.xml
     -
   * - DROF
     - - drof_in
       - drof.streams.xml
     -
   * - MOM
     - - input.nml
       - diag_table
     - - field_table
       - data_table
   * - CICE
     - - ice_in
     -

Directory structure
^^^^^^^^^^^^^^^^^^^^

An expected control directory structure for ACCESS-OM3 is shown as below.
::

    access-om3/
    ├── drv_in
    ├── fd.yaml
    ├── nuopc.runconfig
    ├── nuopc.runseq
    ├── datm_in
    ├── datm.streams.xml
    ├── drof_in
    ├── drof.streams.xml
    ├── input.nml
    ├── diag_table
    ├── ice_in
    └── INPUT/
        ├── (atmosphere forcing data)
        ├── (ocean input data)
        └── (ice input data)


Setting up work directory
^^^^^^^^^^^^^^^^^^^^^^^^^

The model driver will create a work directory with an INPUT subdirectory for input files.
Configuration files are copied into the work directory, and the model driver modifies them as required.
Model executables, input and restart files are linked into the work directory.

ACCESS-OM3 uses pointer files (rpointer.*) to track restart files for each component.
These pointer files are automatically managed by the CMEPS coupler framework.
The input and restart file locations are defined as below:

.. list-table::
   :header-rows: 1

   * - File type
     - Location
   * - Input files
     - ``${WORK}/INPUT/``
   * - Restart files
     - Tracked via rpointer files (``rpointer.cpl``, ``rpointer.ocn``, ``rpointer.ice``, etc.)
   * - Additional restart files
     - ``${WORK}/RESTART/``

Set model run length
^^^^^^^^^^^^^^^^^^^^

The model run length is configured in the ``nuopc.runconfig`` file through the
``ALLCOMP_attributes`` section. The run length is specified using the ``stop_option`` 
and ``stop_n`` parameters, which define the stop condition (e.g., ndays, nsteps, newyear).


Running
---------

ACCESS-OM3 requires one executable (the CESM driver) that manages all components.
Users can specify the executable in the configuration file.
If a full path to an executable is specified, payu uses that executable directly.
If only the executable name is specified, payu loads the environment modules specified
in the configuration file and searches for a matching executable.

The CMEPS coupler automatically manages the exchange of information between components
through the coupling timestep specified in the run sequence (nuopc.runseq).

The current model time is tracked in the file ``${WORK}/log/med.log`` by the CMEPS coupler.
The CMEPS system writes timing and progress information to the log directory.


Archive
-------

When the model run is completed and archive is set to true,
the model driver will move files from the work directory to the archive directory.
The restart pointer files are copied (rather than symlinked) to ensure proper restart functionality.
The table below shows the source files and their corresponding archive locations.

.. list-table::
   :header-rows: 1

   * - Component
     - File Source
     - Archive Location
   * - Global
     - ``${WORK}/*.log``
       ``${WORK}/timing/``
     - ``${ARCHIVE}/output00N/``
   * - Restart
     - ``${WORK}/rpointer.*``
     - ``${ARCHIVE}/restart00N/``


ACCESS-ESM1.5 (AI-drafted)
==============

Type: Coupled model

Submodels:

- Unified Model (UM). The atmospheric component. The UM is a flexible modelling system capable of representing
  weather and climate at a wide range of scales. Technical details are available on the
  `UK Met Office UM Documentation <https://code.metoffice.gov.uk/doc/um/>`_.
- Modular Ocean Model, version 5 (MOM5). The ocean component. Please see the
  `Modular Ocean Model website <https://mom-ocean.github.io>`_ for technical details.
- Los Alamos Sea Ice Model, version 4 (CICE). The sea ice component. Please see the
  `CICE documentation <https://cice-consortium.github.io/cice/>`_ for more technical details.

ACCESS-ESM1.5 is a fully-coupled global climate model that integrates a spectral atmospheric model (UM) with
an ocean model (MOM5) and a sea ice model (CICE). The components communicate through the OASIS coupler.
This section introduces necessary information about how the ACCESS-ESM1.5 model driver organizes the workflow
and file paths. Technical details about how to configure the ACCESS-ESM1.5 model and how the physics is
modelled are available on the `ACCESS website <https://www.access-nri.org.au/models/earth-system-model-esm//>`_.

Setup
------

Configuration files
^^^^^^^^^^^^^^^^^^^

A table of the required and optional configuration files for each component is shown below.

.. list-table:: Model Configuration Files
   :header-rows: 1

   * - Component
     - Required config files
     - Optional config files
   * - ACCESS-ESM1.5
     - - oasis_in (UM)
       - namcouple
     -
   * - UM
     - - errflag
       - hnlist
       - ihist
       - namelists
       - prefix.PRESM_A
       - STASHC
       - UAFILES_A
       - UAFLDS_A
       - cable.nml
       - um_env.yaml
     - - input_atm.nml
       - parexe
   * - MOM5
     - - data_table
       - diag_table
       - field_table
       - input.nml
     - - blob_diag_table
       - mask_table
       - ocean_mask_table
   * - CICE
     - - cice_in.nml
       - input_ice.nml
     - - input_ice_gfdl.nml
       - input_ice_monin.nml
       - restart_date.nml

Directory structure
^^^^^^^^^^^^^^^^^^^^

An expected control directory structure for ACCESS-ESM1.5 is shown as below.
::

    access-esm1.5/
    ├── atm/
    │   ├── errflag
    │   ├── hnlist
    │   ├── ihist
    │   ├── namelists
    │   ├── prefix.PRESM_A
    │   ├── STASHC
    │   ├── UAFILES_A
    │   ├── UAFLDS_A
    │   ├── cable.nml
    │   └── um_env.yaml
    ├── ocean/
    │   ├── data_table
    │   ├── diag_table
    │   ├── field_table
    │   └── input.nml
    ├── ice/
    │   ├── cice_in.nml
    │   ├── input_ice.nml
    │   ├── input_ice_gfdl.nml
    │   ├── input_ice_monin.nml
    │   └── restart_date.nml
    ├── namcouple
    └── manifests/
        ├── exe.yaml
        ├── input.yaml
        └── restart.yaml


Setting up work directory
^^^^^^^^^^^^^^^^^^^^^^^^^

The model driver will create a work directory with subdirectories for each component.
Configuration files are copied into the corresponding subdirectories in the work directory,
and the model driver modifies them as required.
The model executable, input and restart files are linked into the work subdirectories.

For CICE in ACCESS-ESM1.5, restart files are handled specifically because the model writes its own
restart information. The coupler file ``o2i.nc`` (ocean-to-ice) is linked from the ocean work
directory to the ice restart directory.

The input and restart file locations are defined as below:

.. list-table::
   :header-rows: 1

   * - Component
     - File type
     - Location
   * - UM
     - Input files
     - ``${WORK}/atm/INPUT/``
   * - MOM5
     - Input files
     - ``${WORK}/ocean/INPUT/``
   * -
     - Output files
     - ``${WORK}/ocean/``
   * -
     - Restart files
     - ``${WORK}/ocean/RESTART/``
   * - CICE
     - Input/Restart files
     - ``${WORK}/ice/RESTART/``
   * -
     - Output files
     - ``${WORK}/ice/OUTPUT/``

Set model run length
^^^^^^^^^^^^^^^^^^^^

The model run length is configured through the CICE coupling namelist (``input_ice.nml``).
The run length is specified in the ``coupling`` section using the ``runtime`` field,
which is specified in seconds.


Running
---------

ACCESS-ESM1.5 requires three executables to run: one for the atmosphere (UM), one for the ocean (MOM5),
and one for the sea ice (CICE). Users can specify the executable for each component in the configuration file.
If a full path to an executable is specified, payu uses that executable directly.
If only the executable name is specified, payu loads the environment modules specified
in the configuration file and searches for a matching executable.

The OASIS coupler handles the communication between the three components and manages the model timing.

During the model run, the output files of each component are stored under different subdirectories:

.. list-table::
   :header-rows: 1

   * - Component
     - Output Location
   * - Atmosphere
     - Standard output and log files in work directory
   * - Ocean
     - ``${WORK}/ocean/`` for output, ``${WORK}/ocean/RESTART/`` for restarts
   * - Sea ice
     - ``${WORK}/ice/OUTPUT/`` for output, ``${WORK}/ice/RESTART/`` for restarts


Archive
-------

When the model run is completed and archive is set to true,
the model driver will move files from the work directory to the archive directory.
For ACCESS-ESM1.5, the ocean-to-ice coupler file ``o2i.nc`` is copied from the ocean work
directory to the sea-ice restart directory before archiving.
The table below shows the source files and their corresponding archive locations.

.. list-table::
   :header-rows: 1

   * - Component
     - File Source
     - Archive Location
   * - Atmosphere
     - ``${WORK}/atm/``
     - ``${ARCHIVE}/output00N/atm/``
   * - Ocean
     - Output files in ``${WORK}/ocean/``
       ``${WORK}/ocean/RESTART/``
     - ``${ARCHIVE}/output00N/ocean/``
       ``${ARCHIVE}/restart00N/ocean/``
   * - Sea ice
     - ``${WORK}/ice/OUTPUT/``
       ``${WORK}/ice/RESTART/``
     - ``${ARCHIVE}/output00N/ice/``
       ``${ARCHIVE}/restart00N/ice/``


ACCESS-ESM1.6 (AI-drafted)
==============

Type: Coupled model

Submodels:

- Unified Model (UM). The atmospheric component with improved physics compared to ACCESS-ESM1.5.
  Technical details are available on the `UK Met Office UM Documentation <https://code.metoffice.gov.uk/doc/um/>`_.
- Modular Ocean Model (MOM). The ocean component. Can use MOM5 or MOM6 depending on configuration.
  Please see the relevant `Modular Ocean Model documentation <https://mom-ocean.github.io>`_ for technical details.
- Los Alamos Sea Ice Model (CICE). The sea ice component can use CICE4 or CICE5. Please see the
  `CICE documentation <https://cice-consortium.github.io/cice/>`_ for more technical details.

ACCESS-ESM1.6 is an improved version of ACCESS-ESM1.5 with updated atmospheric physics, optional CICE5 support,
and support for MOM6 as an optional ocean model component. The components communicate through the OASIS coupler.
This section introduces necessary information about how the ACCESS-ESM1.6 model driver organizes the workflow
and file paths. Technical details about how to configure the ACCESS-ESM1.6 model are available on the
**XX website**.

Setup
------

Configuration files
^^^^^^^^^^^^^^^^^^^

A table of the required and optional configuration files for each component is shown below.

.. list-table:: Model Configuration Files
   :header-rows: 1

   * - Component
     - Required config files
     - Optional config files
   * - ACCESS-ESM1.6
     - - namcouple
     -
   * - UM
     - - errflag
       - hnlist
       - ihist
       - namelists
       - prefix.PRESM_A
       - STASHC
       - UAFILES_A
       - UAFLDS_A
       - cable.nml
       - um_env.yaml
     - - input_atm.nml
       - parexe
       - pft_params.nml
       - soil.nml
   * - MOM5
     - - data_table
       - diag_table
       - field_table
       - input.nml
     - - blob_diag_table
       - mask_table
       - ocean_mask_table
   * - MOM6
     - - input.nml
       - diag_table
     - - field_table
       - data_table
   * - CICE4
     - - cice_in.nml
       - input_ice.nml
     - - input_ice_gfdl.nml
       - input_ice_monin.nml
       - restart_date.nml
   * - CICE5
     - - cice_in.nml
       - input_ice.nml
     -

Directory structure
^^^^^^^^^^^^^^^^^^^^

An expected control directory structure for ACCESS-ESM1.6 is shown as below.
::

    access-esm1.6/
    ├── atm/
    │   ├── errflag
    │   ├── hnlist
    │   ├── ihist
    │   ├── namelists
    │   ├── prefix.PRESM_A
    │   ├── STASHC
    │   ├── UAFILES_A
    │   ├── UAFLDS_A
    │   ├── cable.nml
    │   ├── um_env.yaml
    │   ├── pft_params.nml
    │   └── soil.nml
    ├── ocean/
    │   ├── data_table
    │   ├── diag_table
    │   ├── field_table
    │   └── input.nml
    ├── ice/
    │   ├── cice_in.nml
    │   └── input_ice.nml
    ├── namcouple
    └── manifests/
        ├── exe.yaml
        ├── input.yaml
        └── restart.yaml


Setting up work directory
^^^^^^^^^^^^^^^^^^^^^^^^^

The model driver will create a work directory with subdirectories for each component.
Configuration files are copied into the corresponding subdirectories in the work directory,
and the model driver modifies them as required.
The model executable, input and restart files are linked into the work subdirectories.

ACCESS-ESM1.6 includes improvements for CICE5 support. Unlike ACCESS-OM2, CICE5 inputs are not copied
but symlinked to support efficient restart handling. The coupler file ``o2i.nc`` (ocean-to-ice) is linked
from the ocean work directory to the ice restart directory.

The input and restart file locations are defined as below:

.. list-table::
   :header-rows: 1

   * - Component
     - File type
     - Location
   * - UM
     - Input files
     - ``${WORK}/atm/INPUT/``
   * - MOM (MOM5/MOM6)
     - Input files
     - ``${WORK}/ocean/INPUT/``
   * -
     - Output files
     - ``${WORK}/ocean/``
   * -
     - Restart files
     - ``${WORK}/ocean/RESTART/``
   * - CICE (CICE4/CICE5)
     - Input/Restart files
     - ``${WORK}/ice/RESTART/``
   * -
     - Output files
     - ``${WORK}/ice/OUTPUT/``

Set model run length
^^^^^^^^^^^^^^^^^^^^

The model run length is configured through the CICE coupling namelist (``input_ice.nml``).
The run length is specified in the ``coupling`` section using the ``runtime`` field,
which is specified in seconds.


Running
---------

ACCESS-ESM1.6 requires three executables to run: one for the atmosphere (UM), one for the ocean (MOM),
and one for the sea ice (CICE). Users can specify the executable for each component in the configuration file.
If a full path to an executable is specified, payu uses that executable directly.
If only the executable name is specified, payu loads the environment modules specified
in the configuration file and searches for a matching executable.

The OASIS coupler handles the communication between the three components and manages the model timing.

During the model run, the output files of each component are stored under different subdirectories:

.. list-table::
   :header-rows: 1

   * - Component
     - Output Location
   * - Atmosphere
     - Standard output and log files in work directory
   * - Ocean
     - ``${WORK}/ocean/`` for output, ``${WORK}/ocean/RESTART/`` for restarts
   * - Sea ice
     - ``${WORK}/ice/OUTPUT/`` for output, ``${WORK}/ice/RESTART/`` for restarts


Archive
-------

When the model run is completed and archive is set to true,
the model driver will move files from the work directory to the archive directory.
For ACCESS-ESM1.6, the ocean-to-ice coupler file ``o2i.nc`` is copied from the ocean work
directory to the sea-ice restart directory before archiving.
The table below shows the source files and their corresponding archive locations.

.. list-table::
   :header-rows: 1

   * - Component
     - File Source
     - Archive Location
   * - Atmosphere
     - ``${WORK}/atm/``
     - ``${ARCHIVE}/output00N/atm/``
   * - Ocean
     - Output files in ``${WORK}/ocean/``
       ``${WORK}/ocean/RESTART/``
     - ``${ARCHIVE}/output00N/ocean/``
       ``${ARCHIVE}/restart00N/ocean/``
   * - Sea ice
     - ``${WORK}/ice/OUTPUT/``
       ``${WORK}/ice/RESTART/``
     - ``${ARCHIVE}/output00N/ice/``
       ``${ARCHIVE}/restart00N/ice/``





MOM6
====



UM model
========



