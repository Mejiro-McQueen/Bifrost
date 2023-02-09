Bifrost, a FOSS Ground Data System software development environment.

What is Bifrost?
================
- Bifrost is a light weight software development environment for developing ground data systems.
- Bifrost is a curated a collection of programs, libraries, and utilities GDS engineers can use and/or modify to suit their missions' needs.
- Bifrost facilitates a service based architecture with the NATS Server at its core [https://nats.io/] to provide maximum flexibility in integrating Bifrost with your mission's software systems.
- Bifrost strives to provide straight forward and sane services for multimission use by adhering to the CCSDS standards as much as possible.
- Bifrost strives to promote hacking in order to quickly fulfill the mission's needs (in the MIT sense) by providing the ability to write your own services that interact with the NATS network to intercept and modify data streams and messages, or provide new capabilities all together. 

What is Bifrost _not_?
======================
- Bifrost is not an official product, supported, or endorsed by the SunRISE project, Ammos Instrumentation Toolkit (AIT), Advanced Multi-Mission Operations System (AMMOS), Jet Propulsion Laboraty (JPL), Caltech, The National Aeronautics and Space Administration (NASA), or any of their affiliates and contributors; You are completely dependant on yourself and the independant FOSS contributors to this repository for support. 
- Bifrost is not an out of the box solution. Our intention is to provide Cubesat missions a way of reusing software developed by other cubesat missions and NASA projects. To this end, many of the Bifrost libraries are not fully CCSDS compliant, bug free, or feature complete. You should expect to invest a considerate amount of time and resources into developing Bifrost services that meet your missions' needs.
- Bifrost is not high performance. Due to historical reasons, many (all) of Bifrost services and libraries are written in python 3. Levarging NATS and starting each process as a service, Bifrost builds a system of processes. Each python process uses python's built in asyncio library to provide concurency within the process.
- Bifrost is not a data visualization or analysis suite (See the Operations section for tips).

What is AIT?
============
AIT is the AMMOS Instrument Toolkit [https://github.com/NASA-AMMOS/AIT-Core] which is an MIT licensed software developed and maintained by Jet Propulsion Laboratory. Some of the components of Bifrost were provided by AMMOS, the AIT project and its open source contributors.

- Bifrost leverages the SLE, SLS, and AOS frames libraries from AIT-DSN.
- Bifrost leverages the command and telemetry dictionary capabilities from AIT-Core.
- Even though the Bifrost service to use them exists, the AIT SLS libraries are dependant on the KMC Client and KMC server developed by AMMOS (They are not included in Bifrost, you're on your own on this one).
  
What are differences the between Bifrost and AIT's versions of (insert object here)?
------------------------------------------------------------------------------------
- Bifrost has removed as many unnecessary, incongruent, or badly supported components from AIT as possible.
- Bifrost has removed as many AIT components that are uncessary for the success to cubesat missions.
- Bifrost has patched or improved any remaining components.

AIT has (insert capability here), will Bifrost merge it in and support it?
--------------------------------------------------------------------------
AIT is MIT licensed. Bifrost is MIT licensed. Make your dreams come true.
Bifrost has no intention of keeping up with AIT development.
However, if you make bug fix or a cool multimission, and want to share it as part of Bifrost, we would appreciate the PR!

Will Bifrost make pull requests to provide (insert capability here) to AIT? 
---------------------------------------------------------------------------
AIT is MIT licensed. Bifrost is MIT licensed. Make your dreams come true.
Bifrost has no intention of keeping up with AIT development.

Is the AIT Plugin (insert plugin here) compatible with Bifrost as a service?
----------------------------------------------------------------------------
Unlikely! However, it shouldn't be too difficult to adapt it.

What is the Bifrost's history?
=============================
Bifrost was orignally SunRISE-AIT, a fork of the AIT repositories for the SunRISE cuebsat mission. SunRISE intended to use AIT as a ground data system, but at the time, AIT was missing many functionalities critical to the success of a ground data system. With the power of extreme programming, and over the course of a year, the SunRISE GDS engineers developed SunRISE-AIT into a functional GDS. SunRISE contributed to the AIT project early on, however it soon became clear that the SunRISE-AIT fork had become orthogonal to AIT upstream in design and philosophy. Thus we arrive at Bifrost, the effort to polish, refine, and share with the FOSS community a multimission version of SunRISE-AIT.

How can I help?
===============
Write a cool multimission service, bug fix, or library that provides a capability and make a PR!
A good long term goal is for Bifrost to be provide all the necessary capabilities to support a mission using the Nasa Core Flight Software.

Caveats
=======
- The command and telemetry dictionaries, and their associated data types are goofy. Keep this in mind when designing your ICD and do a lot of experimenation; Also consider rewriting these modules and let us know about it!
- The SLE libraries aren't polished or even feature complete (SunRISE had limited resources available to refine these modules).
- Many CCSDS oriented libraries are goofy and unpolished.
- Our software tests are terrible if non existant due to our development methodology and resource constrains. We attempt to test against SunRISE Flight Software Simulators and satellites as often as possible.
 
Getting Started
===============
- How do I install Bifrost?
  You'll need PIP, a NATS server (quick docker instructions below), and a configuration file. We'll use conda to sort out our virtual environments.
  0. Setup your project distribution for AIT.
  1. Make a new directory and clone: your project repository, Bifrost
  1. ``conda create -y -q --name $(PROJECT_NAME) python=$(PYTHON_VERSION)``
  2. ``conda env config vars set AIT_CONFIG=./$(project_dir)/config/config.yaml BIFROST_SERVICES_CONFIG='$(project_dir)/config/services.yaml' SDLS=ENC``
  3. ``pip install -e ./Bifrost``
  4. ``pip install -e ./$(your project)``
  4. ``docker container rm nats --force && docker run --name nats  -p 4222:4222 -p 8222:8222 nats -js --http_port 8222 --debug``
  

- How do I run Bifrost?
 ``bifrost``

- How can I see some data flow?
  ``bifrost.messages`` for viewing the message stream.
  ``bifrost.realtime`` for viewing telemetry output.
  ``bifrost.command_loader`` for sending commands (edit this file).
  
How can I visualize or analyze my telemetry?
===========================================
- Bifrost primarily outputs telemetry to an Influx database. You can use the Influx visualization and notebooking capabilities, or any other software that supports influx (Grafana, etc...).
- SunRISE has had success in ingesting telemetry from 3 space craft simultaneously on OpenMCT.
- Bifrost also outputs telemetry to the NATS network and a websocket via its web service; you can use these to feed your favorite data analysis software or write a Bifrost service.

  
Tips
====
- Do not use python if at all possible, choose a language that has good NATS Jetstream support (Golang for example), or any langauge with good NATS support if you do not need to operate on streams (Haskell, Common Lisp), that is, write new services without using Bifrost python libraries. Your new software can interact with Bifrost services over the NATS network.
- If you must use python, do not use Gevent, Greenlets, gipc, etc... Bifrost historically used gevent, however performance was terrible and in many cases dropped telemetry all together; use python's built in asyncio library as much as possible, we have provided helper functions to facilitate this in your services.
- Use the decorators in /bifrost/common/loud_exception.py to help prevent silent errors in your functions.
- You can distribute your GDS across different machines or deploy on AWS!


Bifrost Architecture
====================
Comming soon!
