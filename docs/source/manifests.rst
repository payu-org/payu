=========
Manifests
=========

Introduction
============

payu automatically generates and updates manifest files in the ``manifest``
subdirectory in the control directory. The manifests are stored in YAML_ 
format.

There are three manifests: ``manifest/exe.yaml`` tracks executable files, 
``manifest/input.yaml`` tracks input files and ``manifest/restart.yaml`` 
tracks restart files.

Only files in the temporary ``work`` directory are tracked by manifests. Any
files that are directly accessed from other locations in the filesystem
within models or other programs **are not tracked**

.. _YAML: http://www.yaml.org/

Manifest contents
=================

The manifests store information about the files contained in the
``work`` directory of an experiment. In most cases those files are symbolically 
linked from another location. 

An example input manifest is shown below::

      format: yamanifest
      version: 1.0
      ---
      work/INPUT/gotmturb.inp:
          fullpath: /scratch/x00/aaa000/mom/input/bowl1/gotmturb.inp
          hashes:
              binhash: 1730d092cdc5d86e234d3749857ed318
              md5: 3016ea3bccf1acd2c18eefdd6dbf02e9
      work/INPUT/grid_spec.nc:
          fullpath: /scratch/x00/aaa000/mom/input/bowl1/grid_spec.nc
          hashes:
              binhash: b79c406507e2b96725a08237e2165314
              md5: f571a0106c4a2eba38e3c407335e8cca
      work/INPUT/ocean_temp_salt.res.nc:
          fullpath: /scratch/x00/aaa000/mom/input/bowl1/ocean_temp_salt.res.nc
          hashes:
              binhash: d70322dece2f10aaacf751254a2acee7
              md5: f506e15417ed813fde3516a262ff35e5

The first section of the file specifes a format (``yamanifest``) and a version 
number (``1.0``). The second section has a local path in the ``work`` directory
as the key, and for each of these paths stores the location in the filesystem 
(``fullpath``) and two hashes, ``binhash`` and ``md5``. 

There are two hashes as ``binhash`` is fast and size independent designed 
just to detect if a file has changed. If the calculated binhash is not the same
as that stored in the manifest the slower but robust MD5 hash is calculated. 
Whenever a hash changes the updated value is stored in the manifest file.

Experiment tracking
===================

The manifest files are automatically added to the git repository that 
tracks changes to the experimental configuration. Each time
the model is run the manifest is checked and changed hashes are updated, 
and any new files found are added to the manifest.

In this way manifests uniquely identify all executables, input and restart files
for each model run.

Manifest updates
----------------

Each time the model is run, binhash for each filepath is recalculated
and compared with stored manifest values. If a new filepath has been added,
or the binhash differs from the stored value, the full MD5 hash is
recalculated. By using binhash, a fast change-sensitive hash,
these time consuming MD5 hashes only need be computed when a change has
been detected. So the slow md5 hashes are recalculated as little as possible.

Manifest options
----------------

By default manifests just reflect the state of the model, and when files
change the update hashes are saved in the manifest. These changes in the
manifest files are then tracked with git.

There are some configuration options available to change this default 
behaviour.



