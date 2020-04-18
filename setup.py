import os
import re
import sys

from setuptools import find_packages, setup

if sys.version_info < (3, 7, 0):
    raise RuntimeError("aiojaeger does not support Python earlier than 3.7.0")


def read(f):
    return open(os.path.join(os.path.dirname(__file__), f)).read().strip()


def read_version():
    regexp = re.compile(r"^__version__\W*=\W*\"([\d].+)\"")
    init_py = os.path.join(os.path.dirname(__file__),
                           "aiojaeger", "version.py")
    with open(init_py) as f:
        for line in f:
            match = regexp.match(line)
            if match is not None:
                return match.group(1)
        else:
            msg = "Cannot find version in aiojaeger/version.py"
            raise RuntimeError(msg)


install_requires = ["aiohttp<4", "thriftpy2~=0.4.11", "pydantic~=1.4"]
extras_require = {}

classifiers = [
    "License :: OSI Approved :: MIT License",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Operating System :: POSIX",
    "Development Status :: 3 - Alpha",
    "Framework :: AsyncIO",
]

setup(
    name="aiojaeger",
    version=read_version(),
    description=(
        "Distributed tracing instrumentation"
        " for asyncio application with zipkin and jaeger"
    ),
    long_description="\n\n".join((read("README.rst"), read("CHANGES.txt"))),
    classifiers=classifiers,
    platforms=["POSIX"],
    author="Pavel Mosein",
    author_email="pavel-mosein@yandex.ru",
    url="https://github.com/pavkazzz/aiojaeger",
    download_url="https://pypi.python.org/pypi/aiojaeger",
    license="Apache 2",
    packages=find_packages(),
    install_requires=install_requires,
    extras_require=extras_require,
    keywords=["zipkin", "jaeger", "distributed-tracing", "tracing"],
    zip_safe=True,
    include_package_data=True,
)
