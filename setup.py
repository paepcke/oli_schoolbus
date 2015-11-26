import multiprocessing
from setuptools import setup, find_packages

test_requirements = ['sentinels>=0.0.6', 'nose>=1.0', 'python-dateutil>=2.2']

setup(
    name = "oli_schoolbus",
    version = "0.0.1",
    packages = find_packages(),

    # Dependencies on other packages:
    setup_requires   = ['nose>=1.1.2'],
    tests_require    = test_requirements,
    install_requires = ['redis_bus_python>=0.0.2',
			'tornado>=4.3',
			] + test_requirements,

    # Unit tests; they are initiated via 'python setup.py test'
    #test_suite       = 'nose.collector', 

    #data_files = [('pymysql_utils/data', datafiles)],

    package_data = {
        # If any package contains *.txt or *.rst files, include them:
     #   '': ['*.txt', '*.rst'],
        # And include any *.msg files found in the 'hello' package, too:
     #   'hello': ['*.msg'],
    },

    # metadata for upload to PyPI
    author = "Andreas Paepcke",
    author_email = "paepcke@cs.stanford.edu",
    description = "Example OLI analysis via SchoolBus communication.",
    license = "BSD",
    #zip_safe = False,
    keywords = "OLI",
    url = "git@github.com:paepcke/oli_schoolbus.git" # project home page, if any
)
