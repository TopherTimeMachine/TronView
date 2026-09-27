#!/usr/bin/env python

#################################################
# Module: CDI for Localizer Glideslope
# Supported by Topher 2021.
# Created by Cecil Jones 

from lib.modules._module import Module
from lib import hud_graphics
from lib import hud_utils
from lib import smartdisplay
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_nav import NavData
from lib.common import shared
import pygame  
import math


class cdi(Module):
    # called only when object is first created.
    def __init__(self):
        Module.__init__(self)
        self.name = "HUD CDI"  # set name
        self.navData = NavData()

    # called once for setup
    def initMod(self, pygamescreen, width = None, height = None):
        if width is None:
            width = 200 # default width
        if height is None:
            height = 200 # default height
        Module.initMod(
            self, pygamescreen, width, height
        )  # call parent init screen.
        print(("Init Mod: %s %dx%d"%(self.name,self.width,self.height)))

        # fonts
        self.font = pygame.font.SysFont(
            None, int(self.height / 20)
        )
        self.offscreen_surface = None  # only used if we can't draw directly to the display

        self.MainColor = (255, 255, 255)  # CDI Needles color = White 

        self.yCenter = self.height / 2
        self.xCenter = self.width / 2

        self.showLDMax = True
        self.yLDMaxDots = self.height - (self.height/8)
        self.xLDMaxDotsFromCenter = self.width/2

        self.cdi_color = (255, 255, 255)  # start with white.
        # pull water line offset from HUD config area.
        self.y_offset = hud_utils.readConfigInt("HUD", "Horizon_Offset", 0)  #  Horizon/Waterline Pixel Offset from HUD Center Neg Numb moves Up, Default=0

        self.navData = NavData()
        if len(shared.Dataship.navData) > 0:
            self.navData = shared.Dataship.navData[0]


    # called every redraw for the mod
    def draw(self, dataship:Dataship, smartdisplay, pos):
        # Nothing to draw if no nav source is active.
        if self.navData.HSISource != 1 and self.navData.VNAVSource != 1:
            return

        # draw directly onto the display at pos (no full size surface to clear and blit).
        self.surface = self.getDrawSurface(pos)
        use_offscreen = self.surface is None
        if use_offscreen:
            if self.offscreen_surface is None or self.offscreen_surface.get_size() != (self.width, self.height):
                self.offscreen_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.surface = self.offscreen_surface
            self.surface.fill((0, 0, 0, 0))
        
        new_y_center = self.yCenter + self.y_offset
         
        if self.navData.HSISource == 1:
            pygame.draw.line(
                self.surface,
                self.cdi_color,
                (self.xCenter - (self.navData.ILSDev / 60), new_y_center - 67),
                (self.xCenter - (self.navData.ILSDev / 60), new_y_center - 8),
                4,
            )
            pygame.draw.line(
                self.surface,
                self.cdi_color,        
                (self.xCenter - (self.navData.ILSDev / 60), new_y_center + 8),
                (self.xCenter - (self.navData.ILSDev / 60), new_y_center + 67),
                4,
            )
                     
        if self.navData.VNAVSource == 1:
            pygame.draw.line(
                self.surface,
                self.cdi_color,
                (self.xCenter-70, (self.navData.GSDev / 60) + new_y_center),
                (self.xCenter-8, (self.navData.GSDev / 60) + new_y_center),
                4,                              
            ) 
            pygame.draw.line(
                self.surface,
                self.cdi_color,
                (self.xCenter+8, (self.navData.GSDev / 60) + new_y_center),
                (self.xCenter+70, (self.navData.GSDev / 60) + new_y_center),
                4,                              
            )

        if use_offscreen:
            self.pygamescreen.blit(self.surface, pos)

    # cycle through NAV sources
    def cycleNavSource(self,dataship):
        if self.navData.HSISource == 0 and self.navData.VNAVSource == 0:
            self.navData.HSISource = 1
            self.navData.SourceDesc = "Localizer"
        elif self.navData.HSISource == 1 and self.navData.VNAVSource == 0:
            self.navData.VNAVSource = 1
            self.navData.SourceDesc = "ILS"
        else:
            self.navData.HSISource = 0
            self.navData.VNAVSource = 0
            self.navData.SourceDesc = ""


    # called before screen draw.  To clear the screen to your favorite color.
    def clear(self):
        #self.ahrs_bg.fill((0, 0, 0))  # clear screen
        print("clear")

    # handle key events
    def processEvent(self, event):
        print("processEvent")
    
    def get_module_options(self):
        return {
            "cdi_color": {
                "type": "color",
                "default": self.cdi_color,
                "label": "CDI Color",
                "description": "Color of the CDI needles.",
            }
        }


# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
