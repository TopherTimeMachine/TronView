#!/usr/bin/env python

#################################################
# Module: Hud Horizon
# Topher 2021.
# TRON Aug 2024, updated FPM turn rate accuracy
# Adapted from F18 HUD Screen code by Brian Chesteen.

from lib.modules._module import Module
from lib import hud_graphics
from lib import hud_utils
from lib import smartdisplay
from lib.common.dataship import dataship
import pygame
import math


class horizon(Module):
    # called only when object is first created.
    def __init__(self):
        Module.__init__(self)
        self.name = "HUD Horizon"  # set name
        self.hide_from_add_menu = True

    # called once for setup
    def initMod(self, pygamescreen, width=None, height=None):
        if width is None:
            width = pygamescreen.get_width() # default width
        if height is None:
            height = 640 # default height
        Module.initMod(
            self, pygamescreen, width, height
        )  # call parent init screen.
        print(("Init Mod: %s %dx%d"%(self.name,self.width,self.height)))
        target_font_size = hud_utils.readConfigInt("HUD", "target_font_size", 40)

        # fonts
        self.font = pygame.font.SysFont(None, 30)
        self.font_target = pygame.font.SysFont(None, target_font_size)

        self.surface = pygame.Surface((self.width * 2, self.height * 2))
        self.ahrs_bg_width = self.surface.get_width()
        self.ahrs_bg_height = self.surface.get_height()
        self.ahrs_bg_center = (self.ahrs_bg_width / 2 + 160, self.ahrs_bg_height / 2)
        self.MainColor = (0, 255, 0)  # main color of hud graphics
        self.line_thickness = hud_utils.readConfigInt("HUD", "line_thickness", 2)
        self.ahrs_line_deg = hud_utils.readConfigInt("HUD", "vertical_degrees", 5)
        self.pxy_div = hud_utils.readConfigInt("HUD", "vertical_pixels_per_degree", 30)  # Y axis number of pixels per degree divisor
        self.y_offset = hud_utils.readConfigInt("HUD", "Horizon_Offset", 0)  #  Horizon/Waterline Pixel Offset from HUD Center Neg Numb moves Up, Default=0

        self.line_mode = hud_utils.readConfigInt("HUD", "line_mode", 1)
        self.caged_mode = 1 # default on
        self.center_circle_mode = hud_utils.readConfigInt("HUD", "center_circle", 4)

        self.fov_x = hud_utils.readConfigFloat("HUD", "fov_x", 13.942)
        self.fov_x_each_side = self.fov_x / 2
        self.x_degree_per_pixel = self.fov_x / self.width
        print("HUD x degree_per_pixel: %f"%(self.x_degree_per_pixel))

        # traffic range
        self.showTrafficMiles = hud_utils.readConfigInt("HUD", "show_traffic_within_miles", 5)

        # sampling for flight path.
        self.readings = []  # Setup moving averages to smooth a bit
        self.max_samples = 30 # FPM smoothing
        self.readings1 = []  # Setup moving averages to smooth a bit
        self.max_samples1 = 30 # Caged FPM smoothing

        self.x_offset = 0

    #############################################
    ## Function: generateHudReferenceLineArray
    ## create array of horz lines based on pitch, roll, etc.
    def generateHudReferenceLineArray(
        self,screen_width, screen_height, ahrs_center, pxy_div, pitch=0, roll=0, deg_ref=0, line_mode=1,
    ):

        if line_mode == 1:
            if deg_ref == 0:
                length = screen_width * 0.9
            elif (deg_ref % 10) == 0:
                length = screen_width * 0.49
            elif (deg_ref % 5) == 0:
                length = screen_width * 0.25
            else:
                length = screen_width * 0.10
        else:
            if deg_ref == 0:
                length = screen_width * 0.5
            elif (deg_ref % 10) == 0:
                length = screen_width * 0.25
            elif (deg_ref % 5) == 0:
                length = screen_width * 0.11
            else:
                length = screen_width * 0.5

        ahrs_center_x, ahrs_center_y = ahrs_center
        px_per_deg_y = screen_height / pxy_div
        pitch_offset = px_per_deg_y * (-pitch + deg_ref)

        center_x = ahrs_center_x - (pitch_offset * math.cos(math.radians(90 - roll)))
        center_y = ahrs_center_y - (pitch_offset * math.sin(math.radians(90 - roll)))

        x_len = length * math.cos(math.radians(roll))
        y_len = length * math.sin(math.radians(roll))

        start_x = center_x - (x_len / 2)
        end_x = center_x + (x_len / 2)
        start_y = center_y + (y_len / 2)
        end_y = center_y - (y_len / 2)

        xRot = center_x + math.cos(math.radians(-10)) * (start_x - center_x) - math.sin(math.radians(-10)) * (start_y - center_y)
        yRot = center_y + math.sin(math.radians(-10)) * (start_x - center_x) + math.cos(math.radians(-10)) * (start_y - center_y)
        xRot1 = center_x + math.cos(math.radians(+10)) * (end_x - center_x) - math.sin(math.radians(+10)) * (end_y - center_y)
        yRot1 = center_y + math.sin(math.radians(+10)) * (end_x - center_x) + math.cos(math.radians(+10)) * (end_y - center_y)

        xRot2 = center_x + math.cos(math.radians(-10)) * (end_x - center_x) - math.sin(math.radians(-10)) * (end_y - center_y)
        yRot2 = center_y + math.sin(math.radians(-10)) * (end_x - center_x) + math.cos(math.radians(-10)) * (end_y - center_y)
        xRot3 = center_x + math.cos(math.radians(+10)) * (start_x - center_x) - math.sin(math.radians(+10)) * (start_y - center_y)
        yRot3 = center_y + math.sin(math.radians(+10)) * (start_x - center_x) + math.cos(math.radians(+10)) * (start_y - center_y)

        return [[xRot, yRot],[start_x, start_y],[end_x, end_y],[xRot1, yRot1],[xRot2, yRot2],[xRot3, yRot3]]


    #############################################
    ## Function: draw_dashed_line
    def draw_dashed_line(self,surf, color, start_pos, end_pos, width=1, dash_length=10):
        origin = Point(start_pos)
        target = Point(end_pos)
        displacement = target - origin
        length = len(displacement)
        slope = Point((displacement.x / length, displacement.y/length))

        for index in range(0, length // dash_length, 2):
            start = origin + (slope * index * dash_length)
            end = origin + (slope * (index + 1) * dash_length)
            pygame.draw.line(surf, color, start.get(), end.get(), width)

    def draw_circle(self,surface,color,center,radius,width):
        pygame.draw.circle(
            surface,
            color,
            (int(center[0]),int(center[1])),
            radius,
            width,
        )

    #############################################
    ## Function draw horz lines
    def draw_horz_lines(
        self,
        width,
        height,
        ahrs_center,
        ahrs_line_deg,
        aircraft,
        color,
        line_thickness,
        line_mode,
        font,
        pxy_div,
    ):

        for l in range(-60, 61, ahrs_line_deg):
            line_coords = self.generateHudReferenceLineArray(
                width,
                height,
                ahrs_center,
                pxy_div,
                pitch=aircraft.pitch,
                roll=aircraft.roll,
                deg_ref=l,
                line_mode=line_mode,
            )

            if abs(l) > 45:
                if l % 5 == 0 and l % 10 != 0:
                    continue

            # draw below or above the horz
            if l < 0:
                # draw below.
                z=1+1
                self.draw_dashed_line(
                    self.surface,
                    color,
                    line_coords[1],
                    line_coords[2],
                    width=line_thickness,
                    dash_length=5,
                )
                # draw winglets facing up
                pygame.draw.lines(self.surface,
                    color,
                    False,
                    (line_coords[2],
                    line_coords[4]),
                    line_thickness
                )
                pygame.draw.lines(self.surface,
                    color,
                    False,
                    (line_coords[1],
                    line_coords[5]),
                    line_thickness
                )
            else:
                #draw above horiz.
                pygame.draw.lines(
                    self.surface,
                    color,
                    False,
                    (line_coords[0],
                    line_coords[1],
                    line_coords[2],
                    line_coords[3]),
                    line_thickness
                )

            # draw degree text
            if l != 0 and l % 5 == 0:
                text = font.render(str(l), False, color)
                text_width, text_height = text.get_size()
                left = int(line_coords[1][0]) - (text_width + int(width / 100))
                top = int(line_coords[1][1]) - text_height / 2
                self.surface.blit(text, (left, top))


    def draw_center(self,smartdisplay):
        if self.center_circle_mode == 1:
            pygame.draw.circle(
                smartdisplay.pygamescreen,
                self.MainColor,
                (smartdisplay.x_center + self.x_offset, smartdisplay.y_center + self.y_offset),
                3,
                1,
            )
        elif self.center_circle_mode == 2:
            pygame.draw.circle(
                smartdisplay.pygamescreen,
                self.MainColor,
                (smartdisplay.x_center + self.x_offset, smartdisplay.y_center + self.y_offset),
                15,
                1,
            )
        # draw center + Gun Cross
        elif self.center_circle_mode == 3:
            pygame.draw.circle(
                smartdisplay.pygamescreen,
                self.MainColor,
                (smartdisplay.x_center + self.x_offset, smartdisplay.y_center + self.y_offset),
                50,
                1,
            )
        # draw water line center.
        elif self.center_circle_mode == 5:
            pygame.draw.line(
                smartdisplay.pygamescreen,
                self.MainColor,
                [smartdisplay.x_center - 10 + self.x_offset, smartdisplay.y_center + self.y_offset + 20],
                [smartdisplay.x_center + self.x_offset , smartdisplay.y_center + self.y_offset],
                3,
            )
            pygame.draw.line(
                smartdisplay.pygamescreen,
                self.MainColor,
                [smartdisplay.x_center - 10 + self.x_offset, smartdisplay.y_center + self.y_offset + 20],
                [smartdisplay.x_center - 20 + self.x_offset, smartdisplay.y_center + self.y_offset],
                3,
            )
            pygame.draw.line(
                smartdisplay.pygamescreen,
                self.MainColor,
                [smartdisplay.x_center - 35 + self.x_offset, smartdisplay.y_center + self.y_offset],
                [smartdisplay.x_center - 20 + self.x_offset, smartdisplay.y_center + self.y_offset],
                3,
            )
            pygame.draw.line(
                smartdisplay.pygamescreen,
                self.MainColor,
                [smartdisplay.x_center + 10 + self.x_offset, smartdisplay.y_center + self.y_offset + 20],
                [smartdisplay.x_center  + self.x_offset, smartdisplay.y_center + self.y_offset],
                3,
            )
            pygame.draw.line(
                smartdisplay.pygamescreen,
                self.MainColor,
                [smartdisplay.x_center + 10 + self.x_offset, smartdisplay.y_center + self.y_offset + 20],
                [smartdisplay.x_center + 20 + self.x_offset, smartdisplay.y_center + self.y_offset],
                3,
            )
            pygame.draw.line(
                smartdisplay.pygamescreen,
                self.MainColor,
                [smartdisplay.x_center + 35 + self.x_offset, smartdisplay.y_center + self.y_offset],
                [smartdisplay.x_center + 20 + self.x_offset, smartdisplay.y_center + self.y_offset],
                3,
            )

    def draw_flight_path(self,aircraft,smartdisplay):
        def mean(nums):
            return int(sum(nums)) / max(len(nums), 1)

        # flight path indicator  Default Caged Mode
        if self.caged_mode == 1:
            fpv_x = 0.0
        else:  #  changed the  "- (aircraft.turn_rate * 5" to a "+ (aircraft.turn_rate * 5" 
            fpv_x = ((((aircraft.mag_head - aircraft.gndtrack) + 180) % 360) - 180) * 1.5  + (
                aircraft.turn_rate * 5
            )
            self.readings.append(fpv_x)
            fpv_x = mean(self.readings)  # Moving average to smooth a bit
            if len(self.readings) == self.max_samples:
                self.readings.pop(0)
        gfpv_x = ((((aircraft.mag_head - aircraft.gndtrack) + 180) % 360) - 180) * 1.5  + (
            aircraft.turn_rate * 5
        )
        self.readings1.append(gfpv_x)
        gfpv_x = mean(self.readings1)  # Moving average to smooth a bit
        if len(self.readings1) == self.max_samples1:
            self.readings1.pop(0)
        self.draw_circle(
            smartdisplay.pygamescreen,
            (255, 0, 255),  # changed from Magenta 255, 0, 255
            (
                (smartdisplay.width / 2 + self.x_offset) - (int(fpv_x) * 5),
                (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2),
            ),
            15,
            4,
        )
        
        pygame.draw.line(
            smartdisplay.pygamescreen,
            (255, 0, 255),
            [
                (smartdisplay.width / 2 + self.x_offset) - (int(fpv_x) * 5) - 15,
                (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2),
            ], 
            [
                (smartdisplay.width / 2 + self.x_offset) - (int(fpv_x) * 5) - 30,
                (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2),
            ],
            2,
        )
        pygame.draw.line(
            smartdisplay.pygamescreen,
            (255, 0, 255),
            [
                (smartdisplay.width / 2 + self.x_offset) - (int(fpv_x) * 5) + 15,
                (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2),
            ],
            [
                (smartdisplay.width / 2 + self.x_offset) - (int(fpv_x) * 5) + 30,
                (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2),
            ],
            2,
        )
        pygame.draw.line(
            smartdisplay.pygamescreen,
            (255, 0, 255),
            [
                (smartdisplay.width / 2 + self.x_offset) - (int(fpv_x) * 5),
                (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2) - 15,
            ],
            [
                (smartdisplay.width / 2 + self.x_offset) - (int(fpv_x) * 5),
                (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2) - 30,
            ],
            2,
        )
        if self.caged_mode == 1:
            pygame.draw.line(
                smartdisplay.pygamescreen,
                (255, 0, 255),
                [
                    (smartdisplay.width / 2 + self.x_offset) - (int(gfpv_x) * 5) - 15,
                    (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2),
                ],
                [
                    (smartdisplay.width / 2 + self.x_offset) - (int(gfpv_x) * 5) - 30,
                    (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2),
                ],
                2,
            )
            pygame.draw.line(
                smartdisplay.pygamescreen,
                (255, 0, 255),
                [
                    (smartdisplay.width / 2 + self.x_offset) - (int(gfpv_x) * 5) + 15,
                    (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2),
                ],
                [
                    (smartdisplay.width / 2 + self.x_offset) - (int(gfpv_x) * 5) + 30,
                    (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2),
                ],
                2,
            )
            pygame.draw.line(
                smartdisplay.pygamescreen,
                (255, 0, 255),
                [
                    (smartdisplay.width / 2 + self.x_offset) - (int(gfpv_x) * 5),
                    (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2) - 15,
                ],
                [
                    (smartdisplay.width / 2 + self.x_offset) - (int(gfpv_x) * 5),
                    (smartdisplay.y_center + self.y_offset) - (aircraft.vsi / 2) - 30,
                ],
                2,
            )

            aircraft.flightPathMarker_x = fpv_x # save to aircraft object for other modules to use.


    # called every redraw for the mod
    def draw(self, aircraft, smartdisplay, pos=(None, None)):
        if pos[0] != None:
            self.x_offset = pos[0]
        if pos[1] != None:
            self.y_offset = pos[1]

        self.surface.fill((0, 0, 0))  # clear surface

        self.draw_horz_lines(
            smartdisplay.width,
            smartdisplay.height,
            (smartdisplay.x_center + self.x_offset,smartdisplay.y_center + self.y_offset),
            self.ahrs_line_deg,
            aircraft,
            self.MainColor,
            self.line_thickness,
            self.line_mode,
            self.font,
            self.pxy_div,
        )


        # go through targets if there are any.
        if(aircraft.mag_head != None and self.showTrafficMiles > 0):
            for t in aircraft.traffic.targets:
                if t.dist != None and t.dist < self.showTrafficMiles:
                    result = aircraft.mag_head - t.brng
                    if(result   > - self.fov_x_each_side  and  result < self.fov_x_each_side):
                        # bam! target is in view!?!
                        center_deg = result + self.fov_x_each_side
                        x_offset = self.width - (center_deg / self.x_degree_per_pixel) # convert bearing to target to pixel location on screen.

                        # render target distance and alt
                        txtTargetDist = self.font_target.render("%.2fmi %dft"%(t.dist,t.alt), False, (0,0,0),(255,200,130))
                        text_widthD, text_heightD = txtTargetDist.get_size()
                        self.surface.blit(txtTargetDist, (x_offset-int(text_widthD/2), smartdisplay.y_end-text_heightD))
                        # render target callsign.
                        textTargetCall = self.font_target.render(str(t.callsign), False, (0,0,0),(255,200,130))
                        text_widthC, text_heightC = textTargetCall.get_size()
                        self.surface.blit(textTargetCall, (x_offset-int(text_widthC/2), smartdisplay.y_end-text_heightC-text_heightD))


        self.pygamescreen.blit(self.surface, ( -(0), -(0)))

        self.draw_center(smartdisplay)
        self.draw_flight_path(aircraft,smartdisplay)



    # update a setting
    def setting(self,key,var):
        print("setting ",key,var)
        locals()[key] = var
        print("setting ",locals()[key])

    # cycle through the modes.
    def cyclecaged_mode(self):
        self.caged_mode = self.caged_mode + 1
        if (self.caged_mode > 1):
            self.caged_mode = 0

    # called before screen draw.  To clear the screen to your favorite color.
    def clear(self):
        #self.ahrs_bg.fill((0, 0, 0))  # clear screen
        print("clear")

    # handle key events
    def processEvent(self, event):
        print("processEvent")


#############################################
## Class: Point
## used for graphical points.
class Point:
    # constructed using a normal tupple
    def __init__(self, point_t=(0, 0)):
        self.x = float(point_t[0])
        self.y = float(point_t[1])

    # define all useful operators
    def __add__(self, other):
        return Point((self.x + other.x, self.y + other.y))

    def __sub__(self, other):
        return Point((self.x - other.x, self.y - other.y))

    def __mul__(self, scalar):
        return Point((self.x * scalar, self.y * scalar))

    def __div__(self, scalar):
        return Point((self.x / scalar, self.y / scalar))

    def __len__(self):
        return int(math.sqrt(self.x ** 2 + self.y ** 2))

    # get back values in original tuple format
    def get(self):
        return (self.x, self.y)

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
