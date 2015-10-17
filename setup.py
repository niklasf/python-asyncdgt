#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This file is part of the python-asyncdgt library.
# Copyright (C) 2015 Niklas Fiekas <niklas.fiekas@tu-clausthal.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import setuptools

sys.path.insert(0, os.path.abspath("asyncdgt"))
import _info as asyncdgt


def read_description():
    with open(os.path.join(os.path.dirname(__file__), "README.rst")) as readme:
        return readme.read()


def dependencies():
    deps = []
    deps.append("pyee")
    deps.append("pyserial")
    return deps


setuptools.setup(
    name="asyncdgt",
    version=asyncdgt.__version__,
    author=asyncdgt.__author__,
    author_email=asyncdgt.__email__,
    description=asyncdgt.__doc__.strip().rstrip("."),
    long_description=read_description(),
    license="GPL3",
    keywords="chess dgt",
    url="https://github.com/niklasf/python-asyncdgt",
    packages=["asyncdgt"],
    test_suite="test",
    install_requires=dependencies(),
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: Unix",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.4",
        "Topic :: Games/Entertainment :: Board Games",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
