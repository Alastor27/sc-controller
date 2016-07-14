#!/usr/bin/env python2
"""
SC Controller - Modifiers

Modifier is Action that just sits between input and actual action, changing
way how resulting action works.
For example, click() modifier executes action only if pad is pressed.
"""
from __future__ import unicode_literals

from scc.actions import Action, MouseAction, XYAction, AxisAction, NoAction, ACTIONS
from scc.constants import FE_STICK, FE_TRIGGER, FE_PAD, STICK_PAD_MAX
from scc.constants import LEFT, RIGHT, STICK, SCButtons, HapticPos
from scc.controller import HapticData
from scc.uinput import Axes, Rels
from scc.tools import nameof
from math import pi as PI, sqrt, copysign
from collections import deque

import time, logging
log = logging.getLogger("Modifiers")
_ = lambda x : x

class Modifier(Action):
	def __init__(self):
		Action.__init__(self)
		self.action = NoAction()
	
	
	def __str__(self):
		return "<Modifier '%s' to %s>" % (self.COMMAND, self.action)
	
	__repr__ = __str__
	
	
	def set_haptic(self, hapticdata):
		if self.action:
			return self.action.set_haptic(hapticdata)
		return False
	
	
	def set_speed(self, x, y, z):
		if self.action:
			return self.action.set_speed(x, y, z)
		return False
	
	
	def connect(self, action):
		"""
		Connects modifier to action on right side of pipe.
		Raises TypeError if connection is not supported - for example,
		connecting `sens(2) | button` is not supported.
		
		Returns resulting, first-to-be-processed action, usualy self.
		
		Connection is attempted two times - for `modifier | action`,
		first modifier.connect(action) is called. If TypeError is thrown,
		action.connect_left(modifier) is called and ParseError is generated only
		if connectLeft method doesn't exists or throws TypeError as well.
		"""
		raise TypeError("Cannot connect %s to %s" % (self.COMMAND, action.COMMAND))


class NameModifier(Modifier):
	"""
	Simple modifier that sets name for child action.
	Used internally.
	"""
	COMMAND = "name"
	
	def __init__(self, name, action):
		Modifier.__init__(self)
		self.action = action
		self.set_name(name)
		self.action.set_name(name)
	
	
	def get_name(self):
		return self.name
	
	
	def strip(self):
		rv = self.action.strip()
		rv.set_name(self.name)
		return rv
	
	
	def compress(self):
		self.action = self.action.compress()
		if self.action:
			self.action.set_name(self.name)
		return self.action
	
	
	def to_string(self, multiline=False, pad=0):
		return ("name(" + repr(self.name).strip('u') + ", "
			+ self.action.to_string(multiline, pad) + ")")


