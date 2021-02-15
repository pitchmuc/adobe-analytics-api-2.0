import codecs
import os

from setuptools import setup, find_packages


def read(rel_path: str):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()


def get_version(rel_path: str):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


CLASSIFIERS = [
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Topic :: Scientific/Engineering :: Information Analysis",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Development Status :: 4 - Beta"
]

setup(
    name='aanalytics2',
    version=get_version("aanalytics2/__version__.py"),
    license='GPL',
    description='Adobe Analytics API 2.0 python wrapper',
    long_description=read("README.md"),
    long_description_content_type='text/markdown',
    author='Julien Piccini',
    author_email='piccini.julien@gmail.com',
    url='https://github.com/pitchmuc/adobe_analytics_api_2.0',
    keywords=['adobe', 'analytics', 'API', 'python'],
    packages=find_packages(),
    include_package_data=True,
    data_files=[('aanalytics2', ['CSV_Column_and_Query_String_Reference.pickle', 'eventType_usageLogs.pickle','supported_tags.pickle'])],
    install_requires=[
        'pandas',
        'pathlib2',
        'pathlib',
        'requests',
        'PyJWT[crypto]',
        'PyJWT',
        "dicttoxml",
        "pytest"
    ],
    classifiers=CLASSIFIERS,
    python_requires='>=3.6'
)
