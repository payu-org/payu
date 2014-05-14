====
Payu
====

Payu is a climate model workflow management tool for supercomputing
environments.

Payu is currently only configured for use on computing clusters maintained by
NCI (National Computing Infrastructure) in Australia.


Usage
=====

Installation
------------

If you have access to the ``v45`` project on ``raijin``, then add the ``v45``
modules to your environment and load the ``payu`` module::

   module use /projects/v45/modules
   module load payu

You may want to include these lines in your ``.login`` (for ``tcsh``) or
``.profile`` (for bash) scripts.

If you do not have access to ``v45``, then payu can be installed locally::

   python setup.py install --user

Local installations will also require the installation of the f90nml_ and
PyYAML_ packages.


.. _f90nml: https://pypi.python.org/pypi/f90nml
.. _PyYAML: https://pypi.python.org/pypi/PyYAML


Model Initialization
--------------------

To see a list of supported climate models, type::

   payu list

While not currently supported, the following command will eventually compile
the model and set up the laboratory::

   payu init $model_name


Setting up the experiment
-------------------------

*Until ``payu init`` is properly configured, users will have to manually setup
their experiments by following the steps below. We are working on automating
these steps.*

1. Create a *laboratory path*, usually somewhere in ``/short``::

      mkdir -p /short/${PROJECT}/${USER}/${MODEL}

   where ${MODEL} is one of the models supported by payu.

2. Inside this directory (which we call ``${LAB}``), create directories for your
   executables and input fields::

      mkdir ${LAB}/bin
      mkdir ${LAB}/input

3. Either compile or copy an executable into the ``${LAB}/bin`` directory::

      cp /path/to/model/exec ${LAB}/bin/

4. Create a directory relevant to your experiment, and copy any binary input
   files into this directory::

      mkdir ${LAB}/input/my_data
      cp /some/data/file ${LAB}/input/my_data/

5. Return to the home directory and create a *control directory*::

      cd ~
      mkdir -p ${MODEL}/my_expt
      cd ${MODEL}/my_expt

6. Copy any configuration files into this directory, such as namelists or other
   input text files::

      cp /path/to/namelists ~/${MODEL}/my_expt

7. Create a ``config.yaml`` file inside the directory, such as the one shown
   below for MOM::

      # Submission settings
      queue: normal
      project: v45
      ncpus: 1
      walltime: 1:00:00
      jobname: bowl1
      # Model settings
      model: mom
      shortpath: /short/v45
      exe: fms_MOM_solo.x
      input: bowl1
      # Collation
      collate_walltime: 10:00
      collate_mem: 1GB

   See the (as yet unwritten) section on ``config.yaml`` creation for more
   details.

After completing these steps, the model is ready for submission.


Running the Model
-----------------

Once the experiment has been set up (see the next section), the model is run
from the control directory by typing the following::

   payu run

This will run the model once, and save the output to the archive directory.

If you type ``payu run`` again, then the model will continue from the end of
the previous run.

To run the model ``N`` times in succession, type the following::

   payu run -n N

If there are no archived runs, the model will start from initialization. If
there is an existing run, it will start from the last run and do ``N``
additional runs.

If you ever need to start from a particular run, say ``K``, then type the
following::

   payu run -i K -n N

Note that numbering is 0-based, so that the first run is 0, the second run is
1, and so on. In general, one should not expect to use the ``-i`` flag outside
of testing.

Running jobs are stored in a work directory, which can be accessed by a
symbolic link ``work`` created inside the control directory. Completed runs are
stored in the archive directory, accessible by an equivalent ``archive``
symbolic link.


Licensing
=========

Payu is distributed under the Apache 2.0 License.


Contributors
============

- Marshall Ward <marshall.ward@anu.edu.au> *(Maintainer)*
- Nicholas Hannah