class ClickModifier(Modifier):
	"""
	Allows inputs to be passed only if pad or stick is pressed.
	Used as `click | something`
	"""
	COMMAND = "click"
	
	def connect(self, action):
		# Anything can be connected after click
		self.action = action
		return self
	
	def describe(self, context):
		if context in (Action.AC_STICK, Action.AC_PAD):
			return _("(if pressed)") + "\n" + self.action.describe(context)
		else:
			return _("(if pressed)") + " " + self.action.describe(context)
	
	
	def to_string(self, multiline=False, pad=0):
		return "%sclick | %s" % (
			(" " * pad),
			self.action.to_string(multiline, pad).lstrip()
		)
	
	
	def strip(self):
		return self.action.strip()
	
	
	def compress(self):
		self.action = self.action.compress()
		return self
	
	
	# For button press & co it's safe to assume that they are being pressed...
	def button_press(self, mapper):
		return self.action.button_press(mapper)
	
	def button_release(self, mapper):
		return self.action.button_release(mapper)
	
	def trigger(self, mapper, position, old_position):
		return self.action.trigger(mapper, position, old_position)
	
	def axis(self, mapper, position, what):
		if what in (STICK, LEFT) and mapper.is_pressed(SCButtons.LPAD):
			if what == STICK: mapper.force_event.add(FE_STICK)
			return self.action.axis(mapper, position, what)
		if what in (STICK, LEFT) and mapper.was_pressed(SCButtons.LPAD):
			# Just released
			return self.action.axis(mapper, 0, what)
		# what == RIGHT, there are only three options
		if mapper.is_pressed(SCButtons.RPAD):
			return self.action.axis(mapper, position, what)
		if mapper.was_pressed(SCButtons.RPAD):
			# Just released
			return self.action.axis(mapper, 0, what)
	
	
	def pad(self, mapper, position, what):
		if what == LEFT and mapper.is_pressed(SCButtons.LPAD):
			if what == STICK: mapper.force_event.add(FE_STICK)
			return self.action.pad(mapper, position, what)
		if what == LEFT and mapper.was_pressed(SCButtons.LPAD):
			# Just released
			return self.action.pad(mapper, 0, what)
		# what == RIGHT, there are only two options
		if mapper.is_pressed(SCButtons.RPAD):
			return self.action.pad(mapper, position, what)
		if mapper.was_pressed(SCButtons.RPAD):
			# Just released
			return self.action.pad(mapper, 0, what)
	
	
	def whole(self, mapper, x, y, what):
		if what in (STICK, LEFT) and mapper.is_pressed(SCButtons.LPAD):
			if what == STICK: mapper.force_event.add(FE_STICK)
			return self.action.whole(mapper, x, y, what)
		if what in (STICK, LEFT) and mapper.was_pressed(SCButtons.LPAD):
			# Just released
			return self.action.whole(mapper, 0, 0, what)
		# what == RIGHT, there are only three options
		if mapper.is_pressed(SCButtons.RPAD):
			# mapper.force_event.add(FE_PAD)
			return self.action.whole(mapper, x, y, what)
		if mapper.was_pressed(SCButtons.RPAD):
			# Just released
			return self.action.whole(mapper, 0, 0, what)


