Support tools and install scripts
---------------------------------

These are various scripts which aid for installation on Raijin.

- ``nci_install`` is for the newer versions of Payu, which use a fixed Python
  executable and rely on entry points for command line execution.

- ``legacy_install`` is for older versions, which have less strict install
  requirements (mostly due to internal bootstrapping techniques which re-apply
  similar constraint)

- ``get-pip.py`` is a small script available publicly which install pip for
  Python 2.6.
