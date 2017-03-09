#!/usr/bin/env python

from setuptools import setup

setup(
    name='UCI Scout',
    version='1.0.0',
    description='Frontend Search UI for CS121 Project',
    author='Nova Ng',
    packages=['uci_scout'],
    install_requires=[
        'elasticsearch >= 5.0.0, < 6.0.0',
        'flask >= 0.12',
        'flask-paginate >= 0.4.5'
    ],
)