class BallModifier(Modifier):
	"""
	Emulates ball-like movement with inertia and friction.
	Usefull for trackball and mouse wheel emulation.
	
	Reacts only to "whole" or "axis" inputs and sends generated movements as
	"change" input to child action.
	
	Used as `ball | mouse` or `ball | XY(axis(ABS_X), axis(ABS_Y))`
	"""
	COMMAND = "ball"
	
	DEFAULT_FRICTION = 10.0
	DEFAULT_MEAN_LEN = 10
	
	
	def __init__(self, *params):
		Modifier.__init__(self)
		if isinstance(params[0], Action):
			# TODO: Remove this, merge with _setup. It exists for backwards
			# compatibility, mainly because I'm retarded :(
			a, params = params[0], params[1:]
			self._setup(*params)
			self.connect(a)
		else:
			self._setup(*params)
		
	def _setup(self, friction=DEFAULT_FRICTION, mass=80.0,
			mean_len=DEFAULT_MEAN_LEN, r=0.02, ampli=65536, degree=40.0):
		self._friction = friction
		self._xvel = 0.0
		self._yvel = 0.0
		self._ampli  = ampli
		self._degree = degree
		self._radscale = (degree * PI / 180) / ampli
		self._mass = mass
		self._r = r
		self._I = (2 * self._mass * self._r**2) / 5.0
		self._a = self._r * self._friction / self._I
		self._xvel_dq = deque(maxlen=mean_len)
		self._yvel_dq = deque(maxlen=mean_len)
		self._lastTime = time.time()
		self._old_pos = None
	
	
	def connect(self, action):
		if not hasattr(action, "change"):
			# Not supported, call supermethod to raise exception
			Modifier.connect(self, action)
		self.action = action
		return self
	
	
	def _stop(self):
		""" Stops rolling of the 'ball' """
		self._xvel_dq.clear()
		self._yvel_dq.clear()
	
	
	def _add(self, dx, dy):
		# Compute time step
		_tmp = time.time()
		dt = _tmp - self._lastTime
		self._lastTime = _tmp
		
		# Compute instant velocity
		try:
			self._xvel = sum(self._xvel_dq) / len(self._xvel_dq)
			self._yvel = sum(self._yvel_dq) / len(self._yvel_dq)
		except ZeroDivisionError:
			self._xvel = 0.0
			self._yvel = 0.0

		self._xvel_dq.append(dx * self._radscale / dt)
		self._yvel_dq.append(dy * self._radscale / dt)
	
	
	def _roll(self, mapper):
		# Compute time step
		_tmp = time.time()
		dt = _tmp - self._lastTime
		self._lastTime = _tmp
		
		# Free movement update velocity and compute movement
		self._xvel_dq.clear()
		self._yvel_dq.clear()
		
		_hyp = sqrt((self._xvel**2) + (self._yvel**2))
		if _hyp != 0.0:
			_ax = self._a * (abs(self._xvel) / _hyp)
			_ay = self._a * (abs(self._yvel) / _hyp)
		else:
			_ax = self._a
			_ay = self._a
		
		# Cap friction desceleration
		_dvx = min(abs(self._xvel), _ax * dt)
		_dvy = min(abs(self._yvel), _ay * dt)
		
		# compute new velocity
		_xvel = self._xvel - copysign(_dvx, self._xvel)
		_yvel = self._yvel - copysign(_dvy, self._yvel)
		
		# compute displacement
		dx = (((_xvel + self._xvel) / 2) * dt) / self._radscale
		dy = (((_yvel + self._yvel) / 2) * dt) / self._radscale
		
		self._xvel = _xvel
		self._yvel = _yvel
		
		if dx or dy:
			self.action.change(mapper, dx, dy)
			mapper.schedule(0, self._roll)
	
	
	def describe(self, context):
		if self.get_name(): return self.get_name()
		# Special cases just to make GUI look pretty
		if isinstance(self.action, MouseAction):
			return _("Trackball")
		if isinstance(self.action, XYAction):
			if isinstance(self.action.x, AxisAction) and isinstance(self.action.y, AxisAction):
				x, y = self.action.x.parameters[0], self.action.y.parameters[0]
				if x == Axes.ABS_X and y == Axes.ABS_Y:
					return _("Mouse-like LStick")
				else:
					return _("Mouse-like RStick")
			if isinstance(self.action.x, MouseAction) and isinstance(self.action.y, MouseAction):
				x, y = self.action.x.parameters[0], self.action.y.parameters[0]
				if x in (Rels.REL_HWHEEL, Rels.REL_WHEEL) and y in (Rels.REL_HWHEEL, Rels.REL_WHEEL):
					return _("Mouse Wheel")
			
		return _("Ball(%s)") % (self.action.describe(context))
	
	
	def to_string(self, multiline=False, pad=0):
		return "%sball | %s" % (
			(" " * pad),
			self.action.to_string(multiline, pad).lstrip()
		)
	
	
	def pad(self, mapper, position, what):
		self.whole(mapper, position, 0, what)
	
	
	def whole(self, mapper, x, y, what):
		if mapper.is_touched(what):
			if self._old_pos and mapper.was_touched(what):
				dx, dy = x - self._old_pos[0], self._old_pos[1] - y
				self._add(dx, dy)
				self.action.change(mapper, dx, dy)
			else:
				self._stop()
			self._old_pos = x, y
		elif mapper.was_touched(what):
			self._roll(mapper)


