from setuptools import setup, find_packages

CLASSIFIERS = [
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Topic :: Scientific/Engineering :: Information Analysis",
    "Programming Language :: Python :: 3.5",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8"
]

setup(
    name='adobe_analytics_2',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'pandas>=0.25.1',
        'jwt>=0.6.1',
        'pathlib2>=2.3.5',
        'requests>=2.22.0',
    ],
    classifiers=CLASSIFIERS
)
