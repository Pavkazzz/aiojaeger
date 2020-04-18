import os
import sys

from setuptools import find_packages, setup

if sys.version_info < (3, 7, 0):
    raise RuntimeError("aiozipkin does not support Python earlier than 3.7.0")


def read(f):
    return open(os.path.join(os.path.dirname(__file__), f)).read().strip()


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
    name="aiozipkin",
    version="0.1.0",
    description=(
        "Distributed tracing instrumentation"
        " for asyncio application with zipkin and jaeger"
    ),
    long_description="\n\n".join((read("README.rst"), read("CHANGES.txt"))),
    classifiers=classifiers,
    platforms=["POSIX"],
    author="Pavel Mosein",
    author_email="pavel-mosein@yandex.ru",
    url="https://github.com/pavkazzz/aiozipkin",
    download_url="https://pypi.python.org/pypi/aiozipkin",
    license="Apache 2",
    packages=find_packages(),
    install_requires=install_requires,
    extras_require=extras_require,
    keywords=["zipkin", "jaeger", "distributed-tracing", "tracing"],
    zip_safe=True,
    include_package_data=True,
)
