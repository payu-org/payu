====
Payu
====

Current release: |version|

Payu is a workflow management tool for running numerical models in
supercomputing environments.

Payu was designed to allow users to start running climate models immediately,
without having to re-learn the nuances of countless runscripts across countless
models. Running a model like the MOM ocean model should only require a few
commands::

   mkdir new_expt; cd new_expt
   payu init -m mom
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

* Mailing List: https://groups.google.com/group/payu-climate
* Source: https://github.com/marshallward/payu
