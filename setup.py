from setuptools import setup, find_packages

setup(
    name="bifrost",
    version="0.0.0",
    url="https://github.com/Mejiro-McQueen/Bifrost",
    author="Mejro-McQueen",
    author_email="",
    description='Bifrost is a light weight GDS development environment.',
    python_requires='>=3.8',
    install_requires=[
        'astropy',
        'bitarray',
        'bitstring',  # choose this or bitarray
        'boto3',
        'cffi',
        'colorama',
        'influxdb-client[ciso]',
        'inotify',
        'jsonschema',
        'nats-py',
        'pandas',
        'portion',
        'pyasn1',
        'pyyaml',
        'requests',  # junk this
        'setproctitle',
        'starlette',
        'tqdm',
        'uvicorn',
        'uvloop',
        'websockets',
        # AIT-DSN Junk
        'gevent==23.9.1',
        'greenlet==0.4.16',
    ],
    packages=find_packages(),
    scripts=['bifrost/bin/bifrost',
             'bifrost/bin/subscribers/websocket/bifrost.messages',
             'bifrost/bin/subscribers/websocket/bifrost.realtime',
             'bifrost/bin/subscribers/websocket/bifrost.monitors',
             'bifrost/bin/subscribers/websocket/bifrost.command_loader',
             'bifrost/bin/subscribers/websocket/bifrost.downlink_updates',
             'bifrost/bin/subscribers/websocket/bifrost.inject',
             ],
    extras_require={
        'tests': [
            "pytest",
        ],
    },
)