class DeadzoneModifier(Modifier):
	COMMAND = "deadzone"
	
	def __init__(self, lower, upper=STICK_PAD_MAX):
		Modifier.__init__(self)
		
		self.lower = lower
		self.upper = upper
	
	
	def connect(self, action):
		# Not everything makes sense, but anything can be connected after deadzone
		self.action = action
		return self	
	
	
	def strip(self):
		return self.action.strip()
	
	
	def describe(self, context):
		dsc = self.action.describe(context)
		if "\n" in dsc:
			return "%s\n(with deadzone)" % (dsc,)
		else:
			return "%s (with deadzone)" % (dsc,)
	
	
	def to_string(self, multiline=False, pad=0):
		if self.upper == STICK_PAD_MAX:
			return "%sdeadzone(%s) | %s" % (
				(" " * pad), self.lower,
				self.action.to_string(multiline, pad).lstrip()
			)
		else:
			return "%sdeadzone(%s, %s) | %s" % (
				(" " * pad), self.lower, self.upper,
				self.action.to_string(multiline, pad).lstrip()
			)
	
	
	def trigger(self, mapper, position, old_position):
		if position < self.lower or position > self.upper:
			position = 0
		return self.action.trigger(mapper, position, old_position)
		
	
	def axis(self, mapper, position, what):
		if position < -self.upper or position > self.upper: position = 0
		if position > -self.lower and position < self.lower: position = 0
		return self.action.axis(mapper, position, what)
	
	
	def pad(self, mapper, position, what):
		if position < -self.upper or position > self.upper: position = 0
		if position > -self.lower and position < self.lower: position = 0
		return self.action.pad(mapper, position, what)
	
	
	def whole(self, mapper, x, y, what):
		dist = sqrt(x*x + y*y)
		if dist < -self.upper or dist > self.upper: x, y = 0, 0
		if dist > -self.lower and dist < self.lower: x, y = 0, 0
		return self.action.whole(mapper, x, y, what)


