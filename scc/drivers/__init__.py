#!/usr/bin/env python2
"""
SC-Controller goes through all modules in scc.drivers package and calls
init(daemon) methods from every module that defines it.

Drivers then can use daemon.add_to_mainloop() method to add code that should
be run in every mainloop iteration and daemon.add_controller() to add and
daemon.remove_controller() to remove Controller instances.

Additionaly, start(daemon) method is called from each module that defines it
just before daemon startup is complete.

Assigning Mapper to Controller is handled by daemon.
"""
