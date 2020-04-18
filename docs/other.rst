Support of other collectors
===========================
**aiojaeger** can work with any other zipkin_ compatible service, currently we
tested it with jaeger_ and stackdriver_.

Jaeger support
--------------
jaeger_ supports zipkin_ span format and as a result it is possible to use *aiojaeger*
with jaeger_ server. You just need to specify *jaeger* server address and it
should work out of the box. No need to run a local zipkin server.
For more information see tests and jaeger_ documentation.

.. image:: https://raw.githubusercontent.com/aio-libs/aiojaeger/master/docs/jaeger.png
    :alt: jaeger ui animation


Stackdriver support
-------------------
Google stackdriver_ supports zipkin_ span format as a result it is possible to
use *aiojaeger* with this google_ service. In order to make this work you
need to setup zipkin service locally, that will send traces to the cloud. See
google_ cloud documentation how to setup make zipkin collector:

.. image:: https://raw.githubusercontent.com/aio-libs/aiojaeger/master/docs/stackdriver.png
    :alt: jaeger ui animation


.. _zipkin: http://zipkin.io
.. _jaeger: http://jaeger.readthedocs.io/en/latest/
.. _stackdriver: https://cloud.google.com/stackdriver/
.. _google: https://cloud.google.com/trace/docs/zipkin
