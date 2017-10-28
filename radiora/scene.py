#
# Classes which help define scenes for a RadioRA installation.  These classes are not required to use the functionality
# of the package, but they can simplify the declaration of a set of scenes.  See the test files for samples.
#
# Copyright (C) 2017 Ralph Lipe <ralph@lipe.ws>
#
# SPDX-License-Identifier:    MIT
"""\
Scenes and devices
"""
from radiora import RadioRA, _MasterControlFeedback, LocalZoneChange, STATE_ON, STATE_OFF

import logging
logger = logging.getLogger(__name__)


class Scene:
    def __init__(self, names, supports_on=True, supports_off=True, supports_dim=True):
        if isinstance(names, str):
            self.names = [names]
        else:
            self.names = names
        self.supports_on = supports_on
        self.supports_off = supports_off
        self.supports_dim = supports_dim

    def on(self, radiora):
        assert not self.supports_on
        logger.debug("Scene.on() method called for class that does not support on()")

    def dim(self, radiora):
        assert not self.supports_dim
        logger.debug("Scene.dim() method called for class that does not support dim()")

    def off(self, radiora):
        assert not self.supports_off
        logger.debug("Scene.off() method called for class that does not support off()")

    def __repr__(self):
        return "Scene {0}".format(self.names[0])


class PhantomButton(Scene):
    # Note that the default for a phantom button is that it does not support off.  If it is a room button, you can
    # set the button_number off to the same value.  If there are paired buttons (one turns thing off, and one turns
    # them on, then an "ON" command will be sent to the button_number_off because it is intended to turn off the
    # scene that the button_number_on turned on
    def __init__(self, names, button_on=0, button_off=0, button_dim=0):
        Scene.__init__(self, names,
                       supports_on=(button_on != 0), supports_off=(button_off != 0), supports_dim=(button_dim != 0))
        self.button_on = button_on
        self.button_off = button_off
        self.button_dim = button_dim

    def on(self, radiora):
        if self.supports_on:
            radiora.phantom_button_press(self.button_on, STATE_ON)
        else:
            Scene.on(self, radiora)

    def dim(self, radiora):
        if self.supports_dim:
            radiora.phantom_button_press(self.button_dim, STATE_ON)
        else:
            Scene.dim(self, radiora)

    def off(self, radiora):
        if self.supports_off:
            state_to_set = STATE_OFF if self.button_off == self.button_on else STATE_ON
            radiora.phantom_button_press(self.button_off, state_to_set)
        else:
            Scene.off(self, radiora)


class Zone(Scene):
    def __init__(self, names, zone_number, system,
                 supports_on=True, supports_off=True, supports_dim=True):
        Scene.__init__(self, names, supports_on=supports_on, supports_off=supports_off, supports_dim=supports_dim)
        self.zone_number = zone_number
        self.system = system

    @property
    def system_number(self) -> int:
        """Property always returns a number even if the system attribute is None.  If no system then returns 1."""
        return 1 if self.system is None else self.system

    def __repr__(self):
        return "{0}, {1}, zone number {2}, system {3}".format(self.__class__, self.names[0],
                                                              self.zone_number, self.system)


class Switch(Zone):
    def __init__(self, names, zone_number, system=None):
        Zone.__init__(self, names, zone_number, system, supports_dim=False)

    def on(self, radiora: RadioRA):
        radiora.set_switch_level(self.zone_number, STATE_ON, system=self.system)

    def off(self, radiora: RadioRA):
        radiora.set_switch_level(self.zone_number, STATE_OFF, system=self.system)


class Dimmer(Zone):
    def __init__(self, names, zone_number, system=None, dim_setting=50, on_setting=100):
        Zone.__init__(self, names, zone_number, system)
        self.dim_setting = dim_setting
        self.on_setting = on_setting

    def on(self, radiora):
        radiora.set_dimmer_level(self.zone_number, self.on_setting, system=self.system)

    def dim(self, radiora):
        radiora.set_dimmer_level(self.zone_number, self.dim_setting, system=self.system)

    def off(self, radiora):
        radiora.set_dimmer_level(self.zone_number, 0, system=self.system)