class ModeModifier(Modifier):
	COMMAND = "mode"
	MIN_TRIGGER = 2		# When trigger is bellow this position, list of held_triggers is cleared
	MIN_STICK = 2		# When abs(stick) < MIN_STICK, stick is considered released and held_sticks is cleared
	
	def __init__(self, *stuff):
		Modifier.__init__(self)
		self.default = None
		self.mods = {}
		self.held_buttons = set()
		self.held_sticks = set()
		self.held_triggers = {}
		self.order = []
		self.old_gyro = None
		self.timeout = DoubleclickModifier.DEAFAULT_TIMEOUT

		button = None
		for i in stuff:
			if self.default is not None:
				# Default has to be last parameter
				raise ValueError("Invalid parameters for 'mode'")
			if isinstance(i, Action):
				if button is None:
					self.default = i
					continue
				self.mods[button] = i
				self.order.append(button)
				button = None
			elif i in SCButtons:
				button = i
			else:
				raise ValueError("Invalid parameter for 'mode': %s" % (i,))
		if self.default is None:
			self.default = NoAction()
	
	
	def set_haptic(self, hapticdata):
		supports = False
		if self.default:
			supports = self.default.set_haptic(hapticdata) or supports
		for a in self.mods.values():
			supports = a.set_haptic(hapticdata) or supports
		return supports
	
	
	def set_speed(self, x, y, z):
		supports = False
		if self.default:
			supports = self.default.set_speed(x, y, z) or supports
		for a in self.mods.values():
			supports = a.set_speed(x, y, z) or supports
		return supports
	
	
	def strip(self):
		# Returns default action or action assigned to first modifier
		if self.default:
			return self.default.strip()
		if len(self.order) > 0:
			return self.mods[self.order[0]].strip()
		# Empty ModeModifier
		return NoAction()
	
	
	def compress(self):
		if self.default:
			self.default = self.default.compress()
		for button in self.mods:
			self.mods[button] = self.mods[button].compress()
		return self
	
	
	def __str__(self):
		rv = [ ]
		for key in self.mods:
			rv += [ key.name, self.mods[key] ]
		if self.default is not None:
			rv += [ self.default ]
		return "<Modifier '%s', %s>" % (self.COMMAND, rv)
	
	__repr__ = __str__
	
	
	def describe(self, context):
		l = []
		if self.default : l.append(self.default)
		for x in self.order:
			l.append(self.mods[x])
		return "\n".join([ x.describe(context) for x in l ])
	
	
	def to_string(self, multiline=False, pad=0):
		if multiline:
			rv = [ (" " * pad) + "mode(" ]
			for key in self.mods:
				a_str = self.mods[key].to_string(True).split("\n")
				a_str[0] = (" " * pad) + "  " + (key.name + ",").ljust(11) + a_str[0]	# Key has to be one of SCButtons
				for i in xrange(1, len(a_str)):
					a_str[i] = (" " * pad) + "  " + a_str[i]
				a_str[-1] = a_str[-1] + ","
				rv += a_str
			if self.default is not None:
				a_str = [
					(" " * pad) + "  " + x
					for x in  self.default.to_string(True).split("\n")
				]
				rv += a_str
			if rv[-1][-1] == ",":
				rv[-1] = rv[-1][0:-1]
			rv += [ (" " * pad) + ")" ]
			return "\n".join(rv)
		else:
			rv = [ ]
			for key in self.mods:
				rv += [ key.name, self.mods[key].to_string(False) ]
			if self.default is not None:
				rv += [ self.default.to_string(False) ]
			return "mode(" + ", ".join(rv) + ")"
	
	
	def select(self, mapper):
		"""
		Selects action by pressed button.
		"""
		for b in self.order:
			if mapper.is_pressed(b):
				return self.mods[b]
		return self.default
	
	
	def select_b(self, mapper):
		"""
		Same as select but returns button as well.
		"""
		for b in self.order:
			if mapper.is_pressed(b):
				return b, self.mods[b]
		return None, self.default
	
	
	def button_press(self, mapper):
		sel = self.select(mapper)
		self.held_buttons.add(sel)
		return sel.button_press(mapper)
	
	
	def button_release(self, mapper):
		# Releases all held buttons, not just button that matches
		# currently pressed modifier
		for b in self.held_buttons:
			b.button_release(mapper)
	
	
	def trigger(self, mapper, position, old_position):
		if position < ModeModifier.MIN_TRIGGER:
			for b in self.held_triggers:
				b.trigger(mapper, 0, self.held_triggers[b])
			self.held_triggers = {}
			return False
		else:
			sel = self.select(mapper)
			self.held_triggers[sel] = position
			return sel.trigger(mapper, position, old_position)
		
	
	def axis(self, mapper, position, what):
		return self.select(mapper).axis(mapper, position, what)
	
	
	def gyro(self, mapper, pitch, yaw, roll, *q):
		sel = self.select(mapper)
		if sel is not self.old_gyro:
			if self.old_gyro:
				self.old_gyro.gyro(mapper, 0, 0, 0, *q)
			self.old_gyro = sel
		return sel.gyro(mapper, pitch, yaw, roll, *q)
	
	def pad(self, mapper, position, what):
		return self.select(mapper).pad(mapper, position, what)
	
	def whole(self, mapper, x, y, what):
		if what == STICK:
			if abs(x) < ModeModifier.MIN_STICK and abs(y) < ModeModifier.MIN_STICK:
				for b in self.held_sticks:
					b.whole(mapper, 0, 0, what)
				self.held_sticks.clear()
			else:
				self.held_sticks.add(self.select(mapper))
				for b in self.held_sticks:
					b.whole(mapper, x, y, what)
		else:
			return self.select(mapper).whole(mapper, x, y, what)


