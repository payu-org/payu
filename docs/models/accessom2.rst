.. _ACCESS-OM2_model_driver:

============
ACCESS-OM2 model driver overview
============

This section describes the ACCESS-OM2 model driver for Payu, 
which provides the necessary customisations to run experiments.

Class setup
===========================

To define a new model driver, a class is created as follows::

    from payu.models.model import Model

    class AccessOm2(Model):

This class inherits from the base ``Model`` class, and can override default configuration and path settings.


Methods
===========================

Initialisation
---------------------

The ``__init__`` method initialises the model driver and defines
model-specific attributes such as the model type and configuration files::

    super(AccessOm2, self).__init__(expt, name, config)
    self.model_type = 'access-om2'
    self.config_files = ['accessom2.nml', 'namcouple']


Setup
---------------------

The ``setup`` method is only called when ACCESS-OM2 is used as a submodule (not a top-level model):

    super(AccessOm2, self).setup()


Specify path names
---------------------

Before applying the ACCESS-OM2 customisations, we need to run the standard implementation of ``set_model_pathnames()``::
    
    super(AccessOm2, self).set_model_pathnames()

Then we can override some path names for ACCESS-OM2, including:

- ``work_path``: path to the working directory for the model.
    
- ``control_path``: path to the control directory for the model.

- ``work_input_path``: path to the input directory within the working directory.

- ``work_restart_path``: path to the restart directory within the working directory.

Similarly, input and output paths can also be customised after calling the base methods, if needed::

    super(AccessOm2, self).set_input_paths()
    super(AccessOm2, self).set_model_output_paths()

In ACCESS-OM2, the following paths are customised:

- ``output_path``: path to output directory, e.g., ``self.expt.output_path``.

- ``restart_path``: path to restart directory, e.g., ``self.expt.restart_path``.

- ``prior_output_path``: path to the prior output directory, e.g., ``self.expt.prior_output_path``.

- ``prior_restart_path``: path to the prior restart directory, e.g., ``self.expt.prior_restart_path``.


Archive
---------------------

The ``archive`` method aims to move the model output and restart files from working directory to archive directory
after a successful run. This method is only called when ACCESS-OM2 is running as a submodule. 

When ACCESS-OM2 is a top-level model, the ``archive`` method instead locate ``cice5`` and ``mom`` submodels.
Then it copies the ocean-to-ice coupling file (``o2i.nc``) from the ``mom`` working directory into
the ``cice5`` restart directory.


Collate
---------------------

The ``collate`` method is intended to collate the model restart tiles in the archive directory.
In ACCESS-OM2 top-level models, this is not implemented so a ``pass`` is used to skip this step.


Get restart datetime
---------------------

The ``get_restart_datetime`` method extracts the restart timestamp from
restart files and returns a ``cftime.datetime`` object.
In ACCESS-OM2, this is based on the MOM ocean model only::

    self.get_restart_datetime_using_submodel(restart_path, ['mom'])


Get current experiment datetime
---------------------

``get_cur_expt_time`` is useful when monitoring the current experiment time via ``payu status``. 
In ACCESS-OM2, it reads the latest ``cur_exp-datetime`` entry from the
``work/atmosphere/log/matmxx.pe00000.log``, 
and returns it as a ``cftime.datetime`` object using the format of ``%Y-%m-%dT%H:%M:%S``.