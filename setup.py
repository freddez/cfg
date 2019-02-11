from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="cfg-manager",
    version="1.1.5",
    description="git based config files manager and installer",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://github.com/freddez/cfg",
    author="Frédéric de ZORZI",
    author_email="f@idez.net",
    classifiers=[ 
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    keywords="system configuration files git deploy",
    packages=find_packages(exclude=[]),
    python_requires=">=3.5.*, <4",
    install_requires=["gitpython", "colorama", "termcolor"],
    entry_points={"console_scripts": ["cfg=cfg.cfg:main"]},
    project_urls={  # Optional
        "Bug Reports": "https://github.com/freddez/cfg/issues",
        "Funding": "https://donate.pypi.org",
        "Say Thanks!": "https://saythanks.io/to/freddez",
        "Source": "https://github.com/freddez/cfg",
    },
)
