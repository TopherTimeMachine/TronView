#!/usr/bin/env python

#################################################
# Module: Gun Cross
# Topher 2023.
# Created by Cecil Jones 

from lib.modules._module import Module
from lib import hud_graphics
from lib import hud_utils
from lib import smartdisplay
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_imu import IMUData
from lib.common.dataship.dataship_air import AirData
from lib.common import shared
import pygame
import math
import time

class gcross(Module):
    # called only when object is first created.
    def __init__(self):
        Module.__init__(self)
        self.name = "HUD gcross"  # set name
        self.GunSightMode = 4 # Visual mode this gun sight is in.
        self.TargetWingSpan = 0 # value to show user of target wing span.

        self.imuData = IMUData()
        self.airData = AirData()

    # called once for setup
    def initMod(self, pygamescreen, width=None, height=None):
        if width is None:
            width = 640 # default width
        if height is None:
            height = 480 # default height
        Module.initMod(
            self, pygamescreen, width, height
        )  # call parent init screen.
        print(("Init Mod: %s %dx%d"%(self.name,self.width,self.height)))

        # fonts
        self.font = pygame.font.SysFont(
            None, int(self.height / 20)
        )
        self.offscreen_surface = None  # only used if we can't draw directly to the display

        self.GColor = ( 0,255, 0)  # Gun Cross Color = Yellow
        self.y_offset = hud_utils.readConfigInt("HUD", "Horizon_Offset", 0)  #  Horizon/Waterline Pixel Offset
        # use aircraft.flightPathMarker_x this value comes from the horizon code.
        self.y_center = height / 2
        self.x_center = width / 2
        self.x_offset = 0

        self.GColor_color = ( 0,255, 0)  # Gun Cross Color = Yellow

        self.TargetWingSpan = 0

        self.imuData = IMUData()
        self.airData = AirData()
        if len(shared.Dataship.imuData) > 0:
            self.imuData = shared.Dataship.imuData[0]
        if len(shared.Dataship.airData) > 0:
            self.airData = shared.Dataship.airData[0]

    # called every redraw for the mod
    def draw(self, dataship, smartdisplay, pos):
        # draw directly onto the display at pos (no full size surface to clear and blit).
        self.surface = self.getDrawSurface(pos)
        use_offscreen = self.surface is None
        if use_offscreen:
            if self.offscreen_surface is None or self.offscreen_surface.get_size() != (self.width, self.height):
                self.offscreen_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.surface = self.offscreen_surface
            self.surface.fill((0, 0, 0, 0))

        
        # Set circle radius and line width
        circle_radius = 150
        arc_radius = 148
        circle_radius_ctrdot = 5
        line_width = 2
        arc_width = 10

        if self.GunSightMode == 0:
            pygame.draw.line(self.surface, self.GColor, [self.width / 2 - 10 + self.x_offset, self.height / 2 + self.y_offset + 20], [self.width / 2 + self.x_offset, self.height / 2 + self.y_offset], 3)
            pygame.draw.line(self.surface, self.GColor, [self.width / 2 - 10 + self.x_offset, self.height / 2 + self.y_offset + 20], [self.width / 2 - 20 + self.x_offset, self.height / 2 + self.y_offset], 3)
            pygame.draw.line(self.surface, self.GColor, [self.width / 2 - 35 + self.x_offset, self.height / 2 + self.y_offset], [self.width / 2 - 20 + self.x_offset, self.height / 2 + self.y_offset], 3)
            pygame.draw.line(self.surface, self.GColor, [self.width / 2 + 10 + self.x_offset, self.height / 2 + self.y_offset + 20], [self.width / 2 + self.x_offset, self.height / 2 + self.y_offset], 3)
            pygame.draw.line(self.surface, self.GColor, [self.width / 2 + 10 + self.x_offset, self.height / 2 + self.y_offset + 20], [self.width / 2 + 20 + self.x_offset, self.height / 2 + self.y_offset], 3)
            pygame.draw.line(self.surface, self.GColor, [self.width / 2 + 35 + self.x_offset, self.height / 2 + self.y_offset], [self.width / 2 + 20 + self.x_offset, self.height / 2 + self.y_offset], 3)

        elif self.GunSightMode == 1:
            pygame.draw.line(self.surface, self.GColor_color, (self.width / 2 - 15, self.height / 2 - 120), (self.width / 2 + 15, self.height / 2 - 120), 4)
            pygame.draw.line(self.surface, self.GColor_color, (self.width / 2, self.height / 2 - 135), (self.width / 2, self.height / 2 - 105), 4)
            pygame.draw.circle(self.surface, self.GColor_color, (int(self.width / 2), int(self.height / 2 - 60)), 8, 0)
            pygame.draw.circle(self.surface, self.GColor_color, (int(self.width / 2), int(self.height / 2 + 60)), 8, 0)
            pygame.draw.lines(self.surface, self.GColor_color, False, [[self.width / 2 - 321, self.height / 2 - 120], [self.width / 2 - 160, self.height / 2 - 60], [self.width / 2 - 107, self.height / 2], [self.width / 2 - 80, self.height / 2 + 60], [self.width / 2 - 53, self.height / 2 + 120], [self.width / 2 - 40, self.height / 2 + 180]], 4)
            pygame.draw.lines(self.surface, self.GColor_color, False, [[self.width / 2 + 321, self.height / 2 - 120], [self.width / 2 + 160, self.height / 2 - 60], [self.width / 2 + 107, self.height / 2], [self.width / 2 + 80, self.height / 2 + 60], [self.width / 2 + 53, self.height / 2 + 120], [self.width / 2 + 40, self.height / 2 + 180]], 4)

        elif self.GunSightMode == 2:
            pygame.draw.line(self.surface, self.GColor_color, (self.width / 2 - 15, self.height / 2 - 120), (self.width / 2 + 15, self.height / 2 - 120), 4)
            pygame.draw.line(self.surface, self.GColor_color, (self.width / 2, self.height / 2 - 135), (self.width / 2, self.height / 2 - 105), 4)
            pygame.draw.circle(self.surface, self.GColor_color, (int(self.width / 2), int(self.height / 2 - 60)), 8, 0)
            pygame.draw.circle(self.surface, self.GColor_color, (int(self.width / 2), int(self.height / 2 + 60)), 8, 0)
            pygame.draw.lines(self.surface, self.GColor_color, False, [[self.width / 2 - 385, self.height / 2 - 120], [self.width / 2 - 193, self.height / 2 - 60], [self.width / 2 - 128, self.height / 2], [self.width / 2 - 96, self.height / 2 + 60], [self.width / 2 - 64, self.height / 2 + 120], [self.width / 2 - 48, self.height / 2 + 180]], 4)
            pygame.draw.lines(self.surface, self.GColor_color, False, [[self.width / 2 + 385, self.height / 2 - 120], [self.width / 2 + 193, self.height / 2 - 60], [self.width / 2 + 128, self.height / 2], [self.width / 2 + 96, self.height / 2 + 60], [self.width / 2 + 64, self.height / 2 + 120], [self.width / 2 + 48, self.height / 2 + 180]], 4)

        elif self.GunSightMode == 3:
            pygame.draw.line(self.surface, self.GColor_color, (self.width / 2 - 15, self.height / 2 - 120), (self.width / 2 + 15, self.height / 2 - 120), 4)
            pygame.draw.line(self.surface, self.GColor_color, (self.width / 2, self.height / 2 - 135), (self.width / 2, self.height / 2 - 105), 4)
            pygame.draw.circle(self.surface, self.GColor_color, (int(self.width / 2), int(self.height / 2 - 60)), 8, 0)
            pygame.draw.circle(self.surface, self.GColor_color, (int(self.width / 2), int(self.height / 2 + 60)), 8, 0)
            pygame.draw.lines(self.surface, self.GColor_color, False, [[self.width / 2 - 449, self.height / 2 - 120], [self.width / 2 - 225, self.height / 2 - 60], [self.width / 2 - 150, self.height / 2], [self.width / 2 - 112, self.height / 2 + 60], [self.width / 2 - 75, self.height / 2 + 120], [self.width / 2 - 56, self.height / 2 + 180]], 4)
            pygame.draw.lines(self.surface, self.GColor_color, False, [[self.width / 2 + 449, self.height / 2 - 120], [self.width / 2 + 225, self.height / 2 - 60], [self.width / 2 + 150, self.height / 2], [self.width / 2 + 112, self.height / 2 + 60], [self.width / 2 + 75, self.height / 2 + 120], [self.width / 2 + 56, self.height / 2 + 180]], 4)

        elif self.GunSightMode == 4:
            pygame.draw.line(self.surface, self.GColor_color, (self.width / 2 - 15, self.height / 2 - 120), (self.width / 2 + 15, self.height / 2 - 120), 4)
            pygame.draw.line(self.surface, self.GColor_color, (self.width / 2, self.height / 2 - 135), (self.width / 2, self.height / 2 - 105), 4)

            # Check if VSI data is available
            if not hasattr(self.airData, 'VSI') or self.airData.VSI is None:
                # Display NO VSI DATA message
                text = self.font.render("NO VSI DATA", True, self.GColor_color)
                text_rect = text.get_rect(center=(self.width / 2, self.height / 2))
                self.surface.blit(text, text_rect)
                if use_offscreen:
                    smartdisplay.pygamescreen.blit(self.surface, pos)
                return

            # Adjust all drawing operations to use self.surface instead of smartdisplay.pygamescreen or self.pygamescreen
            pipper_posn = (int(self.width / 2), int((self.height / 2 + self.y_offset) - (self.airData.VSI / 4)))
            color = self.GColor_color   
            traffic_nm = 0.95

            if traffic_nm <= 1.5:
                gun_rng = ((270 * traffic_nm) / 1.5)
                gun_arc = ((270 - gun_rng) + 180)
            if gun_arc > 360: 
                gun_arc = gun_arc - 360
            
            pygame.draw.circle(self.surface, color, pipper_posn, circle_radius, line_width)
            pygame.draw.circle(self.surface, color, pipper_posn, circle_radius_ctrdot)

            start_angle = math.radians(gun_arc)
            end_angle = math.radians(90)
            pygame.draw.arc(self.surface, color, (pipper_posn[0] - arc_radius, pipper_posn[1] - arc_radius, arc_radius * 2, arc_radius * 2), start_angle, end_angle, 5)

            green_arc_radius = arc_radius - 5
            green_arc_width = 15
            start_angle = math.radians(gun_arc)
            end_angle = math.radians(gun_arc + 5)
            pygame.draw.arc(self.surface, color, (pipper_posn[0] - green_arc_radius, pipper_posn[1] - green_arc_radius, green_arc_radius * 2, green_arc_radius * 2), start_angle, end_angle, green_arc_width)

        if use_offscreen:
            smartdisplay.pygamescreen.blit(self.surface, pos)

    # cycle through the modes.
    def cycleGunSight(self):
        self.GunSightMode = self.GunSightMode + 1
        if (self.GunSightMode > 4):
            self.GunSightMode = 0
        # based on mode show a different target wing span.
        if (self.GunSightMode == 1):
            self.TargetWingSpan = 25
        elif (self.GunSightMode == 2):
            self.TargetWingSpan = 30
        elif (self.GunSightMode == 3):
            self.TargetWingSpan = 35


    # called before screen draw.  To clear the screen to your favorite color.
    def clear(self):
        #self.ahrs_bg.fill((0, 0, 0))  # clear screen
        print("clear")

    # handle key events
    def processEvent(self, event):
        print("processEvent")

    def get_module_options(self):
        # each item in the dict represents a configuration option.  These are variable in this class that are exposed to the user to edit.
        return {
            "GunSightMode": {
                "type": "int",
                "min": 0,
                "max": 4,
                "default": 0,
                "label": "Gun Sight Mode",
                "description": ""
            },
            "GColor_color": {
                "type": "color",
                "default": (0, 255, 0),
                "label": "Gun Sight Color",
                "description": ""
            },
        }

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python

