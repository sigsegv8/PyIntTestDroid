#!/usr/bin/env python

from distutils.core import setup

setup ( name = 'PyIntTestDroid',
        version = '1.0',
        description = 'Integration Test Droid Library',
        author="David Tay",
        author_email="david.tay@jamdeo.com",
        packages = [ "pyint" ],
        long_description = 'Python library to help automate tests for Android products.',
        maintainer = 'David Tay',
        maintainer_email = 'david.tay@jamdeo.com',
        license = 'Apache',
        package_data={'pyint': ['*.conf']},
        )
