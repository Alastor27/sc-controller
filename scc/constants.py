#!/usr/bin/env python

# The MIT License (MIT)
#
# Copyright (c) 2015 Stany MARCEL <stanypub@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from scc.lib import IntEnum
from scc.uinput import Axes, Keys

"""
If SC-Controller is updated while daemon is running, DAEMON_VERSION send by
daemon will differ one one expected by UI and daemon will be forcefully restarted.
"""
DAEMON_VERSION = "0.3"

HPERIOD  = 0.02
LPERIOD  = 0.5
DURATION = 1.0

FE_STICK	= 1
FE_TRIGGER	= 2
FE_PAD		= 3
FE_GYRO		= 4

LEFT	= "LEFT"
RIGHT	= "RIGHT"
WHOLE	= "WHOLE"
STICK	= "STICK"
GYRO	= "GYRO"
PITCH	= "PITCH"
YAW		= "YAW"
ROLL	= "ROLL"
SAME	= "SAME"	# may be used with MenuAction

PARSER_CONSTANTS = ( LEFT, RIGHT, WHOLE, STICK, GYRO, PITCH, YAW, ROLL, SAME )



class SCButtons(IntEnum):
	RPADTOUCH	= 0b00010000000000000000000000000000
	LPADTOUCH	= 0b00001000000000000000000000000000
	RPAD		= 0b00000100000000000000000000000000
	LPAD		= 0b00000010000000000000000000000000 # Same for stick but without LPadTouch
	STICK		= 0b00000000000000000000000000000001 # generated internally, not sent by controller
	RGRIP	 	= 0b00000001000000000000000000000000
	LGRIP	 	= 0b00000000100000000000000000000000
	START	 	= 0b00000000010000000000000000000000
	C		 	= 0b00000000001000000000000000000000
	BACK		= 0b00000000000100000000000000000000
	A			= 0b00000000000000001000000000000000
	X			= 0b00000000000000000100000000000000
	B			= 0b00000000000000000010000000000000
	Y			= 0b00000000000000000001000000000000
	LB			= 0b00000000000000000000100000000000
	RB			= 0b00000000000000000000010000000000
	LT			= 0b00000000000000000000001000000000
	RT			= 0b00000000000000000000000100000000


class HapticPos(IntEnum):
	"""Specify witch pad or trig is used"""
	RIGHT = 0
	LEFT = 1
	BOTH = 2	# emulated

STICK_PAD_MIN = -32768
STICK_PAD_MAX = 32768
STICK_PAD_MIN_HALF = STICK_PAD_MIN / 3
STICK_PAD_MAX_HALF = STICK_PAD_MAX / 3

TRIGGER_MIN = 0
TRIGGER_HALF = 50
TRIGGER_CLICK = 254 # Values under this are generated until trigger clicks
TRIGGER_MAX = 255

ALL_BUTTONS = ( Keys.BTN_START, Keys.BTN_MODE, Keys.BTN_SELECT, Keys.BTN_A,
	Keys.BTN_B, Keys.BTN_X, Keys.BTN_Y, Keys.BTN_TL, Keys.BTN_TR,
	Keys.BTN_THUMBL, Keys.BTN_THUMBR, Keys.BTN_WHEEL, Keys.BTN_GEAR_DOWN,
	Keys.BTN_GEAR_UP, Keys.KEY_OK, Keys.KEY_SELECT, Keys.KEY_GOTO,
	Keys.KEY_CLEAR, Keys.KEY_OPTION, Keys.KEY_INFO, Keys.KEY_TIME,
	Keys.KEY_VENDOR, Keys.KEY_ARCHIVE, Keys.KEY_PROGRAM, Keys.KEY_CHANNEL,
	Keys.KEY_FAVORITES, Keys.KEY_EPG )

ALL_AXES = ( Axes.ABS_X, Axes.ABS_Y, Axes.ABS_RX, Axes.ABS_RY, Axes.ABS_Z,
	Axes.ABS_RZ, Axes.ABS_HAT0X, Axes.ABS_HAT0Y, Axes.ABS_HAT1X, Axes.ABS_HAT1Y,
	Axes.ABS_HAT2X, Axes.ABS_HAT2Y, Axes.ABS_HAT3X, Axes.ABS_HAT3Y,
	Axes.ABS_PRESSURE, Axes.ABS_DISTANCE, Axes.ABS_TILT_X, Axes.ABS_TILT_Y,
	Axes.ABS_TOOL_WIDTH, Axes.ABS_VOLUME, Axes.ABS_MISC )
