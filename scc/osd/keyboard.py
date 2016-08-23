#!/usr/bin/env python2
"""
SC-Controller - OSD Menu

Display menu that user can navigate through and print chosen item id to stdout
"""
from __future__ import unicode_literals
from scc.tools import _, set_logging_level

from gi.repository import Gtk, Gdk, GdkX11, GLib
from scc.constants import LEFT, RIGHT, STICK, STICK_PAD_MIN, STICK_PAD_MAX
from scc.constants import STICK_PAD_MIN_HALF, STICK_PAD_MAX_HALF
from scc.constants import SCButtons
from scc.tools import point_in_gtkrect, circle_to_square, find_profile, clamp
from scc.paths import get_share_path, get_config_path
from scc.parser import TalkingActionParser
from scc.menu_data import MenuData
from scc.actions import Action
from scc.profile import Profile
from scc.config import Config
from scc.uinput import Keys
from scc.lib import xwrappers as X
from scc.gui.daemon_manager import DaemonManager
from scc.gui.svg_widget import SVGWidget
from scc.gui.gdk_to_key import KEY_TO_GDK
from scc.osd.timermanager import TimerManager
from scc.osd.slave_mapper import SlaveMapper
from scc.osd import OSDWindow
import scc.osd.osk_actions

import os, sys, json, logging
log = logging.getLogger("osd.menu")