class DoubleclickModifier(Modifier):
	COMMAND = "doubleclick"
	DEAFAULT_TIMEOUT = 0.2
	
	def __init__(self, doubleclickaction, normalaction=None, time=None):
		Modifier.__init__(self)
		self.action = doubleclickaction
		self.normalaction = normalaction or NoAction()
		self.holdaction = NoAction()
		self.timeout = time or DoubleclickModifier.DEAFAULT_TIMEOUT
		self.waiting = False
		self.pressed = False
		self.active = None
	
	
	def set_haptic(self, hapticdata):
		supports = self.action.set_haptic(hapticdata)
		if self.normalaction:
			supports = self.normalaction.set_haptic(hapticdata) or supports
		if self.holdaction:
			supports = self.holdaction.set_haptic(hapticdata) or supports
		return supports
	
	
	def set_speed(self, x, y, z):
		supports = self.action.set_speed(x, y, z)
		if self.normalaction:
			supports = self.normalaction.set_speed(x, y, z) or supports
		if self.holdaction:
			supports = self.holdaction.set_speed(x, y, z) or supports
		return supports
	
	
	def strip(self):
		if self.holdaction:
			return self.holdaction.strip()
		return self.action.strip()
	
	
	def compress(self):
		self.action = self.action.compress()
		self.holdaction = self.holdaction.compress()
		self.normalaction = self.normalaction.compress()
		
		if isinstance(self.normalaction, DoubleclickModifier):
			self.action = self.action.compress() or self.normalaction.action.compress()
			self.holdaction = self.holdaction.compress() or self.normalaction.holdaction.compress()
			self.normalaction = self.normalaction.normalaction.compress()
		elif isinstance(self.action, HoldModifier):
			self.holdaction = self.action.holdaction.compress()
			self.action = self.action.normalaction.compress()
		elif isinstance(self.holdaction, DoubleclickModifier):
			self.action = self.holdaction.action.compress()
			self.holdaction = self.holdaction.normalaction.compress()
		elif isinstance(self.holdaction, DoubleclickModifier):
			self.action = self.action.compress() or self.holdaction.action.compress()
			self.normalaction = self.normalaction.compress() or self.holdaction.normalaction.compress()
			self.holdaction = self.holdaction.holdaction.compress()
		return self
	
	
	def __str__(self):
		l = [ self.action ]
		if self.normalaction:
			l += [ self.normalaction ]
		return "<Modifier %s dbl='%s' hold='%s' normal='%s'>" % (
			self.COMMAND, self.action, self.holdaction, self.normalaction )
	
	__repr__ = __str__
	
	
	def describe(self, context):
		l = [ ]
		if self.action:
			l += [ self.action ]
		if self.holdaction:
			l += [ self.holdaction ]
		if self.normalaction:
			l += [ self.normalaction ]
		return "\n".join([ x.describe(context) for x in l ])
	
	
	def to_string(self, multiline=False, pad=0):
		firstline, lastline = "", ""
		if self.action:
			firstline += DoubleclickModifier.COMMAND + "(" + self.action.to_string() + ","
		if self.holdaction:
			firstline += HoldModifier.COMMAND + "(" + self.holdaction.to_string() + ","
		lastline += ", " + str(self.timeout)
		lastline += ")"
		
		if multiline:
			if self.normalaction:
				rv = [ (" " * pad) + firstline ]
				rv += self.normalaction.to_string(True, pad+2).split("\n")
				rv += [ (" " * pad) + lastline ]
			else:
				rv = [ firstline.strip(",") + lastline ]
			return "\n".join(rv)
		elif self.normalaction:
			return firstline + self.normalaction.to_string() + lastline
		else:
			return firstline.strip(",") + lastline
	
	
	def button_press(self, mapper):
		self.pressed = True
		if self.waiting:
			# Double-click happened
			mapper.remove_scheduled(self.on_timeout)
			self.waiting = False
			self.active = self.action
			self.active.button_press(mapper)
		else:
			# First click, start the timer
			self.waiting = True
			mapper.schedule(self.timeout, self.on_timeout)
	
	
	def button_release(self, mapper):
		self.pressed = False
		if self.waiting and self.active is None and not self.action:
			# In HoldModifier, button released before timeout
			mapper.remove_scheduled(self.on_timeout)
			self.waiting = False
			if self.normalaction:
				self.normalaction.button_press(mapper)
				self.normalaction.button_release(mapper)
		elif self.active:
			# Released held button
			self.active.button_release(mapper)
			self.active = None
	
	
	def on_timeout(self, mapper, *a):
		if self.waiting:
			self.waiting = False
			if self.pressed:
				# Timeouted while button is still pressed
				self.active = self.holdaction if self.holdaction else self.normalaction
				self.active.button_press(mapper)
			elif self.normalaction:
				# User did short click and nothing else
				self.normalaction.button_press(mapper)
				self.normalaction.button_release(mapper)


