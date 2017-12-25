#!/usr/bin/env python2
"""
SC-Controller - Scripts

Contains code for most of what can be done using 'scc' script.
Created so scc-* stuff doesn't polute /usr/bin.
"""
from scc.tools import init_logging, set_logging_level, find_binary
import sys, subprocess


class InvalidArguments(Exception): pass


def cmd_daemon(argv0, argv):
	""" Controls scc-daemon """
	# Actually just passes parameters to scc-daemon
	scc_daemon = find_binary("scc-daemon")
	subprocess.Popen([scc_daemon] + argv).communicate()


def help_daemon():
	scc_daemon = find_binary("scc-daemon")
	subprocess.Popen([scc_daemon, "--help"]).communicate()


def cmd_gui(argv0, argv):
	""" Starts GUI """
	# Passes parameters to sc-controller
	scc_daemon = find_binary("sc-controller")
	subprocess.Popen([scc_daemon] + argv).communicate()


def help_gui():
	scc_daemon = find_binary("sc-controller")
	subprocess.Popen([scc_daemon, "--help"]).communicate()


def cmd_test_evdev(argv0, argv):
	"""
	Evdev driver test. Displays gamepad inputs using evdev driver.
	
	Usage: scc test_evdev /dev/input/node
	Return codes:
	  0 - normal exit
	  1 - invalid arguments or other error
	  2 - failed to open device
	"""
	from scc.drivers.evdevdrv import evdevdrv_test
	return evdevdrv_test(argv)


def cmd_test_hid(argv0, argv):
	"""
	HID driver test. Displays gamepad inputs using hid driver.
	
	Usage: scc test_hid vendor_id device_id
	Return codes:
	  0 - normal exit
	  1 - invalid arguments or other error
	  2 - failed to open device
	  3 - device is not HID-compatibile
	  4 - failed to parse HID descriptor
	"""
	from scc.drivers.hiddrv import hiddrv_test, HIDController
	return hiddrv_test(HIDController, argv)


def sigint(*a):
	print("\n*break*")
	sys.exit(0)


def import_osd():
	import gi
	gi.require_version('Gtk', '3.0')
	gi.require_version('Rsvg', '2.0')
	gi.require_version('GdkX11', '3.0')


def run_osd_tool(tool, argv0, argv):
	import signal, argparse
	signal.signal(signal.SIGINT, sigint)
	
	from scc.tools import init_logging
	from scc.paths import get_share_path
	init_logging()
	
	sys.argv[0] = "scc osd-keyboard"
	if not tool.parse_argumets([argv0] + argv):
		sys.exit(1)
	tool.run()
	sys.exit(tool.get_exit_code())


def help_osd_keyboard():
	import_osd()
	from scc.osd.keyboard import Keyboard
	return run_osd_tool(Keyboard(), "osd-keyboard", ["--help"])


def cmd_osd_keyboard(argv0, argv):
	""" Displays on-screen keyboard """
	import_osd()
	from scc.osd.keyboard import Keyboard
	return run_osd_tool(Keyboard(), argv0, argv)


def cmd_dependency_check(argv0, argv):
	""" Checks if all required libraries are installed on this system """
	try:
		import gi
		gi.require_version('Gtk', '3.0') 
		gi.require_version('GdkX11', '3.0') 
		gi.require_version('Rsvg', '2.0') 
	except ValueError, e1:
		print >>sys.stderr, e1
		if "Rsvg" in str(e1):
			print >>sys.stderr, "Please, install 'gir1.2-rsvg-2.0' package to use this application"
		else:
			print >>sys.stderr, "Please, install 'PyGObject' package to use this application"
	except ImportError, e2:
		print e2
		return 1
	try:
		import evdev
	except Exception, e:
		print >>sys.stderr, e
		print >>sys.stderr, "Please, install python-evdev package to enable non-steam controller support"
	try:
		import scc.lib.xwrappers as X
		X.Atom
	except Exception, e:
		print >>sys.stderr, e
		print >>sys.stderr, "Failed to load X11 helpers, please, check your X installation"
		return 1
	return 0

def show_help(command = None, out=sys.stdout):
	names = [ x[4:] for x in globals() if x.startswith("cmd_") ]
	max_len = max([ len(x) for x in names ])
	if command in names:
		if "help_" + command in globals():
			return globals()["help_" + command]()
		hlp = (globals()["cmd_" + command].__doc__ or "").strip("\t \r\n")
		if hlp:
			lines = hlp.split("\n")
			if len(lines) > 0:
				for line in lines:
					line = (line
						.replace("Usage: scc", "Usage: %s" % (sys.argv[0], )))
					if line.startswith("\t"): line = line[1:]
					print >>out, line
				return 0
	
	print >>out, "Usage: %s <command> [ arguments ]" % (sys.argv[0], )
	print >>out, ""
	print >>out, "List of commands:"
	for name in names:
		hlp = ((globals()["cmd_" + name].__doc__ or "")
					.strip("\t \r\n")
					.split("\n")[0])
		print >>out, (" - %%-%ss %%s" % (max_len, )) % (
			name.replace("_", "-"), hlp)
	return 0


def main():
	init_logging()
	if len(sys.argv) < 2:
		sys.exit(show_help())
	if "-h" in sys.argv or "--help" in sys.argv:
		while "-h" in sys.argv:
			sys.argv.remove("-h")
		while "--help" in sys.argv:
			sys.argv.remove("--help")
		sys.exit(show_help(sys.argv[1].replace("-", "_") if len(sys.argv) > 1 else None))
	if "-v" in sys.argv:
		while "-v" in sys.argv:
			sys.argv.remove("-v")
		set_logging_level(True, True)
	else:
		set_logging_level(False, False)
	try:
		command = globals()["cmd_" + sys.argv[1].replace("-", "_")]
	except:
		print >>sys.stderr, "Unknown command: %s" % (sys.argv[1], )
		sys.exit(show_help(out=sys.stderr))
	
	try:
		sys.exit(command(sys.argv[0], sys.argv[2:]))
	except KeyboardInterrupt:
		sys.exit(0)
	except InvalidArguments:
		print >>sys.stderr, "Invalid arguments"
		print >>sys.stderr, ""
		show_help(sys.argv[1], out=sys.stderr)
		sys.exit(1)
