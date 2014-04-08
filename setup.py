from setuptools import setup, find_packages

with open('README.rst') as f:
    readme_rst = f.read()

setup(
    name = 'payu',
    version = '0.1',
    description = 'A climate model workflow manager for supercomputing '
                  'environments.',
    long_description = readme_rst,
    author = 'Marshall Ward',
    author_email = 'python@marshallward.org',
    url = 'http://github.com/marshallward/payu',
    license = 'Apache Software License 2.0',

    packages = find_packages(),
    install_requires = ['f90nml'],

    classifiers = [
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
    ]

    keywords='payu supercomputer model climate workflow'
)