class HoldModifier(DoubleclickModifier):
	# Hold modifier is implemented as part of DoubleclickModifier, because
	# situation when both are assigned to same button needs to be treated
	# specially.
	COMMAND = "hold"
	
	def __init__(self, holdaction, normalaction=None, time=None):
		DoubleclickModifier.__init__(self, NoAction(), normalaction, time)
		self.holdaction = holdaction


class SensitivityModifier(Modifier):
	COMMAND = "sens"
	def __init__(self, *speeds):
		Modifier.__init__(self)
		speeds = [ float(s) for s in speeds ]
		while len(speeds) < 3:
			speeds.append(1.0)
		self.parameters = speeds
	
	
	def connect(self, action):
		# Anything can be connected to sensitivity
		self.action = action
		action.set_speed(*self.parameters)
		return self
	
	
	def connect(self, action):
		# Not everything makes sense, but anything can be connected after deadzone
		self.action = action
		return self	
	
	
	def strip(self):
		return self.action.strip()
	
	
	def describe(self, context):
		if self.get_name(): return self.get_name()
		return self.action.describe(context)
	
	
	def to_string(self, multiline=False, pad=0):
		params = self.parameters
		while len(params) > 1 and params[-1] == 1.0:
			params = params[0:-1]
		return "%ssens(%s) | %s" % (
			(" " * pad),
			", ".join([ str(p) for p in params ]),
			self.action.to_string(multiline, pad).lstrip()
		)
	
	
	def __str__(self):
		return "<Sensitivity=%s, %s>" % (self.parameters, self.action)
	
	
	def compress(self):
		return self.action.compress()


class FeedbackModifier(Modifier):
	"""
	Enables haptic feedback for specified action, if action supports
	haptic feedback.
	
	Feedback supporting action has to have set_haptic method defined, usually
	by inheriting from HapticEnabledAction. If action doesn't have such method,
	or if calling it raises TypeError, parser will report error.
	
	Used as `something | feedback(side)`
	"""
	COMMAND = "feedback"
	
	def __init__(self, *params):
		""" Takes same params as HapticData """
		Modifier.__init__(self)
		self.haptic = HapticData(*params)
		self.parameters = params
	
	
	def connect_left(self, action):
		if self.action:
			# Already has action, but something may be able to connect to it
			# (for example `ball | mouse | feedback` )
			if hasattr(action, "connect"):
				self.action = action.connect(self.action)
				return self
		if hasattr(action, "set_haptic"):
			action.set_haptic(self.haptic)	# May throw TypeError
			self.action = action
			return self
		# Call supermethod to throw error
		raise TypeError("Cannot attach feedback to %s" % (action.COMMAND))
	
	
	def describe(self, context):
		if self.get_name(): return self.get_name()
		return self.action.describe(context)
	
	
	def to_string(self, multiline=False, pad=0):
		return "%s | feedback(%s)" % (
			self.action.to_string(multiline, pad),
			",".join([ nameof(p) for p in self.parameters ])
		)
	
	
	def __str__(self):
		return "<with Feedback %s %s>" % (
			",".join([ nameof(p) for p in self.parameters ]),
			self.action
		)
	
	
	def strip(self):
		return self.action.strip()
	
	def compress(self):
		return self.action.compress()


# Add modifiers to ACTIONS dict
for i in [ globals()[x] for x in dir() if hasattr(globals()[x], 'COMMAND') ]:
	if i.COMMAND is not None:
		ACTIONS[i.COMMAND] = i
ACTIONS['sensitivity'] = ACTIONS['sens']