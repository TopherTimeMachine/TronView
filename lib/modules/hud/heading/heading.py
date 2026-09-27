#!/usr/bin/env python

#################################################
# Module: Heading
# Topher 2024 re-write.
# 2/9/2025 - refactor using new dataship classes. 

from lib.modules._module import Module
from lib import hud_graphics
from lib import hud_utils
from lib import smartdisplay
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_imu import IMUData
from lib.common.dataship.dataship_gps import GPSData
import pygame
import math
from lib.common import shared



class heading(Module):
    # called only when object is first created.
    def __init__(self):
        Module.__init__(self)
        self.name = "Heading"  # set name
        self.x_offset = 0
        self.font1_size = 20
        self.font2_size = 30
        self.label_color = (255, 255, 0)
        self.pixels_per_degree = 12  # Default value, can be adjusted
        self.show_track = True
        self.tick_color = (0, 255, 0)
        self.smoothing_factor = 0.15  # Lower = smoother but slower
        self.current_display_hdg = None  # For smooth transitions
        self.target_hdg = None

        self.imuData = IMUData()
        self.gpsData = GPSData()
        if len(shared.Dataship.imuData) > 0:
            self.imuData = shared.Dataship.imuData[0]
        if len(shared.Dataship.gpsData) > 0:
            self.gpsData = shared.Dataship.gpsData[0]

    # called once for setup
    def initMod(self, pygamescreen, width=None, height=None):
        if width is None:
            width = 500  # default width
        if height is None:
            height = 200  # default height
        Module.initMod(self, pygamescreen, width, height)
        print(f"Heading module initialized with screen: {pygamescreen}, width: {width}, height: {height}")

        self.imuData = IMUData()
        self.gpsData = GPSData()
        if len(shared.Dataship.imuData) > 0:
            self.imuData = shared.Dataship.imuData[0]
        if len(shared.Dataship.gpsData) > 0:
            self.gpsData = shared.Dataship.gpsData[0]

    # setup must have defaults for all parameters
    def setup(self):
        print(f"Setting up heading module with dimensions: {self.width}x{self.height}")
        self.myfont = pygame.font.SysFont("monospace", self.font1_size, bold=True)  
        self.myfont1 = pygame.font.SysFont("monospace", self.font2_size, bold=True) 

        # Setup mask
        self.mask = pygame.Surface((66, 30))
        self.mask.fill((0, 0, 0))

        self.hdg = pygame.Surface((360, 80))
        self.hdg_rect = self.hdg.get_rect()
        self.hdg.fill((0, 0, 0))
        self.hdg1 = pygame.Surface((640, 80))
        self.hdg1.fill((0, 0, 0))
        self.trk = pygame.Surface((640, 80), pygame.SRCALPHA)

        ## Setup Labels
        self.N = self.myfont.render("360", False, self.label_color)
        self.N_rect = self.N.get_rect()
        self.R1 = self.myfont.render("010", False, self.label_color)
        self.R1_rect = self.R1.get_rect()
        self.R2 = self.myfont.render("020", False, self.label_color)
        self.R2_rect = self.R2.get_rect()
        self.R3 = self.myfont.render("030", False, self.label_color)
        self.R3_rect = self.R3.get_rect()
        self.R4 = self.myfont.render("040", False, self.label_color)
        self.R4_rect = self.R4.get_rect()
        self.R5 = self.myfont.render("050", False, self.label_color)
        self.R5_rect = self.R5.get_rect()
        self.R6 = self.myfont.render("060", False, self.label_color)
        self.R6_rect = self.R6.get_rect()
        self.R7 = self.myfont.render("070", False, self.label_color)
        self.R7_rect = self.R7.get_rect()
        self.R8 = self.myfont.render("080", False, self.label_color)
        self.R8_rect = self.R8.get_rect()
        self.E = self.myfont.render("090", False, self.label_color)
        self.E_rect = self.E.get_rect()
        self.R10 = self.myfont.render("100", False, self.label_color)
        self.R10_rect = self.R10.get_rect()
        self.R11 = self.myfont.render("110", False, self.label_color)
        self.R11_rect = self.R11.get_rect()
        self.R12 = self.myfont.render("120", False, self.label_color)
        self.R12_rect = self.R12.get_rect()
        self.R13 = self.myfont.render("130", False, self.label_color)
        self.R13_rect = self.R13.get_rect()
        self.R14 = self.myfont.render("140", False, self.label_color)
        self.R14_rect = self.R13.get_rect()
        self.R15 = self.myfont.render("150", False, self.label_color)
        self.R15_rect = self.R15.get_rect()
        self.R16 = self.myfont.render("160", False, self.label_color)
        self.R16_rect = self.R16.get_rect()
        self.R17 = self.myfont.render("170", False, self.label_color)
        self.R17_rect = self.R17.get_rect()
        self.S = self.myfont.render("180", False, self.label_color)
        self.S_rect = self.S.get_rect()
        self.R19 = self.myfont.render("190", False, self.label_color)
        self.R19_rect = self.R19.get_rect()
        self.R20 = self.myfont.render("200", False, self.label_color)
        self.R20_rect = self.R20.get_rect()
        self.R21 = self.myfont.render("210", False, self.label_color)
        self.R21_rect = self.R21.get_rect()
        self.R22 = self.myfont.render("220", False, self.label_color)
        self.R22_rect = self.R22.get_rect()
        self.R23 = self.myfont.render("230", False, self.label_color)
        self.R23_rect = self.R23.get_rect()
        self.R24 = self.myfont.render("240", False, self.label_color)
        self.R24_rect = self.R24.get_rect()
        self.R25 = self.myfont.render("250", False, self.label_color)
        self.R25_rect = self.R25.get_rect()
        self.R26 = self.myfont.render("260", False, self.label_color)
        self.R26_rect = self.R26.get_rect()
        self.W = self.myfont.render("270", False, self.label_color)
        self.W_rect = self.W.get_rect()
        self.R28 = self.myfont.render("280", False, self.label_color)
        self.R28_rect = self.R28.get_rect()
        self.R29 = self.myfont.render("290", False, self.label_color)
        self.R29_rect = self.R29.get_rect()
        self.R30 = self.myfont.render("300", False, self.label_color)
        self.R30_rect = self.R30.get_rect()
        self.R31 = self.myfont.render("310", False, self.label_color)
        self.R31_rect = self.R31.get_rect()
        self.R32 = self.myfont.render("320", False, self.label_color)
        self.R32_rect = self.R32.get_rect()
        self.R33 = self.myfont.render("330", False, self.label_color)
        self.R33_rect = self.R33.get_rect()
        self.R34 = self.myfont.render("340", False, self.label_color)
        self.R34_rect = self.R34.get_rect()
        self.R35 = self.myfont.render("350", False, self.label_color)
        self.R35_rect = self.R35.get_rect()

        self.old_hdg_hdg = None
        self.old_gnd_trk = None

    def roint(self,num):
        return int(round(num))

    def smooth_value(self, current, target, smoothing):
        if current is None:
            return target
        # Calculate the shortest angular distance
        diff = ((target - current + 180) % 360) - 180
        # Apply smoothing
        return current + diff * smoothing

    # called every redraw for the mod
    def draw(self, dataship:Dataship, smartdisplay, pos=(None, None)):
        #print(f"mag_head: {aircraft.mag_head}, gndtrack: {aircraft.gndtrack}")
        x = pos[0] if pos[0] is not None else 0
        y = pos[1] if pos[1] is not None else 0

        # Get heading value, preferring magnetic heading but falling back to ground track
        hdg_hdg = None
        gnd_trk = None

        if self.imuData.mag_head is not None:
            hdg_hdg = self.imuData.mag_head
            # GPS track is TRUE; convert it to magnetic so it can be shown on the magnetic heading tape.
            if self.gpsData.GndTrack is not None:
                gnd_trk = (self.gpsData.GndTrack - self.gpsData.get_mag_decl()) % 360
            else:
                gnd_trk = self.imuData.mag_head
        elif self.gpsData.GndTrack is not None:
            hdg_hdg = self.gpsData.GndTrack
            gnd_trk = self.gpsData.GndTrack
        else:
            # Draw X if no valid heading data
            pygame.draw.line(self.pygamescreen, (255, 0, 0), [x + self.width // 2 - 10, y + self.height // 2], [x + self.width // 2 + 10, y + self.height // 2], 3)
            pygame.draw.line(self.pygamescreen, (255, 0, 0), [x + self.width // 2, y + self.height // 2 - 10], [x + self.width // 2, y + self.height // 2 + 10], 3)
            return

        # Initialize current_display_hdg if None
        if self.current_display_hdg is None:
            self.current_display_hdg = hdg_hdg

        # Smooth the heading transition
        self.current_display_hdg = self.smooth_value(
            self.current_display_hdg, 
            hdg_hdg, 
            self.smoothing_factor
        )

        # Only redraw if the heading or track has changed significantly
        if (abs(self.current_display_hdg - (self.old_hdg_hdg or 0)) > 0.1 or 
            self.old_gnd_trk != gnd_trk):
            
            # reuse the tape surface (only reallocate if the module was resized). the track marker
            # is drawn onto the same surface so only one blit is needed per frame.
            if self.hdg.get_size() != (self.width, self.height) or not (self.hdg.get_flags() & pygame.SRCALPHA):
                self.hdg = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            else:
                self.hdg.fill((0, 0, 0, 0))
            self.trk = self.hdg

            center_x = self.width // 2

            # Draw ticks
            for tick in range(0, 72):  # Changed to cover all 360 degrees (72 * 5 = 360)
                angle = tick * 5 % 360
                x0 = self.roint(center_x + ((angle - self.current_display_hdg + 180) % 360 - 180) * self.pixels_per_degree)
                
                if tick % 2 == 0:  # Major ticks (every 10 degrees)
                    pygame.draw.line(self.hdg, self.tick_color , [x0, 30], [x0, 60], 3)
                else:  # Minor ticks (every 5 degrees)
                    pygame.draw.line(self.hdg, self.tick_color , [x0, 45], [x0, 60], 3)

            # Draw labels
            label_positions = {
                0: self.N, 10: self.R1, 20: self.R2, 30: self.R3, 40: self.R4,
                50: self.R5, 60: self.R6, 70: self.R7, 80: self.R8, 90: self.E,
                100: self.R10, 110: self.R11, 120: self.R12, 130: self.R13, 140: self.R14,
                150: self.R15, 160: self.R16, 170: self.R17, 180: self.S, 190: self.R19,
                200: self.R20, 210: self.R21, 220: self.R22, 230: self.R23, 240: self.R24,
                250: self.R25, 260: self.R26, 270: self.W, 280: self.R28, 290: self.R29,
                300: self.R30, 310: self.R31, 320: self.R32, 330: self.R33, 340: self.R34,
                350: self.R35
            }

            for angle, label in label_positions.items():
                x2 = self.roint(center_x + ((angle - self.current_display_hdg + 180) % 360 - 180) * self.pixels_per_degree)
                self.hdg.blit(label, (x2 - label.get_rect().center[0], 18))

            # Draw heading indicator (always at center)
            pygame.draw.line(self.hdg, self.tick_color , [center_x - 10, 80], [center_x, 60], 3)
            pygame.draw.line(self.hdg, self.tick_color , [center_x, 60], [center_x + 10, 80], 3)

            # Calculate track indicator offset
            track_diff = (gnd_trk - self.current_display_hdg + 180) % 360 - 180
            track_offset = self.roint(track_diff * self.pixels_per_degree)

            # Draw track indicator marker
            pygame.draw.line(self.trk, (255, 0, 255), [center_x + track_offset, 60], [center_x + track_offset, 80], 3)
            pygame.draw.line(self.trk, (255, 0, 255), [center_x + track_offset - 10, 60], [center_x + track_offset + 10, 60], 3)

            # draw the hdg_hdg value under the heading indicator and center it.  pad it to always show 3 digits.
            if self.show_track:
                hdg_text = f"{self.roint(self.current_display_hdg):03d}"
                # Add "GND TRK" label if we're using ground track instead of magnetic heading
                if self.imuData.mag_head is None and self.gpsData.GndTrack is not None:
                    hdg_text += " GND TRK"
                hdg_hdg_text = self.myfont.render(hdg_text, False, self.label_color)
                hdg_hdg_rect = hdg_hdg_text.get_rect()
                hdg_hdg_rect.center = (center_x, 100)
                self.hdg.blit(hdg_hdg_text, hdg_hdg_rect)

            self.old_hdg_hdg = self.current_display_hdg
            self.old_gnd_trk = gnd_trk

        # Draw the heading and track surfaces at the specified position
        self.pygamescreen.blit(self.hdg, (x, y))

    # called before screen draw.  To clear the screen to your favorite color.
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
            "label_color": {
                "type": "color",
                "default": self.label_color,
                "label": "Label Color",
                "description": "Color of the labels.",
            },
            "font1_size": {
                "type": "int",
                "default": self.font1_size,
                "label": "Font Size",
                "description": "Size of the font.",
                "min": 10,
                "max": 50,
                "post_change_function": "setup",
            },
            "font2_size": {
                "type": "int",
                "default": self.font2_size,
                "label": "Font Size 2",
                "description": "Size of the font 2.",
                "min": 10,
                "max": 50,
                "post_change_function": "setup",
            },
            "pixels_per_degree": {
                "type": "int",
                "default": self.pixels_per_degree,
                "label": "Pixels per Degree",
                "description": "Number of pixels between each degree marker.",
                "min": 7,
                "max": 30,
                "post_change_function": "setup",
            },
            "show_track": {
                "type": "bool",
                "default": self.show_track,
                "label": "Show Track",
                "description": "Show the track indicator.",
            },
            "tick_color": {
                "type": "color",
                "default": self.tick_color,
                "label": "Tick Color",
                "description": "Color of the tick marks.",
            },
            "smoothing_factor": {
                "type": "float",
                "default": self.smoothing_factor,
                "label": "Smoothing Factor",
                "description": "Heading smoothing factor (0.05-1.0). Lower values = smoother but slower transitions.",
                "min": 0.05,
                "max": 1.0,
            },
        }

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python








