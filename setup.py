#!/usr/bin/env python3
"""
Setup script for dbbasic-tsv
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="dbbasic-tsv",
    version="1.0.1",
    author="AskRobots Contributors",
    description="A pure-Python, filesystem-based database using TSV files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/askrobots/dbbasic-tsv",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[],  # No dependencies!
    extras_require={
        "dev": ["pytest>=7.0", "pytest-cov>=4.0"],
    },
    keywords="database tsv filesystem nosql embedded portable",
    project_urls={
        "Bug Reports": "https://github.com/askrobots/dbbasic-tsv/issues",
        "Source": "https://github.com/askrobots/dbbasic-tsv",
        "Documentation": "https://github.com/askrobots/dbbasic-tsv#readme",
    },
)