#!/usr/bin/env python

#################################################
# Module: Traffic Bar
# Topher 2024
# 2/10/2025 - new dataship refactor

from lib.modules._module import Module
from lib import hud_graphics
from lib import hud_utils
from lib import smartdisplay
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_targets import TargetData
from lib.common.dataship.dataship_imu import IMUData
from lib.common.dataship.dataship_gps import GPSData
from lib.common import shared
import pygame
import math


class traffic_bar(Module):
    # called only when object is first created.
    def __init__(self):
        Module.__init__(self)
        self.name = "Traffic Bar"  # set name
        self.target_font_size = hud_utils.readConfigInt("HUD", "target_font_size", 40)
        self.showTrafficMiles = hud_utils.readConfigInt("HUD", "show_traffic_within_miles", 25)
        self.fov_x = hud_utils.readConfigFloat("HUD", "fov_x", 13.942)
        self.colorTarget = (255,200,130)
        self.colorDetails = (128,128,128) #grey
        self.targetData = TargetData()
        self.imuData = IMUData()
        self.gpsData = GPSData()
    # called once for setup, or when module is being resized in editor
    def initMod(self, pygamescreen, width=None, height=None):
        if width is None:
            width = pygamescreen.get_width() # default width
        if height is None:
            height = 100 # default height
        Module.initMod(
            self, pygamescreen, width, height
        )  # call parent init screen.
        print(("Init Mod: %s %dx%d"%(self.name,self.width,self.height)))

        # fonts
        self.font_target = pygame.font.SysFont(None, self.target_font_size)
        self.offscreen_surface = None  # only used if we can't draw directly to the display

        # traffic range
        self.fov_x_each_side = self.fov_x / 2
        self.x_degree_per_pixel = self.fov_x / self.width

        if len(shared.Dataship.targetData) > 0:
            self.targetData = shared.Dataship.targetData[0]

        if len(shared.Dataship.imuData) > 0:
            self.imuData = shared.Dataship.imuData[0]

        if len(shared.Dataship.gpsData) > 0:
            self.gpsData = shared.Dataship.gpsData[0]

    # called every redraw for the module
    def draw(self, dataship: Dataship, smartdisplay, pos=(0, 0)):
        # draw directly onto the display at pos (no full size surface to clear and blit).
        self.surface = self.getDrawSurface(pos)
        use_offscreen = self.surface is None
        if use_offscreen:
            if self.offscreen_surface is None or self.offscreen_surface.get_size() != (self.width, self.height):
                self.offscreen_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.surface = self.offscreen_surface
            self.surface.fill((0, 0, 0, 0))
        
        # target bearings are TRUE. convert magnetic heading to true, else fall back to GPS (true) track.
        if self.imuData.mag_head is not None:
            useHeading = (self.imuData.mag_head + self.gpsData.get_mag_decl()) % 360
        elif self.gpsData is not None:
            useHeading = self.gpsData.GndTrack
        else:
            return

        # Traffic rendering (coordinates are local to self.surface; it is blitted at pos below)
        if useHeading is not None and self.showTrafficMiles > 0:
            for t in self.targetData.targets:
                if t.dist is not None and t.brng is not None and t.dist < self.showTrafficMiles:
                    result = ((useHeading - t.brng + 180) % 360) - 180
                    if -self.fov_x_each_side < result < self.fov_x_each_side:
                        center_deg = result + self.fov_x_each_side
                        x_offset = self.width - (center_deg / self.x_degree_per_pixel)

                        # draw distance and altitude
                        txtTargetDist = self.font_target.render(f"{t.dist:.2f}mi {t.alt}ft", True, (0,0,0), self.colorDetails)
                        text_widthD, text_heightD = txtTargetDist.get_size()
                        self.surface.blit(txtTargetDist, (x_offset - int(text_widthD/2), self.height - text_heightD))

                        # draw callsign
                        textTargetCall = self.font_target.render(str(t.callsign), False, (0,0,0),  self.colorTarget )
                        text_widthC, text_heightC = textTargetCall.get_size()
                        self.surface.blit(textTargetCall, (x_offset - int(text_widthC/2), self.height - text_heightC - text_heightD))

        if use_offscreen:
            smartdisplay.pygamescreen.blit(self.surface, pos, special_flags=pygame.BLEND_ALPHA_SDL2)



    def clear(self):
        #self.ahrs_bg.fill((0, 0, 0))  # clear screen
        print("clear")

    # handle key events
    def processEvent(self, event):
        print("processEvent")

    # return a dict of objects that are used to configure the module.
    def get_module_options(self):
        # each item in the dict represents a configuration option.  These are variable in this class that are exposed to the user to edit.
        return {
            "showTrafficMiles": {
                "type": "int",
                "default": self.showTrafficMiles,
                "min": 1,
                "max": 50,
                "label": "Traffic Range",
                "description": "Range in miles to show traffic.",
            },
            "target_font_size": {
                "type": "int",
                "default": self.target_font_size,
                "min": 10,
                "max": 50,
                "label": "Target Font Size",
                "description": "Font size of the target information.",
                "post_change_function": "changeHappened"
            },
            "fov_x": {
                "type": "float",
                "default": self.fov_x,
                "min": 10,
                "max": 30,
                "label": "Field of View Horizontal",
                "description": "Horizontal field of view in degrees.",
                "post_change_function": "changeHappened"
            },
            "colorTarget": {
                "type": "color",
                "default": self.colorTarget,
                "label": "Target TextColor",
                "description": "Color of the target information.",
                "post_change_function": "changeHappened"
            },
            "colorDetails": {
                "type": "color",
                "default": self.colorDetails,
                "label": "Details Text Color",
                "description": "Color of the details information.",
                "post_change_function": "changeHappened"
            }
        }

    def changeHappened(self):
        self.initMod(self.pygamescreen, self.width, self.height)

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
