"""Setup/config file for the package"""
from setuptools import setup, find_packages


if __name__ == "__main__":
    with open("README.md", encoding="utf-8") as f:
        long_description = f.read()

    setup(
        name="wg_utilities",
        version="0.1.0",
        author="Will Garside",
        author_email="worgarside@gmail.com",
        description="Generic utilities for use across all personal projects",
        long_description=long_description,
        long_description_content_type="text/markdown",
        url="https://github.com/worgarside/wg-utilities",
        packages=find_packages(),
        classifiers=[
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
        ],
        install_requires=[],
    )