class GrafikEye(Zone):
    def __init__(self, names, zone_number, system=None, **kwargs):
        self.scenes = {}
        for key, value in kwargs.items():
            key = key.replace('_', ' ')   # take out all the underscores and replace them with spaces
            self.scenes[key] = value
        Zone.__init__(self, names, zone_number, system,
                      supports_on='on' in kwargs.keys(),
                      supports_off='off' in kwargs.keys(),
                      supports_dim='dim' in kwargs.keys())

    def on(self, radiora):
        if self.supports_on:
            radiora.set_grafik_eye_scene(self.zone_number, self.scenes['on'], self.system)
        else:
            Zone.on(self, radiora)

    def dim(self, radiora):
        if self.supports_dim:
            radiora.set_grafik_eye_scene(self.zone_number, self.scenes['dim'], self.system)
        else:
            Zone.dim(self, radiora)

    def off(self, radiora):
        if self.supports_off:
            radiora.set_grafik_eye_scene(self.zone_number, self.scenes['off'], self.system)
        else:
            Zone.off(self, radiora)


class SubScene(Scene):
    def __init__(self, names, grafik_eye: GrafikEye, on_scene, off_scene, dim_scene=None):
        Scene.__init__(self, names, supports_dim=(dim_scene is not None))
        self.grafik_eye = grafik_eye
        self.on_scene_number = grafik_eye.scenes[on_scene]
        self.off_scene_number = grafik_eye.scenes[off_scene]
        if dim_scene is None:
            self.dim_scene_number = None
        else:
            self.dim_scene_number = grafik_eye.scenes[dim_scene]

    def on(self, radiora):
        radiora.set_grafik_eye_scene(self.grafik_eye.zone_number, self.on_scene_number)

    def dim(self, radiora):
        if self.supports_dim:
            radiora.set_grafik_eye_scene(self.grafik_eye.zone_number, self.dim_scene_number)
        else:
            Scene.dim(self, radiora)

    def off(self, radiora):
        radiora.set_grafik_eye_scene(self.grafik_eye.zone_number, self.off_scene_number)


class CompositeScene(Scene):
    def __init__(self, names, child_scenes):
        self.child_scenes = child_scenes
        supports_dim = True
        for child in child_scenes:
            supports_dim = supports_dim and child.supports_dim
        Scene.__init__(self, names, supports_dim=supports_dim)

    def on(self, rr):
        for child in self.child_scenes:
            child.on(rr)

    def dim(self, rr):
        for child in self.child_scenes:
            child.dim(rr)

    def off(self, rr):
        for child in self.child_scenes:
            child.off(rr)


class SceneGroup(dict):
    def __init__(self, scenes=()):
        # If a caller wants a list of all scenes in this group they should not use the dictionary because there
        # are multiple keys per scene.  Use the SceneGroup.all_scenes member instead
        dict.__init__(self)
        self.zones = {1: {}, 2: {}}
        self.all_scenes = []
        self.add_scenes(scenes)

    def add_scene(self, scene):
        self.all_scenes.append(scene)
        for name in scene.names:
            self[name] = scene
        if isinstance(scene, Zone):
            self.zones[scene.system_number][scene.zone_number] = scene

    def add_scenes(self, scenes):
        for scene in scenes:
            self.add_scene(scene)

    def zone_for_feedback(self, feedback: LocalZoneChange) -> Zone:
        """If there is a zone in this group for the specified feedback then it is returned, else None"""
        if feedback.zone_number in self.zones[feedback.system_number]:
            return self.zones[feedback.system_number][feedback.zone_number]
        else:
            return None


class MasterControl:
    def __init__(self, name, master_control_number, system=None, **kwargs):
        """Buttons are a bi-directional lookup.  You can use a string or a button number"""
        self.name = name
        self.master_control_number = master_control_number
        self.system = system
        self.buttons = {}
        for key, value in kwargs.items():
            key = key.replace('_', ' ')   # take out all the underscores and replace them with spaces
            self.buttons[key] = value
            self.buttons[value] = key

    @property
    def system_number(self) -> int:
        """Property always returns a number even if the system attribute is None.  If no system then returns 1."""
        return 1 if self.system is None else self.system

    def __repr__(self):
        return "Master control {0}, number {1}, system {2}".format(self.name, self.master_control_number, self.system)


class MasterControlGroup(dict):
    def __init__(self, controls=()):
        dict.__init__(self)
        self.controls = {1: {}, 2: {}}
        self.add_controls(controls)

    def add_control(self, control):
        self[control.name] = control
        self.controls[control.system_number][control.master_control_number] = control

    def add_controls(self, controls):
        for control in controls:
            self.add_control(control)

    def control_for_feedback(self, feedback) -> MasterControl:
        """If there is a master control in this group for the specified feedback then it is returned, else None"""
        if (isinstance(feedback, _MasterControlFeedback)
                and feedback.master_control_number in self.controls[feedback.system_number]):
            return self.controls[feedback.system_number][feedback.master_control_number]
        else:
            return None