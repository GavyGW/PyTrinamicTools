'''
Created on 30.07.2019

@author: LH, ED
'''
import setuptools
from PyTrinamicTools.version import __version__

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="PyTrinamicTools",
    version=__version__,
    author="ED, LK, LH, ..",
    author_email="tmc_info@trinamic.com",
    description="TRINAMIC's Python tools collection.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/trinamic/PyTrinamicTools",
    packages=setuptools.find_packages(),
    install_requires=[
        "PyTrinamic",
        "matplotlib"
    ],
    py_modules=[
        "PyTrinamicTools/helpers/Microsteps",
        "PyTrinamicTools/version"
    ],
    scripts=[
        "PyTrinamicTools/tools/MicrostepCalculator.py"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    license="MIT",
    zip_safe=False,
)
