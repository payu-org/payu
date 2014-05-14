"""setup.py
   Installation script for payu

   Additional configuration settings are in ``setup.cfg``.
"""

import os
from distutils.core import setup

PKG_NAME = 'payu'
PKG_VERSION = __import__(PKG_NAME).__version__
PKG_SCRIPTS = [os.path.join('bin', f) for f in os.listdir('bin')]
PKG_PKGS = [path for (path, dirs, files) in os.walk(PKG_NAME)
             if '__init__.py' in files]

with open('README.rst') as f:
    README_RST = f.read()

setup(
    name=PKG_NAME,
    version=PKG_VERSION,
    description='A climate model workflow manager for supercomputing '
                'environments.',
    long_description=README_RST,
    author='Marshall Ward',
    author_email='python@marshallward.org',
    url='http://github.com/marshallward/payu',

    packages=PKG_PKGS,
    requires=['f90nml', 'PyYAML'],
    scripts=PKG_SCRIPTS,

    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
    ],

    keywords='{} supercomputer model climate workflow'.format(PKG_NAME)
)
