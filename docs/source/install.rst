.. _install:

============
Installation
============

Payu is currently only supported for users on the NCI computing systems. If you 
wish to use payu on other systems, see the notes at the end of this document.


NCI Users
=========

Payu is made available for users of NCI HPC systems in `conda` environments.

The ACCESS-Hive `ACCESS-OM models`_ documentation contains instructions for
using ACCESS-NRI supported conda environments.

`CLEX CMS`_ also provides `conda environments`_ that support payu.

Local installation
------------------

Using `pip`_ it is possible to install payu from PyPI::

   pip install payu --user

If you want to use the latest version of payu, then you can install directly
from the repository::

   pip install payu@git+https://github.com/payu-org/payu --user
   
or clone the codebase and install from there::

   git clone https://github.com/payu-org/payu
   cd payu
   pip install . --user


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
     are based on the OpenMPI implementation. 

There are also some additional assumptions based on the architecture of the NCI
HPC facilities.

Despite these rather strict requirements, there is opportunity for generalising
payu for other platforms, such as through new drivers for alternative
schedulers and parallelisation platforms. Please create a `GitHub Issue`_ if
you are interested in porting payu to your machine.

.. _`Environment Modules`: http://modules.sourceforge.net/
.. _`PBS scheduler`: http://en.wikipedia.org/wiki/Portable_Batch_System
.. _`MPI`: http://en.wikipedia.org/wiki/Message_Passing_Interface
.. _`GitHub Issue`: https://github.com/payu-org/payu/issues
.. _`pip`: https://pip.pypa.io/en/stable/cli/pip_install
.. _`ACCESS-OM models`: https://access-hive.org.au/models/run-a-model/run-access-om/#model-specific-prerequisites
.. _`conda environments`: https://github.com/coecms/access-esm#quickstart-guide
.. _`CLEX CMS`: https://github.com/coecms
