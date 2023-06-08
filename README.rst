Bifrost is a customizable distributed light weight Ground Data System.

What is Bifrost?
================
- Bifrost is a light weight software development environment for developing ground data systems.
- Bifrost is a curated a collection of programs, libraries, and utilities GDS engineers can use and/or modify to suit their missions' needs.
- Bifrost facilitates a service based architecture with the NATS Server at its core [https://nats.io/] to provide maximum flexibility in integrating Bifrost with your mission's software systems.
- Bifrost strives to provide straight forward and sane services for multimission use by adhering to the CCSDS standards as much as possible.
- Bifrost strives to promote hacking (in the MIT sense) in order to quickly fulfill the mission's needs by providing the ability to write your own services that interact with the NATS network to intercept and modify data streams and messages, or provide new capabilities all together (Project Expansions). 

Getting Started
===============
- Is there a docker image available?
  
  Yes! Your project expansion can also be layered onto the base Bifrost image. Use the NASA Core Flight Software (cFS) expansion as a reference. More documentation on configuration options is coming soon.
  
  1. Fork this repository and build the docker image using ``docker build . -t bifrost:latest``
  2. Create a directory ``/gds`` and give read and write permissions to user `bifrost` (GDS artifacts and influx will be stored here). 
  3. Fork and clone the NASA Core Flight Software Reference Expansion: https://github.com/Mejiro-McQueen/Bifrost-NASA-cFS
  4. Use ``docker-compose up`` in the NASA cFS Expansion to build and start the required services. (This does not actually deploy the cFS)

- How do I manually install Bifrost?
  
  You'll need PIP, a NATS server (docker quick start instructions below), and a configuration file. We'll use conda to sort out our virtual environments.
  
  1. Setup your project distribution for AIT.
  2. Make a new directory and clone: your project repository, Bifrost
  3. ``conda create -y -q --name $(PROJECT_NAME) python=$(PYTHON_VERSION)``
  4. ``conda env config vars set AIT_CONFIG=./$(project_dir)/config/config.yaml BIFROST_SERVICES_CONFIG='$(project_dir)/config/services.yaml' SDLS=ENC``
  5. ``pip install -e ./Bifrost``
  6. ``pip install -e ./$(your project)``
  7. ``docker container rm nats --force && docker run --name nats  -p 4222:4222 -p 8222:8222 nats -js --http_port 8222 --debug``
  
- How do I run Bifrost?
  
 ``bifrost``

- How can I see some data flow?
  
  You'll need a simulator attached to Bifrost. You may be able to use the NASA'S NOS3 (https://github.com/nasa/nos3) to deploy the NASA cFS for demonstration purposes.
  
      - ``bifrost.messages`` for viewing the message stream.
      - ``bifrost.realtime`` for viewing telemetry output.
      - ``bifrost.command_loader`` for sending commands (edit this file).

What is Bifrost _not_?
======================

- Bifrost is not an official product, supported, or endorsed by Ammos Instrumentation Toolkit (AIT), Advanced Multi-Mission Operations System (AMMOS), Jet Propulsion Laboraty (JPL), Caltech, The National Aeronautics and Space Administration (NASA), or any of their affiliates and contributors; You are completely dependant on yourself and the independant FOSS contributors to this repository for support. 
- Bifrost is not an out of the box solution for every mission. Our intention is to provide Cubesat missions a way of reusing software developed by other cubesat missions and NASA projects. To this end, many of the Bifrost libraries are not fully CCSDS compliant, bug free, or feature complete. You should expect to invest a considerate amount of time and resources into evaluating/developing Bifrost services that meet your missions' needs.
- Bifrost is not high performance. Due to historical reasons, many (all) of Bifrost services and libraries are written in python 3. Bifrost is a collection of services on the NATS network that run as independent processes. Each python process uses python's built in asyncio library to provide concurency within the process.
- Bifrost is not a data visualization or analysis suite, but provides capabilities to intergrate with them (See the Operations section for tips).

What is AIT?
============

AIT is the AMMOS Instrument Toolkit [https://github.com/NASA-AMMOS/AIT-Core] which is an MIT licensed software developed and maintained by Jet Propulsion Laboratory. Some of the components of Bifrost were provided by AMMOS, the AIT project and its open source contributors.

- Bifrost leverages the DSN Interfaces and Transfer Frame frames libraries from AIT-DSN.
- Bifrost leverages the command and telemetry dictionary capabilities from AIT-Core.
- Even though the Bifrost service to use them exists, the AIT SLS libraries are dependant on the KMC Client and KMC server developed by AMMOS (They are not included in Bifrost).
  
AIT has (insert capability here), will Bifrost merge it in and support it?
--------------------------------------------------------------------------

Bifrost has no intention of keeping up with AIT development.
However: AIT is MIT licensed. Bifrost is MIT licensed. You can make it happen!

Will Bifrost make pull requests to provide (insert capability here) to AIT? 
---------------------------------------------------------------------------

Bifrost has no intention of keeping up with AIT development.
However: AIT is MIT licensed. Bifrost is MIT licensed. You can make it happen!

Is the AIT Plugin (insert plugin here) compatible with Bifrost as a service?
----------------------------------------------------------------------------

Unlikely! However, it shouldn't be too difficult to adapt it.
  
How can I visualize or analyze my telemetry?
===========================================

- Bifrost outputs telemetry to an Influx database. You can use the Influx visualization and notebooking capabilities, or any other software that supports influx (Grafana, etc...), (See the Bifrost NASA cFS Expansion docker compose file to quickly setup and integrate an InfluxDB instance: https://github.com/Mejiro-McQueen/Bifrost-NASA-cFS)
- Bifrost is partially integrated with OpenMCT. Use the javascript files as a baseline for your mission adaptation (See the Bifrost NASA cFS Expansion docker compose file to quickly setup and integrate an OpenMCT instance: https://github.com/Mejiro-McQueen/Bifrost-NASA-cFS):
    - realtime telemetry: :heavy_check_mark:
    - influx historical telemetry: :negative_squared_cross_mark:
    - station monitor data: :negative_squared_cross_mark:
    - bifrost messages: :negative_squared_cross_mark:
    - bifrost directives: :negative_squared_cross_mark:
    - bifrost monitors: :negative_squared_cross_mark:
    
- Bifrost also outputs telemetry to the NATS network, stdio, and a websocket via its web service; you can use these to feed your favorite data analysis software, scripts, or write a new Bifrost service.
  
Tips
====

- Do not use python if at all possible, choose a language that has good NATS Jetstream support (Golang for example), or any langauge with good NATS support if you do not need to operate on telemetry streams (Haskell, Common Lisp), that is, write new services without using Bifrost python libraries. Your new software can interact with Bifrost services over the NATS network.
- If you must use python, do not use Gevent, Greenlets, gipc, etc... Bifrost historically used gevent, however performance was terrible and in many cases dropped telemetry all together; use python's built in asyncio library as much as possible, we have provided helper libraries to facilitate this in your services.
- You can distribute your GDS across different machines or deploy on AWS!
  
Bifrost Architecture
====================

Comming soon!
