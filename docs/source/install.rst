.. _install:

============
Installation
============

Payu is currently only supported for users on the NCI computing systems, such
as Raijin. If you wish to use payu on other systems, see the notes at the end
of this document.


NCI Users
=========

If you are an NCI user and a member of the v45 group, then payu can be loaded
from its environment module::

   module use /projects/v45/modules
   module load payu

If you do not have access to v45, then you can install it locally from the
latest codebase::

   git clone https://github.com/marshallward/payu
   cd payu
   python setup.py install --user

Payu depends on the following modules, which may need to be installed
separately if you are not using the environment modules:

   * f90nml_
   * PyYAML_

.. _f90nml: https://pypi.python.org/pypi/f90nml
.. _PyYAML: https://pypi.python.org/pypi/PyYAML


General Use
===========

Payu is not supported for general use, and it would be a tremendous surprise if
it even worked on other machines. In particular, the following services are
presumed to be available:

   * `Environment Modules`_: Not only do we assume support for environment
     modules, but we also assume the existence of certain modules, such as
     an OpenMPI module and particular versions of Python.

   * `PBS Scheduler`_: Payu relies on executables that are provided with most
     PBS implementations, such as Torque or PBSPro. Most of the argument flags
     are currently based around PBSPro conventions.

   * `MPI`_: Jobs are submitted via ``mpirun`` and most of the argument flags
     are based on the OpenMPI implementation. We also rely on Raijin's internal
     preprocessing scripts for a few tasks.

There are also some additional assumptions based on the architecture of Raijin.

Despite these rather strict requirements, there is opportunity for generalising
payu for other platforms, such as through new drivers for alternative
schedulers and parallelisation platforms. Please contact the `mailing list`_ if
you are interested in porting payu to your machine.

.. _`Environment Modules`: http://modules.sourceforge.net/
.. _`PBS scheduler`: http://en.wikipedia.org/wiki/Portable_Batch_System
.. _`MPI`: http://en.wikipedia.org/wiki/Message_Passing_Interface
.. _`mailing list`: https://groups.google.com/group/payu-climate
