"""Setup/config file for the package"""

from os.path import sep, abspath, join
from setuptools import setup, find_packages

PROJECT_ROOT = sep + join(
    "",
    *abspath(__file__).split(sep)[
        0 : abspath(__file__).split(sep).index("wg-utilities") + 1
    ]
)

if __name__ == "__main__":
    with open(join(PROJECT_ROOT, "README.md"), encoding="utf-8") as f:
        long_description = f.read()

    setup(
        name="wg_utilities",
        version="2.12.2",
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
        install_requires=[
            "requests>=2.26.0",
            "google-auth-oauthlib>=0.4.6",
            "spidev>=3.5; sys_platform == 'linux'",
            "rpi.gpio>=0.7.0; sys_platform == 'linux'",
            # "jetson.gpio>=2.0; sys_platform == 'linux'",
            "spotipy~=2.19.0",
            "pyjwt~=2.1.0",
            "flask>=2.0.2",
            "pytz~=2022.1",
            "tzlocal~=4.2",
        ],
    )
