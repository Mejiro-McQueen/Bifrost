Bifrost, a FOSS Ground Data System software development environment.

What is Bifrost?
================
- Bifrost is a light weight software development environment for developing ground data systems.
- Bifrost is a curated a collection of programs, libraries, and utilities GDS engineers can use and/or modify to suit their missions' needs.
- Bifrost facilitates a service based architecture with the NATS Server at its core [https://nats.io/] to provide maximum flexibility in integrating Bifrost with your mission's software systems.
- Bifrost strives to provide straight forward and sane services for multimission use by adhering to the CCSDS standards as much as possible.
- Bifrost strives to promote hacking (in the MIT sense) in order to quickly fulfill the mission's needs by providing the ability to write your own services that interact with the NATS network to intercept and modify data streams and messages, or provide new capabilities all together. 

What is Bifrost _not_?
======================
- Bifrost is not an official product, supported, or endorsed by the SunRISE project, Ammos Instrumentation Toolkit (AIT), Advanced Multi-Mission Operations System (AMMOS), Jet Propulsion Laboraty (JPL), Caltech, The National Aeronautics and Space Administration (NASA), or any of their affiliates and contributors; You are completely dependant on yourself and the independant FOSS contributors to this repository for support. 
- Bifrost is not an out of the box solution for every mission. Our intention is to provide Cubesat missions a way of reusing software developed by other cubesat missions and NASA projects. To this end, many of the Bifrost libraries are not fully CCSDS compliant, bug free, or feature complete. You should expect to invest a considerate amount of time and resources into evaluating/developing Bifrost services that meet your missions' needs.
- Bifrost is not high performance. Due to historical reasons, many (all) of Bifrost services and libraries are written in python 3. Bifrost is a collection of services on the NATS network that run as independent processes. Each python process uses python's built in asyncio library to provide concurency within the process.
- Bifrost is not a data visualization or analysis suite (See the Operations section for tips) (Integration with OpenMCT comming soon).

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
Unlikely! However, it shouldn't be too difficult to adapt it. Many Bifrost Services originated from SunRISE-AIT and were easy to port.

What is the Bifrost's history?
=============================
Bifrost was orignally SunRISE-AIT, a fork of the AIT repositories for the SunRISE cuebsat mission. SunRISE intended to use AIT as a ground data system, but at the time, AIT was missing many functionalities critical to the success of a ground data system. With the power of extreme programming, and over the course of a year, the SunRISE GDS engineers developed SunRISE-AIT into a functional GDS. SunRISE contributed to the AIT project early on, however it soon became clear that the SunRISE-AIT fork had become orthogonal to AIT upstream in design and philosophy. Thus we arrive at Bifrost, the effort to polish, refine, and share with the FOSS community a multimission version of SunRISE-AIT.
 
Getting Started
===============
- How do I install Bifrost?
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
      - ``bifrost.messages`` for viewing the message stream.
      - ``bifrost.realtime`` for viewing telemetry output.
      - ``bifrost.command_loader`` for sending commands (edit this file).
  
- Is there a docker image available?
Yes, fill out the docker.env file and use the docker-compose to quick start.
  
How can I visualize or analyze my telemetry?
===========================================
- Bifrost primarily outputs telemetry to an Influx database. You can use the Influx visualization and notebooking capabilities, or any other software that supports influx (Grafana, etc...).
- SunRISE has had success in ingesting telemetry from 6 space craft simultaneously on OpenMCT.
- Bifrost reintegration with OpenMCT is comming soon and is the highest priority.
- Bifrost also outputs telemetry to the NATS network, stdio, and a websocket via its web service; you can use these to feed your favorite data analysis software, scripts, or write a new Bifrost service.

  
Tips
====
- Do not use python if at all possible, choose a language that has good NATS Jetstream support (Golang for example), or any langauge with good NATS support if you do not need to operate on telemetry streams (Haskell, Common Lisp), that is, write new services without using Bifrost python libraries. Your new software can interact with Bifrost services over the NATS network.
- If you must use python, do not use Gevent, Greenlets, gipc, etc... Bifrost historically used gevent, however performance was terrible and in many cases dropped telemetry all together; use python's built in asyncio library as much as possible, we have provided helper functions to facilitate this in your services.
- You can distribute your GDS across different machines or deploy on AWS!

Bifrost Architecture
====================
Comming soon!
