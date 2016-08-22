#!/usr/bin/env python2
"""
SC-Controller - Action Editor - "DPAD or Menu"

Setups DPAD emulation or menu display
"""
from __future__ import unicode_literals
from scc.tools import _

from gi.repository import Gtk, Gdk, GLib
from scc.actions import Action, NoAction, DPadAction, DPad8Action, ButtonAction
from scc.special_actions import MenuAction
from scc.modifiers import NameModifier
from scc.uinput import Keys
from scc.gui.ae import AEComponent, describe_action
from scc.gui.ae.menu_action import MenuActionCofC
from scc.gui.binding_editor import BindingEditor
from scc.gui.action_editor import ActionEditor


import os, logging
log = logging.getLogger("AE.DPAD")

__all__ = [ 'DPADComponent' ]


class DPADComponent(AEComponent, MenuActionCofC, BindingEditor):
	GLADE = "ae/dpad.glade"
	NAME = "dpad"
	CTXS = Action.AC_STICK | Action.AC_PAD
	PRIORITY = 2
	
	DPAD8_WIDGETS = [ 'btDPAD4', 'btDPAD5', 'btDPAD6', 'btDPAD7' ]
	
	def __init__(self, app, editor):
		AEComponent.__init__(self, app, editor)
		MenuActionCofC.__init__(self)
		BindingEditor.__init__(self, app)
		self._recursing = False
		self._userdata_load_started = False
		self.actions = [ NoAction() ] * 8
	
	
	def load(self):
		if self.loaded : return
		AEComponent.load(self)
		if self.app.osd_controller:
			self.builder.get_object("btEditMenu").set_visible(False)
			btDPAD1 = self.builder.get_object("btDPAD1")
			gr = btDPAD1.get_parent()
			gr.remove(btDPAD1)
			gr.attach(btDPAD1, 1, 1, 1, 1)
	
	
	def shown(self):
		if not self._userdata_load_started:
			self._userdata_load_started = True
			self.load_menu_list()
	
	
	def set_action(self, mode, action):
		cbm = self.builder.get_object("cbMenuType")
		cb = self.builder.get_object("cbActionType")
		if isinstance(action, DPadAction):
			self.set_cb(cbm, "menu", 1)
			if isinstance(action, DPad8Action):
				self.set_cb(cb, "dpad8", 1)
			else:
				self.set_cb(cb, "dpad", 1)
			self.update_button_desc(action)
		elif isinstance(action, MenuAction):
			self._current_menu = action.menu_id
			self.set_cb(cb, "menu", 1)
			self.set_cb(cbm, self.menu_class_to_key(action), 1)
		self.on_cbActionType_changed()
	
	
	def update_button_desc(self, action):
		for i in xrange(0, len(action.actions)):
			self.actions[i] = action.actions[i]
		for i in xrange(0, 8):
			self.set_button_desc(i)
	
	
	def set_button_desc(self, i):
		desc = describe_action(Action.AC_BUTTON, None, self.actions[i])
		l = self.builder.get_object("lblDPAD%s" % (i,))
		if l is None:
			l = self.builder.get_object("btDPAD%s" % (i,)).get_children()[0]
		l.set_markup(desc)
	
	
	def get_button_title(self):
		return _("DPAD or Menu")
	
	
	def handles(self, mode, action):
		if MenuActionCofC.handles(self, mode, action):
			return True
		return isinstance(action, DPadAction) # DPad8Action is derived from DPadAction
	
	
	def update(self):
		cb = self.builder.get_object("cbActionType")
		key = cb.get_model().get_value(cb.get_active_iter(), 1)
		if key == "dpad8":
			# 8-way dpad
			self.editor.set_action(DPad8Action(*self.actions))
		elif key == "dpad":
			# 4-way dpad
			self.editor.set_action(DPadAction(*self.actions[0:4]))
		elif key == "wsad":
			# special case of 4-way dpad
			a = DPadAction(ButtonAction(Keys.KEY_W), ButtonAction(Keys.KEY_S),
				ButtonAction(Keys.KEY_A), ButtonAction(Keys.KEY_D))
			self.actions = [ NoAction() ] * 8
			self.editor.set_action(a)
			self.update_button_desc(a)
		elif key == "arrows":
			# special case of 4-way dpad
			a = DPadAction(ButtonAction(Keys.KEY_UP),
				ButtonAction(Keys.KEY_DOWN), ButtonAction(Keys.KEY_LEFT),
				ButtonAction(Keys.KEY_RIGHT))
			self.actions = [ NoAction() ] * 8
			self.editor.set_action(a)
			self.update_button_desc(a)
		else:
			# Menu
			self.on_cbMenus_changed()
	
	
	def on_cbActionType_changed(self, *a):
		if self._recursing: return
		cb = self.builder.get_object("cbActionType")
		stActionData = self.builder.get_object("stActionData")
		key = cb.get_model().get_value(cb.get_active_iter(), 1)
		if key in ("dpad", "dpad8", "wsad", "arrows"):
			for i in self.DPAD8_WIDGETS:
				self.builder.get_object(i).set_visible(key == "dpad8")
			stActionData.set_visible_child(self.builder.get_object("grDPAD"))
		else: # key == "menu"
			stActionData.set_visible_child(self.builder.get_object("grMenu"))
		self.update()
	
	
	def on_action_chosen(self, i, action):
		self.actions[i] = action
		#if action.name:
		#	action = NameModifier(action.name, action)
		self.set_button_desc(i)
		self.update()
	
	
	def on_btDPAD_clicked(self, b):
		""" 'Select DPAD Left Action' handler """
		i = int(b.get_name())
		action = self.actions[i]
		#f isinstance(action, NameModifier):
		#action.action.name = action.name
		#action = action.action
		ae = self.choose_editor(action, "")
		# ae = ActionEditor(self.app, self.on_choosen)
		ae.set_title(_("Select DPAD Action"))
		ae.set_input(i, action, mode = Action.AC_BUTTON)
		ae.show(self.app.window)
