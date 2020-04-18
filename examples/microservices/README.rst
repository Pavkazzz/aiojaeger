Microservices Demo
==================

Example of microservices project using aiohttp_. There are 5 services, which
calls each other to serve request. You can explore traces and services
interconnection in Zipkin UI. This demo uses new aiohttp features available
only in >= 3.0.0 version and python 3.7 context variables.


Installation
============

Clone repository and install required dependencies::

    $ git clone git@github.com:aio-libs/aiojaeger.git
    $ cd aiojaeger
    $ pip install -e .
    $ pip install -r requirements-dev.txt
    $ pip install aiohttp-jinja2


Start zipkin server (make sure you have docker installed)::

    $ make zipkin_start

To stop zipkin server (stop and remove docker container)::

    $ make zipkin_stop

To start all service execute following command:::

    $ python examples/microservices/runner.py

Open browser::

    http://127.0.0.1:9001


First service will start chain of http calls to other services, and then will
render page with fetched information. You can investigate that chain and timing
in Zipkin UI.

Zipkin UI available::

    http://127.0.0.1:9411/zipkin/



Requirements
============
* aiohttp_

.. _Python: https://www.python.org
.. _aiohttp: https://github.com/aio-libs/aiohttp
