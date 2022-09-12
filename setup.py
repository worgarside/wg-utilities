"""Setup/config file for the package"""

from os.path import abspath, join, sep

from setuptools import find_packages, setup

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
        version="2.30.3",
        author="Will Garside",
        author_email="worgarside@gmail.com",
        description="Generic utilities for use across all personal projects",
        long_description=long_description,
        long_description_content_type="text/markdown",
        url="https://github.com/worgarside/wg-utilities",
        packages=find_packages(),
        package_data={pkg: ["py.typed"] for pkg in find_packages()},
        classifiers=[
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
        ],
        extras_require={
            "clients": [
                "flask>=2.0.2",
                "pyjwt>=2.1.0",
                "requests>=2.26.0",
                "google-auth-oauthlib>=0.4.6",
                "pytz~=2022.1",
                "tzlocal~=4.2",
                "python-dotenv",
                "spotipy>=2.19.0",
            ],
            "devices.epd": [
                "spidev>=3.5; sys_platform == 'linux'",
                "rpi.gpio>=0.7.0; sys_platform == 'linux'",
            ],
            "devices.dht22": ["pigpio"],
            "devices.yamaha_yas_209": [
                "async-upnp-client",
                "pydantic",
                "xmltodict~=0.13",
            ],
            "exceptions": [
                "python-dotenv",
                "requests>=2.26.0",
            ],
            "functions+xml": [
                "lxml>=4.8.0",
            ],
        },
        zip_safe=False,
    )
