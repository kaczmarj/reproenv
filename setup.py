"""Setup script for ReproEnv.

To install, run `python setup.py install` or
`pip install --no-cache-dir --editable .`.
"""
from setuptools import setup

import versioneer

version = versioneer.get_version()

setup(version=version)
