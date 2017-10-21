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
from radiora import RadioRA, STATE_ON, STATE_OFF

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


class PhantomButton(Scene):
    # Note that the default for a phantom button is that it does not support off.  If it is a room button, you can
    # set the button_number off to the same value.  If there are paired buttons (one turns thing off, and one turns
    # them on, then an "ON" command will be sent to the button_number_off because it is intended to turn off the
    # scene that the button_number_on turned on
    def __init__(self, names, button_number_on, button_number_off=0, button_number_dim=0):
        Scene.__init__(self, names, supports_off=(button_number_on != 0), supports_dim=(button_number_dim != 0))
        self.button_number_on = button_number_on
        self.button_number_off = button_number_off
        self.button_number_dim = button_number_dim

    def on(self, radiora):
        radiora.phantom_button_press(self.button_number_on, STATE_ON)

    def dim(self, radiora):
        radiora.phantom_button_press(self.button_number_dim, STATE_ON)

    def off(self, radiora):
        assert self.supports_off
        state_to_set = STATE_OFF if self.button_number_off == self.button_number_on else STATE_ON
        radiora.phantom_button_press(self.button_number_off, state_to_set)


class Zone(Scene):
    def __init__(self, names: [str], zone_number: int, supports_on=True, supports_off=True, supports_dim=True):
        Scene.__init__(self, names, supports_on=supports_on, supports_off=supports_off, supports_dim=supports_dim)
        self.zone_number = zone_number


class Switch(Zone):
    def __init__(self, names, zone_number):
        Zone.__init__(self, names, zone_number, supports_dim=False)

    def on(self, radiora: RadioRA):
        radiora.set_switch_level(self.zone_number, STATE_ON)

    def off(self, radiora: RadioRA):
        radiora.set_switch_level(self.zone_number, STATE_OFF)


class Dimmer(Zone):
    def __init__(self, names, zone_number, dim_setting=50, on_setting=100):
        Zone.__init__(self, names, zone_number)
        self.dim_setting = dim_setting
        self.on_setting = on_setting

    def on(self, radiora):
        radiora.set_dimmer_level(self.zone_number, self.on_setting)

    def dim(self, radiora):
        radiora.set_dimmer_level(self.zone_number, self.dim_setting)

    def off(self, radiora):
        radiora.set_dimmer_level(self.zone_number, 0)


class GrafikEye(Zone):
    def __init__(self, names, zone_number, **kwargs):
        self.scenes = {}
        for key, value in kwargs.items():
            key = key.replace('_', ' ')   # take out all the underscores and replace them with spaces
            self.scenes[key] = value
            print("    {0} = {1}".format(key, value))
        Zone.__init__(self, names, zone_number,
                      supports_on='on' in kwargs.keys(),
                      supports_off='off' in kwargs.keys(),
                      supports_dim='dim' in kwargs.keys())

    def on(self, radiora):
        radiora.set_grafik_eye_scene(self.zone_number, self.scenes['on'])

    def dim(self, radiora):
        radiora.set_grafik_eye_scene(self.zone_number, self.scenes['dim'])

    def off(self, radiora):
        radiora.set_grafik_eye_scene(self.zone_number, self.scenes['off'])


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
        radiora.set_grafik_eye_scene(self.grafik_eye.zone_number, self.dim_scene_number)

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
    def __init__(self, scenes=None):
        # If a caller wants a list of all scenes in this group they should not use the dictionary because there
        # are multiple keys per scene.  Use the SceneGroup.all_scenes member instead
        dict.__init__(self)
        self.all_scenes = []
        if scenes is not None:
            self.add_scenes(scenes)

    def add_scene(self, scene):
        self.all_scenes.append(scene)
        for name in scene.names:
            print("ADDING {0}".format(name))
            self[name] = scene

    def add_scenes(self, scenes):
        for scene in scenes:
            self.add_scene(scene)
