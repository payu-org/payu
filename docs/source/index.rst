====
Payu
====

Current release: |version|

Payu is a workflow management tool for running numerical models in
supercomputing environments.

Payu was designed to allow users to start running climate models immediately,
without having to re-learn the nuances of countless runscripts across countless
models. Running a model like the MOM ocean model should only require a few
commands. 
First, create a new experiment directory::

   mkdir new_expt; cd new_expt

Next, :ref:`Create-experiment` or clone an existing released configuration and customise it as needed.
For example, to clone MOM5 test configuration::

   payu clone -b control -B master https://github.com/payu-org/bowl1.git bowl1
   cd bowl1

Then generate the executable file by following the 
`README instructions <https://github.com/payu-org/bowl1/blob/master/README.md>`_.

To run the model, simply execute::

   payu run

Currently, payu is very highly customised for users of NCI computing
environments, with a very strong dependence on `environment modules`_, the `PBS
scheduler`_, and an `MPI`_ runtime environment.  Using payu on other machines
will require, at a minimum, the installation of these services, as well as a
potentially significant modification of the codebase.

.. _`environment modules`: http://modules.sourceforge.net/
.. _`PBS scheduler`: http://en.wikipedia.org/wiki/Portable_Batch_System
.. _`MPI`: http://en.wikipedia.org/wiki/Message_Passing_Interface


User Guide
==========

Contents:

.. toctree::
   :maxdepth: 2

   install
   usage
   config
   manifests
   design


Support and Development
=======================

Support is coordinated through issues, discussions and pull requests on the GitHub repository https://github.com/payu-org/payu
