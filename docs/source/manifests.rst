.. _usage:

=====
Manifests
=====

Introduction
========

payu automatically generates and updates manifest files in the ``manifest``
subdirectory in the control directory. The manifests are also writtern in the 
YAML_ file format.

There are three manifests, ``manifest/exe.yaml`` tracks executable files, 
``manifest/input.yaml`` tracks input files and ``manifest/restart.yaml`` 
tracks restart files.

Only files in the temporary ``work`` directory are tracked by manifests. Any
files that are directly accessed from other locations in the filesystem
within models or other programs 

How do manifests work?
======================

The manifests used by payu store information about the files contained in the
``work`` directory. In most cases those files are symbolically linked from
another location, so the manifest stores the local path in the ``work`` 
directory, the ``fullpath``, which is where the file exists on the filesystem
and is linked to, and some verification hashes.

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
as the key, and for each path has the location in the filesystem (``fullpath``)
and in two hashes, ``binhash`` and ``md5``. There are two hashes as the ``binhash``
is fast and size independent designed to detect if there have been any changes in
the file, and if so, the slower but robust MD5 hash is calculated. Whenever a hash
changes it is stored in the manifest file.
