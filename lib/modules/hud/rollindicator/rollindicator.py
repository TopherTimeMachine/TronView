#!/usr/bin/env python

#################################################
# Module: Roll indicator
# Topher 2021.

from lib.modules._module import Module
from lib import hud_graphics
from lib import hud_utils
from lib import smartdisplay
import pygame
import math
from lib.common import shared
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_imu import IMUData

class rollindicator(Module):
    # called only when object is first created.
    def __init__(self):
        Module.__init__(self)
        self.name = "RollIndicator"  # set name
        self.hsi_size = 360
        self.roll_point_size = 20
        self.x_offset = 0
        self.IMUData = IMUData()

    # called once for setup
    def initMod(self, pygamescreen, width=None, height=None):
        if width is None:
            width = 500 # default width
        if height is None:
            height = 500 # default height
        Module.initMod(
            self, pygamescreen, width, height
        )  # call parent init screen.
        print(("Init Mod: %s %dx%d"%(self.name,self.width,self.height)))

        # fonts
        self.font = pygame.font.SysFont(
            None, int(self.height / 20)
        )

        self.roll_point_image = pygame.image.load("lib/modules/hud/rollindicator/tick_w.bmp").convert()
        self.roll_point_image.set_colorkey((0, 0, 0))
        self.update_roll_point_size()

        self.roll_tick = pygame.Surface((self.hsi_size, self.hsi_size), pygame.SRCALPHA)
        def roint(num):
            return int(round(num))
        # render big tick onto surface.
        for big_tick in range(6, 13):
            cos = math.cos(math.radians(360.0 / 36 * big_tick))
            sin = math.sin(math.radians(360.0 / 36 * big_tick))
            x0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * cos * 6)
            y0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * sin * 6)
            x1 = roint(self.hsi_size / 2 + self.hsi_size / 2.1 * cos)
            y1 = roint(self.hsi_size / 2 + self.hsi_size / 2.1 * sin)
            pygame.draw.line(self.roll_tick, (255, 255, 255), [x0, y0], [x1, y1], 4)
        for big_tick in range(12, 25):
            cos = math.cos(math.radians(360.0 / 72 * big_tick))
            sin = math.sin(math.radians(360.0 / 72 * big_tick))
            x0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * cos * 6)
            y0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * sin * 6)
            x1 = roint(self.hsi_size / 2 + self.hsi_size / 2.3 * cos)
            y1 = roint(self.hsi_size / 2 + self.hsi_size / 2.3 * sin)
            pygame.draw.line(self.roll_tick, (255, 255, 255), [x0, y0], [x1, y1], 2)
        for big_tick in range(1, 4):
            cos = math.cos(math.radians(360.0 / 8 * big_tick))
            sin = math.sin(math.radians(360.0 / 8 * big_tick))
            x0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * cos * 6)
            y0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * sin * 6)
            x1 = roint(self.hsi_size / 2 + self.hsi_size / 2.3 * cos)
            y1 = roint(self.hsi_size / 2 + self.hsi_size / 2.3 * sin)
            pygame.draw.line(self.roll_tick, (255, 255, 255), [x0, y0], [x1, y1], 4)
        for big_tick in range(3, 4):
            cos = math.cos(math.radians(360.0 / 36 * big_tick))
            sin = math.sin(math.radians(360.0 / 36 * big_tick))
            x0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * cos * 6)
            y0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * sin * 6)
            x1 = roint(self.hsi_size / 2 + self.hsi_size / 2.1 * cos)
            y1 = roint(self.hsi_size / 2 + self.hsi_size / 2.1 * sin)
            pygame.draw.line(self.roll_tick, (255, 255, 255), [x0, y0], [x1, y1], 4)
        for big_tick in range(15, 16):
            cos = math.cos(math.radians(360.0 / 36 * big_tick))
            sin = math.sin(math.radians(360.0 / 36 * big_tick))
            x0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * cos * 6)
            y0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * sin * 6)
            x1 = roint(self.hsi_size / 2 + self.hsi_size / 2.1 * cos)
            y1 = roint(self.hsi_size / 2 + self.hsi_size / 2.1 * sin)
            pygame.draw.line(self.roll_tick, (255, 255, 255), [x0, y0], [x1, y1], 4)
        for big_tick in range(1, 2):
            cos = math.cos(math.radians(360.0 / 4 * big_tick))
            sin = math.sin(math.radians(360.0 / 4 * big_tick))
            x0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * cos * 5.5)
            y0 = roint(self.hsi_size / 2 + self.hsi_size / 15 * sin * 5.5)
            x1 = roint(self.hsi_size / 2 + self.hsi_size / 2.1 * cos)
            y1 = roint(self.hsi_size / 2 + self.hsi_size / 2.1 * sin)
            pygame.draw.line(self.roll_tick, (255, 255, 255), [x0, y0], [x1, y1], 4)

        if len(shared.Dataship.imuData) > 0:
            self.IMUData = shared.Dataship.imuData[0]
        else:
            self.IMUData = IMUData()

    # called every redraw for the mod
    def draw(self, dataship: Dataship, smartdisplay, pos=(None, None)):

        # tick surface is drawn with its top left at pos. its center is the roll pivot.
        if pos[0] is not None and pos[1] is not None:
            draw_pos = (pos[0], pos[1])
        else:
            draw_pos = (self.width // 2 - self.hsi_size // 2, self.height // 2 - self.hsi_size // 2)
        x_center = draw_pos[0] + self.hsi_size // 2
        y_center = draw_pos[1] + self.hsi_size // 2

        # Draw roll ticks
        smartdisplay.pygamescreen.blit(self.roll_tick, draw_pos)

        roll = self.IMUData.roll
        if roll is None:
            return

        # Draw roll point. only the small pointer is rotated (not a full size surface),
        # and rotated versions are cached per 0.5 degree.
        key = int(round(roll * 2))
        roll_point_rotated = self.roll_point_cache.get(key)
        if roll_point_rotated is None:
            roll_point_rotated = pygame.transform.rotate(self.roll_point_scaled, key / 2.0)
            if len(self.roll_point_cache) > 720:
                self.roll_point_cache.clear()
            self.roll_point_cache[key] = roll_point_rotated

        # the pointer sits roll_point_radius pixels below the pivot and swings around it.
        roll_rad = math.radians(key / 2.0)
        px = x_center + self.roll_point_radius * math.sin(roll_rad)
        py = y_center + self.roll_point_radius * math.cos(roll_rad)
        roll_point_rect = roll_point_rotated.get_rect(center=(int(round(px)), int(round(py))))
        smartdisplay.pygamescreen.blit(roll_point_rotated, roll_point_rect)


    # called before screen draw.  To clear the screen to your favorite color.
    def clear(self):
        #self.ahrs_bg.fill((0, 0, 0))  # clear screen
        print("clear")

    # handle key events
    def processEvent(self, event):
        print("processEvent")
    
    def get_module_options(self):
        return {
            "roll_point_size": {
                "type": "int",
                "default": self.roll_point_size,
                "min": 10,
                "max": 50,
                "label": "Roll Point Size",
                "description": "Size of the roll point.",
                "post_change_function": "update_roll_point_size"
            }
        }
    
    def update_roll_point_size(self):
        self.roll_point_scaled = pygame.transform.scale(
            self.roll_point_image, (self.roll_point_size, self.roll_point_size)
        )
        self.roll_point_scaled_rect = self.roll_point_scaled.get_rect()
        # pointer center distance below the pivot (top of pointer is 120px below center).
        self.roll_point_radius = 120 + self.roll_point_size / 2
        self.roll_point_cache = {}  # rotated pointers keyed by roll in 0.5 deg steps
    


# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
