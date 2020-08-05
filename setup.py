from setuptools import setup, find_packages
with open("README.md", "r") as fh:
    long_description = fh.read()

CLASSIFIERS = [
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Topic :: Scientific/Engineering :: Information Analysis",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Development Status :: 4 - Beta"
]

setup(
    name='aanalytics2',
    version="0.0.8",
    license='GPL',
    description='Adobe Analytics v2 API wrapper',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Julien Piccini',
    author_email='piccini.julien@gmail.com',
    url='https://github.com/pitchmuc/adobe_analytics_api_2.0',
    keywords=['adobe', 'analytics', 'API', 'python'],
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'pandas',
        'pathlib2',
        'pathlib',
        'requests',
        'PyJWT[crypto]',
        'PyJWT',
        "dicttoxml"
    ],
    classifiers=CLASSIFIERS,
    python_requires='>=3.6'
)