class Keyboard(OSDWindow, TimerManager):
	EPILOG="""Exit codes:
   0  - clean exit, user closed keyboard
   1  - error, invalid arguments
   2  - error, failed to access sc-daemon, sc-daemon reported error or died while menu is displayed.
   3  - erorr, failed to lock input stick, pad or button(s)
	"""
	OSK_PROF_NAME = ".scc-osd.keyboard"
	RECOLOR_BACKGROUNDS = ( "button1", "button2", "text", "background" )
	RECOLOR_STROKES = ( "button1_border", "button2_border", "text" )
	
	BUTTON_MAP = {
		SCButtons.A.name : Keys.KEY_ENTER,
		SCButtons.B.name : Keys.KEY_ESC,
		SCButtons.LB.name : Keys.KEY_BACKSPACE,
		SCButtons.RB.name : Keys.KEY_SPACE,
		SCButtons.LGRIP.name : Keys.KEY_LEFTSHIFT,
		SCButtons.RGRIP.name : Keys.KEY_RIGHTALT,
	}
	
	def __init__(self, config=None):
		OSDWindow.__init__(self, "osd-keyboard")
		TimerManager.__init__(self)
		self.daemon = None
		self.mapper = None
		self.keymap = Gdk.Keymap.get_default()
		self.keymap.connect('state-changed', self.on_state_changed)
		Action.register_all(sys.modules['scc.osd.osk_actions'], prefix="OSK")
		self.profile = Profile(TalkingActionParser())
		self.config = config or Config()
		
		self.kbimage = os.path.join(get_config_path(), 'keyboard.svg')
		if not os.path.exists(self.kbimage):
			# Prefer image in ~/.config/scc, but load default one as fallback
			self.kbimage = os.path.join(get_share_path(), "images", 'keyboard.svg')
		self.background = SVGWidget(self, self.kbimage, init_hilighted=False)
		self.recolor()
		
		self.limits = {}
		self.limits[LEFT]  = self.background.get_rect_area("LIMIT_LEFT")
		self.limits[RIGHT] = self.background.get_rect_area("LIMIT_RIGHT")
		
		cursor = os.path.join(get_share_path(), "images", 'menu-cursor.svg')
		self.cursors = {}
		self.cursors[LEFT] = Gtk.Image.new_from_file(cursor)
		self.cursors[LEFT].set_name("osd-keyboard-cursor")
		self.cursors[RIGHT] = Gtk.Image.new_from_file(cursor)
		self.cursors[RIGHT].set_name("osd-keyboard-cursor")
		
		self._eh_ids = []
		self._stick = 0, 0
		self._hovers = { self.cursors[LEFT] : None, self.cursors[RIGHT] : None }
		self._pressed = { self.cursors[LEFT] : None, self.cursors[RIGHT] : None }
		self._pressed_areas = {}
		
		self.c = Gtk.Box()
		self.c.set_name("osd-keyboard-container")
		
		self.f = Gtk.Fixed()
		self.f.add(self.background)
		self.f.add(self.cursors[LEFT])
		self.f.add(self.cursors[RIGHT])
		self.c.add(self.f)
		self.add(self.c)
		
		self.timer('labels', 0.1, self.update_labels)
	
	
	def recolor(self):
		source_colors = {}
		try:
			# Try to read json file and bail out if it fails
			source_colors = json.loads(open(self.kbimage + ".json", "r").read())['colors']
		except Exception, e:
			log.warning("Failed to load keyboard description")
			log.warning(e)
			return
		
		editor = self.background.edit()
		
		for k in Keyboard.RECOLOR_BACKGROUNDS:
			if k in self.config['osk_colors'] and k in source_colors:
				editor.recolor_background(source_colors[k], self.config['osk_colors'][k])
		editor.recolor_background(source_colors["background"], self.config['osd_colors']["background"])
		
		for k in Keyboard.RECOLOR_STROKES:
			if k in self.config['osk_colors'] and k in source_colors:
				editor.recolor_strokes(source_colors[k], self.config['osk_colors'][k])
		
		editor.commit()
	
	
	def use_daemon(self, d):
		"""
		Allows (re)using already existing DaemonManager instance in same process
		"""
		self.daemon = d
		self._cononect_handlers()
		self.on_daemon_connected(self.daemon)
	
	
	def on_state_changed(self, x11keymap):
		if not self.timer_active('labels'):
			self.timer('labels', 0.1, self.update_labels)
	
	
	def update_labels(self):
		""" Updates keyboard labels based on active X keymap """
		labels = {}
		# Get current layout group
		dpy = X.Display(hash(GdkX11.x11_get_default_xdisplay()))		# Still no idea why...
		group = X.get_xkb_state(dpy).group
		# Get state of shift/alt/ctrl key
		mt = Gdk.ModifierType(self.keymap.get_modifier_state())
		for a in self.background.areas:
			# Iterate over all translatable keys...
			if hasattr(Keys, a.name) and getattr(Keys, a.name) in KEY_TO_GDK:
				# Try to convert GKD key to keycode
				gdkkey = KEY_TO_GDK[getattr(Keys, a.name)]
				found, entries = self.keymap.get_entries_for_keyval(gdkkey)
				
				if gdkkey == Gdk.KEY_equal:
					# Special case, GDK reports nonsense here
					entries = [ [ e for e in entries if e.level == 0 ][-1] ]
				
				if not found: continue
				for k in sorted(entries, key=lambda a : a.level):
					# Try to convert keycode to label
					translation = self.keymap.translate_keyboard_state(k.keycode, mt, group)
					if hasattr(translation, "keyval"):
						code = Gdk.keyval_to_unicode(translation.keyval)
					else:
						code = Gdk.keyval_to_unicode(translation[1])
					if code != 0:
						labels[a.name] = unichr(code)
						break
		
		self.background.edit().set_labels(labels).commit()
	
	
	def parse_argumets(self, argv):
		if not OSDWindow.parse_argumets(self, argv):
			return False
		return True
	
	
	def _cononect_handlers(self):
		self._eh_ids += [
			self.daemon.connect('dead', self.on_daemon_died),
			self.daemon.connect('error', self.on_daemon_died),
			self.daemon.connect('event', self.on_event),
			self.daemon.connect('reconfigured', self.on_reconfigured),
			self.daemon.connect('alive', self.on_daemon_connected),
		]
	
	
	def run(self):
		self.daemon = DaemonManager()
		self._cononect_handlers()
		OSDWindow.run(self)
	
	
	def on_reconfigured(self, *a):
		self.profile.load(find_profile(Keyboard.OSK_PROF_NAME)).compress()
		log.debug("Reloaded profile")
	
	
	def on_daemon_died(self, *a):
		log.error("Daemon died")
		self.quit(2)
	
	
	def on_failed_to_lock(self, error):
		log.error("Failed to lock input: %s", error)
		self.quit(3)
	
	
	def on_daemon_connected(self, *a):
		self.lock_inputs()
	
	
	def lock_inputs(self):
		def success(*a):
			log.info("Sucessfully locked input")
			pass
		
		# Lock everything
		locks = [ LEFT, RIGHT, STICK ] + [ b.name for b in SCButtons ]
		self.daemon.lock(success, self.on_failed_to_lock, *locks)
	
	
	def unlock_inputs(self):
		self.daemon.unlock_all()
	
	
	def quit(self, code=-1):
		self.unlock_inputs()
		for x in self._eh_ids:
			self.daemon.disconnect(x)
		self._eh_ids = []
		del self.mapper
		OSDWindow.quit(self, code)
	
	
	def show(self, *a):
		OSDWindow.show(self, *a)
		self.profile.load(find_profile(Keyboard.OSK_PROF_NAME)).compress()
		self.create_mapper()
		self.set_cursor_position(0, 0, self.cursors[LEFT], self.limits[LEFT])
		self.set_cursor_position(0, 0, self.cursors[RIGHT], self.limits[RIGHT])
	
	
	def create_mapper(self):
		self.mapper = SlaveMapper(self.profile, keyboard=b"SCC OSD Keyboard")
		self.mapper.set_special_actions_handler(self)
	
	
	def on_event(self, daemon, what, data):
		"""
		Called when button press, button release or stick / pad update is
		send by daemon.
		"""
		self.mapper.handle_event(daemon, what, data)	
	
	
	def on_sa_close(self, *a):
		""" Called by CloseOSDKeyboardAction """
		self.quit(0)
	
	
	def on_sa_cursor(self, mapper, action, x, y):
		self.set_cursor_position(
			x * action.speed[0],
			y * action.speed[1],
			self.cursors[action.side], self.limits[action.side])
	
	
	def on_sa_move(self, mapper, action, x, y):
		self._stick = x, y
		if not self.timer_active('stick'):
			self.timer("stick", 0.05, self._move_window)
	
	
	def on_sa_press(self, mapper, action, pressed):
		self.key_from_cursor(self.cursors[action.side], pressed)
	
	
	def set_cursor_position(self, x, y, cursor, limit):
		"""
		Moves cursor image.
		"""
		w = limit[2] - (cursor.get_allocation().width * 0.5)
		h = limit[3] - (cursor.get_allocation().height * 0.5)
		x = x / float(STICK_PAD_MAX)
		y = y / float(STICK_PAD_MAX) * -1.0
		
		x, y = circle_to_square(x, y)
		
		x = clamp(
			cursor.get_allocation().width * 0.5,
			(limit[0] + w * 0.5) + x * w * 0.5,
			self.get_allocation().width - cursor.get_allocation().width
			)
		
		y = clamp(
			cursor.get_allocation().height * 0.5,
			(limit[1] + h * 0.5) + y * h * 0.5,
			self.get_allocation().height - cursor.get_allocation().height
			)
		
		cursor.position = int(x), int(y)
		self.f.move(cursor,
			x - cursor.get_allocation().width * 0.5,
			y - cursor.get_allocation().height * 0.5)
		for a in self.background.areas:
			if a.contains(x, y):
				if a != self._hovers[cursor]:
					self._hovers[cursor] = a
					if self._pressed[cursor] is not None:
						self.mapper.keyboard.releaseEvent([ self._pressed[cursor] ])
						self.key_from_cursor(cursor, True)
					if not self.timer_active('redraw'):
						self.timer('redraw', 0.01, self.redraw_background)
					break
	
	
	def redraw_background(self, *a):
		"""
		Updates hilighted keys on bacgkround image.
		"""
		hilights = {
			"AREA_" + a.name : "#" + self.config['osk_colors']['hilight']
			for a in [ a for a in self._hovers.values() if a ]
		}
		hilights.update({
			"AREA_" + a.name : "#" + self.config['osk_colors']['pressed']
			for a in self._pressed_areas.values()
		})
		
		self.background.hilight(hilights)
	
	
	def _move_window(self, *a):
		"""
		Called by timer while stick is tilted to move window around the screen.
		"""
		x, y = self._stick
		x = x * 50.0 / STICK_PAD_MAX
		y = y * -50.0 / STICK_PAD_MAX
		rx, ry = self.get_position()
		self.move(rx + x, ry + y)
		if abs(self._stick[0]) > 100 or abs(self._stick[1]) > 100:
			self.timer("stick", 0.05, self._move_window)
	
	
	def key_from_cursor(self, cursor, pressed):
		"""
		Sends keypress/keyrelease event to emulated keyboard, based on
		position of cursor on OSD keyboard.
		"""
		x, y = cursor.position
		
		if pressed:
			for a in self.background.areas:
				if a.contains(x, y):
					if a.name.startswith("KEY_") and hasattr(Keys, a.name):
						key = getattr(Keys, a.name)
						if self._pressed[cursor] is not None:
							self.mapper.keyboard.releaseEvent([ self._pressed[cursor] ])
						self.mapper.keyboard.pressEvent([ key ])
						self._pressed[cursor] = key
						self._pressed_areas[cursor] = a
					break
		elif self._pressed[cursor] is not None:
			self.mapper.keyboard.releaseEvent([ self._pressed[cursor] ])
			self._pressed[cursor] = None
			del self._pressed_areas[cursor]
		if not self.timer_active('redraw'):
			self.timer('redraw', 0.01, self.redraw_background)

