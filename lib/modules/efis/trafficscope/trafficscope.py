#!/usr/bin/env python

#################################################
# Module: Traffic Scope
# Topher 2021.
# 

from lib.modules._module import Module
from lib import hud_graphics
from lib import hud_utils
from lib import smartdisplay
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_targets import TargetData, Target
from lib.common.dataship.dataship_gps import GPSData
from lib.common.dataship.dataship_imu import IMUData

import pygame
import math
import time
#from osgeo import osr
from lib.common import shared


class trafficscope(Module):
    # called only when object is first created.
    def __init__(self):
        Module.__init__(self)
        self.name = "Traffic Scope"  # set name
        self.show_callsign = False
        self.show_details = False
        self.scope_scale = 0
        self.scope_scale_miles = 10
        self.target_show_lat_lon = hud_utils.readConfigBool("TrafficScope", "target_show_lat_lon", False)
        self.draw_icon = hud_utils.readConfigBool("TrafficScope", "draw_icon", True)
        self.icon_scale = hud_utils.readConfigInt("TrafficScope", "icon_scale", 10)
        self.details_offset = hud_utils.readConfigInt("TrafficScope", "details_offset", 5)

        self.targetDetails = {} # keep track of details about each target. like the x,y position on the screen. and if they are selected.

        # Add smoothing configuration
        self.enable_smoothing = hud_utils.readConfigBool("TrafficScope", "enable_smoothing", True)
        self.smoothing_factor = 0.15
        
        # Add tracking of previous positions
        self.target_positions = {} # Store previous positions for smoothing

        # store the target data and gps data to use in the draw method.
        self.targetData = TargetData()
        self.gpsData = GPSData()
        self.imuData = IMUData()
        self.selectedTarget = None


    # called once for setup
    def initMod(self, pygamescreen, width=None, height=None):
        if width is None:
            width = 500 # default width
        if height is None:
            height = 500 # default height
        Module.initMod(
            self, pygamescreen, width, height
        )  # call parent init screen.
        if shared.Dataship.debug_mode > 0:
            print(("Init Mod: %s %dx%d"%(self.name,self.width,self.height)))

        self.xCenter = self.width/2
        self.yCenter = self.height/2

        target_font_size = hud_utils.readConfigInt("TrafficScope", "target_font_size", 16)
        self.font = pygame.font.SysFont("monospace", 12, bold=False)
        self.font_target = pygame.font.SysFont("monospace", target_font_size, bold=False)

        self.setScaleInMiles()

        self.targetData = TargetData()
        self.gpsData = GPSData()
        self.imuData = IMUData()

        # set the target data and gps data to the first item in the list.
        if len(shared.Dataship.targetData) > 0:
            self.targetData = shared.Dataship.targetData[0]
        if len(shared.Dataship.gpsData) > 0:
            self.gpsData = shared.Dataship.gpsData[0]
        if len(shared.Dataship.imuData) > 0:
            self.imuData = shared.Dataship.imuData[0]

        # setup buttons
        self.buttonsClear()
        self.buttonAdd("send_yo", "Send Yo", self.sendMsg)
        self.buttonAdd("send_position", "Send position", self.sendMsg)

    def buildBaseSurface(self):
        # static scope graphics (rings, cross lines, scale labels) are drawn once here and cached.
        self.surfaceBase = pygame.Surface((self.width, self.height),pygame.SRCALPHA)
        self.offscreen_surface = None  # only used if we can't draw directly to the display
        self.surface2 = None  # set each frame in draw()
        #self.surface.set_alpha(128)
        #self.surface2.set_alpha(128)
        #self.surface.fill((0,0,0))
        self.darkGrey = (40,40,40)

        # fill background black
        hud_graphics.hud_draw_circle(
            self.surfaceBase, 
            (0,0,0,0), 
            (self.xCenter, self.yCenter), 
            int(self.width/2), 
            0,
        )  

        # draw cross lines
        pygame.draw.line(
            self.surfaceBase,
            self.darkGrey,  # color orange
            (0, self.height/2), 
            (self.width,self.height/2),
            1,
        )

        pygame.draw.line(  # 
            self.surfaceBase,
            self.darkGrey,
            (self.width/2,0), 
            (self.width/2, self.height),
            1,
        )
        # draw outter circle
        hud_graphics.hud_draw_circle(
            self.surfaceBase, 
            self.darkGrey, 
            (self.xCenter, self.yCenter), 
            int(self.width/2), 
            1,
        ) 
        hud_graphics.hud_draw_circle(
            self.surfaceBase, 
            self.darkGrey, 
            (self.xCenter, self.yCenter), 
            int(self.width/4), 
            1,
        )

        # show scale.
        labelScale = self.font.render(str(self.scope_scale_miles)+" mi.", False, (200,255,255), (0,0,0))
        labelScale_rect = labelScale.get_rect()
        self.surfaceBase.blit(labelScale, (self.xCenter-labelScale_rect.width, 5))

        # show scale.
        labelScale = self.font.render("%.1f mi."%(self.scope_scale_miles/2), False, (200,255,255), (0,0,0))
        labelScale_rect = labelScale.get_rect()
        self.surfaceBase.blit(labelScale, (self.xCenter-labelScale_rect.width, int(self.height/4)+5 ))


    def setScaleInMiles(self,miles = None ):
        if miles is not None:
            self.scope_scale_miles = miles
        self.scope_scale = (self.width/2) / self.scope_scale_miles 
        self.buildBaseSurface()

    # called every redraw for the mod
    def draw(self, dataship:Dataship, smartdisplay, pos):
        # draw directly onto the display at pos (no full size surface to clear and blit).
        self.surface2 = self.getDrawSurface(pos)
        use_offscreen = self.surface2 is None
        if use_offscreen:
            if self.offscreen_surface is None or self.offscreen_surface.get_size() != (self.width, self.height):
                self.offscreen_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.surface2 = self.offscreen_surface
            self.surface2.fill((0,0,0,0))
        # draw the cached static scope graphics.
        self.surface2.blit(self.surfaceBase, (0, 0))

        self.selectedTarget = self.targetData.get_selected_target()  # make sure we have the latest selected target.

        # Get aircraft heading or ground track, if both are None then use 0
        # Target bearings and tracks are TRUE, so the IMU (magnetic) heading has declination applied.
        if self.imuData.yaw is not None:
            target_heading = (self.imuData.yaw + self.gpsData.get_mag_decl()) % 360
        elif self.gpsData.GndTrack is not None:
            target_heading = self.gpsData.GndTrack
        else:
            target_heading = 0

        def draw_target(t: Target):
            if t.dist is None or t.dist > self.scope_scale_miles or t.brng is None:
                return

            brngToUse = (t.brng - target_heading) % 360
            radianAngle = math.radians(brngToUse - 90)
            d = t.dist * self.scope_scale
            target_x = self.xCenter + (d * math.cos(radianAngle))
            target_y = self.yCenter + (d * math.sin(radianAngle))

            # Apply position smoothing if enabled
            if self.enable_smoothing:
                current_time = time.time()
                
                if t.callsign not in self.target_positions:
                    # Initialize position tracking for new target
                    self.target_positions[t.callsign] = {
                        'x': target_x,
                        'y': target_y,
                        'displayed_x': target_x,
                        'displayed_y': target_y,
                        'last_update': current_time
                    }
                else:
                    # Get time elapsed since last update
                    dt = current_time - self.target_positions[t.callsign]['last_update']
                    
                    # Update the actual position
                    self.target_positions[t.callsign]['x'] = target_x
                    self.target_positions[t.callsign]['y'] = target_y
                    
                    # Smoothly interpolate to new position
                    self.target_positions[t.callsign]['displayed_x'] += (target_x - self.target_positions[t.callsign]['displayed_x']) * self.smoothing_factor * dt * 60
                    self.target_positions[t.callsign]['displayed_y'] += (target_y - self.target_positions[t.callsign]['displayed_y']) * self.smoothing_factor * dt * 60
                    
                    # Update timestamp
                    self.target_positions[t.callsign]['last_update'] = current_time
                    
                    # Use smoothed positions
                    target_x = self.target_positions[t.callsign]['displayed_x']
                    target_y = self.target_positions[t.callsign]['displayed_y']

            # Draw the target using smoothed positions
            if self.draw_icon:
                direction_target_facing = ((t.track or brngToUse) - target_heading) % 360
                t.targetDirection = round(math.radians(direction_target_facing - 90), 2)
                self.drawAircraftIcon(self.surface2, t, target_x, target_y, self.icon_scale)
            else:
                hud_graphics.hud_draw_circle(self.surface2, (0, 255, 129), (target_x, target_y), 4, 0)

            x_text = target_x + self.details_offset
            y_text = target_y + self.details_offset

            if self.show_callsign:
                label = self.font_target.render(t.callsign, False, (200,255,255), (0,0,0))
                self.surface2.blit(label, (x_text, y_text))
                label_rect = label.get_rect()
            else:
                label_rect = pygame.Rect(0, 0, 0, 0)

            if self.show_details:
                self.draw_target_details(t, target_x, target_y, x_text, y_text, label_rect, target_heading)

            # store the x,y position of the target in the local targetDetails dictionary.
            if t.callsign not in self.targetDetails:
                self.targetDetails[t.callsign] = {"x": target_x, "y": target_y, "selected": False}
                if shared.Dataship.debug_mode > 0:
                    print("Added target to targetDetails: %s" % t.callsign, "x: %d, y: %d" % (target_x, target_y))
            else: # else just update the x,y position.
                self.targetDetails[t.callsign]["x"] = target_x
                self.targetDetails[t.callsign]["y"] = target_y

        # Separate targets into selected and non-selected lists
        # only targets inside the scope range (outer ring) are drawn.
        valid_targets = list(filter(lambda t: t.dist is not None and t.dist <= self.scope_scale_miles and t.brng is not None, self.targetData.targets))
        
        selected_targets = []
        other_targets = []

        for t in valid_targets:
            if t.callsign in self.targetDetails and self.targetDetails[t.callsign]["selected"]:
                selected_targets.append(t)
            else:
                other_targets.append(t)

        # Draw non-selected targets first
        list(map(draw_target, other_targets))
        
        # Draw selected targets last (so they appear on top)
        list(map(draw_target, selected_targets))

        if use_offscreen:
            self.pygamescreen.blit(self.surface2, pos)

        # if there is a selected target then draw some buttons.
        if self.selectedTarget is not None:
            if self.selectedTarget.type == 101:   # meshtastic type target.
                self.buttonsDraw(dataship, smartdisplay, pos)  # draw buttons

    def draw_target_details(self, t: Target, xx, yy, x_text, y_text, label_rect, target_heading):
        if t.speed is not None and t.speed > -1 and t.track is not None:
            t.targetBrngToUse = round((t.track - target_heading) % 360, 2)
            radianTargetTrack = math.radians(t.targetBrngToUse - 90)
            d = min(t.speed / 3, 60)
            
            lineX, lineY = xx + d * math.cos(radianTargetTrack), yy + d * math.sin(radianTargetTrack)
            arrowX, arrowY = xx + (d-2) * math.cos(math.radians(t.targetBrngToUse - 82)), yy + (d-2) * math.sin(math.radians(t.targetBrngToUse - 82))
            arrowX2, arrowY2 = xx + (d-2) * math.cos(math.radians(t.targetBrngToUse - 98)), yy + (d-2) * math.sin(math.radians(t.targetBrngToUse - 98))

            # draw a line from the nose of target in direction it is heading.
            pygame.draw.line(self.surface2, (200,255,255), (xx,yy), (lineX, lineY), 1)
            pygame.draw.line(self.surface2, (200,255,255), (lineX,lineY), (arrowX, arrowY), 1)
            pygame.draw.line(self.surface2, (200,255,255), (lineX,lineY), (arrowX2, arrowY2), 1)

            next_text_y_offset = label_rect.height
            if self.selectedTarget == None or self.selectedTarget and t.address == self.selectedTarget.address:

                labelSpeed = self.font_target.render(f"{t.speed}mph", False, (200,255,255), (0,0,0))
                labelSpeed_rect = labelSpeed.get_rect()
                self.surface2.blit(labelSpeed, (x_text, y_text + label_rect.height))

                if t.altDiff is not None:
                    prefix = "+" if t.altDiff > 0 else ""
                    labelAlt = self.font_target.render(f"{prefix}{t.altDiff:,}ft", False, (200,255,255), (0,0,0))
                    self.surface2.blit(labelAlt, (x_text + labelSpeed_rect.width + 10, y_text + label_rect.height))

                labelDist = self.font_target.render(f"{t.dist:.1f}mi ", False, (200,255,255), (0,0,0))
                self.surface2.blit(labelDist, (x_text + label_rect.width + 10, y_text))
                next_text_y_offset += labelSpeed_rect.height 

                # Add time since last update
                if hasattr(t, 'time'):
                    time_since_update = int(time.time() - t.time)
                    labelUpdate = self.font_target.render(f"{time_since_update}s ago", False, (200,255,255), (0,0,0))
                    self.surface2.blit(labelUpdate, (x_text, y_text + next_text_y_offset))
                    next_text_y_offset += labelUpdate.get_rect().height

                if self.target_show_lat_lon:
                    labelLat = self.font_target.render(f"{t.lat:.6f} {t.lon:.6f}", False, (200,255,255), (0,0,0))
                    self.surface2.blit(labelLat, (x_text, y_text + next_text_y_offset))
                    next_text_y_offset += labelLat.get_rect().height

                if t.payload_last is not None:
                    labelPayload = self.font_target.render("msg: "+t.payload_last.payload, False, (200,255,255), (0,0,0))
                    self.surface2.blit(labelPayload, (x_text, y_text + next_text_y_offset))
                    next_text_y_offset += labelPayload.get_rect().height

                if t.faa_db_record:
                    labelFaa = self.font_target.render(f"{t.faa_db_record.aircraft_desc_mfr} {t.faa_db_record.aircraft_desc_model}", False, (200,255,255), (0,0,0))
                    self.surface2.blit(labelFaa, (x_text, y_text + next_text_y_offset))
                    next_text_y_offset += labelFaa.get_rect().height

                    if t.faa_db_record.commerical_name:
                        labelCommercial = self.font_target.render(f"{t.faa_db_record.commerical_name}", False, (200,255,255), (0,0,0))
                        self.surface2.blit(labelCommercial, (x_text, y_text + next_text_y_offset))
                        next_text_y_offset += labelCommercial.get_rect().height
            
            # if aircraft is selected then give some more details.
            if self.selectedTarget and t.address == self.selectedTarget.address:
                if t.faa_db_record:
                    labelCommercial = self.font_target.render(f"{t.faa_db_record.owner_name}\n{t.faa_db_record.city},{t.faa_db_record.state}", False, (200,255,255), (0,0,0))
                    self.surface2.blit(labelCommercial, (x_text, y_text + next_text_y_offset))
                    next_text_y_offset += labelCommercial.get_rect().height
                

    # draw aircraft icon based on the type of aircraft
    def drawAircraftIcon(self, surface, target, xx, yy, scale):

        direction_target_facing = target.targetDirection
        # types of aircraft
        # 0 = unkown
        # 1 = Light (ICAO) < 15 500 lbs
        # 2 = Small - 15 500 to 75 000 lbs
        # 3 = Large - 75 000 to 300 000 lbs
        # 4 = High Vortex Large (e.g., aircraft 24 such as B757)
        # 5 = Heavy (ICAO) - > 300 000 lbs
        # 7 = Rotorcraft
        # 9 = Glider
        # 10 = lighter then air
        # 11 = sky diver
        # 12 = ultra light
        # 14 = drone Unmanned aerial vehicle
        # 15 = space craft and aliens!
        nose = (xx + scale * math.cos(direction_target_facing), 
            yy + scale * math.sin(direction_target_facing))
        tail = (xx - scale * math.cos(direction_target_facing), 
                yy - scale * math.sin(direction_target_facing))
                
        # if type is 0 through 5 then draw a simple aircraft icon
        if(target.type >= 0 and target.type <= 5):
            # Calculate points for the target aircraft outline

            wing_left = (xx + scale * 0.7 * math.cos(direction_target_facing + math.pi/2), 
                            yy + scale * 0.7 * math.sin(direction_target_facing + math.pi/2))
            wing_right = (xx + scale * 0.7 * math.cos(direction_target_facing - math.pi/2), 
                            yy + scale * 0.7 * math.sin(direction_target_facing - math.pi/2))
            elevator_left = (tail[0] + scale * 0.3 * math.cos(direction_target_facing + math.pi/2), 
                                tail[1] + scale * 0.3 * math.sin(direction_target_facing + math.pi/2))
            elevator_right = (tail[0] + scale * 0.3 * math.cos(direction_target_facing - math.pi/2), 
                                tail[1] + scale * 0.3 * math.sin(direction_target_facing - math.pi/2))

            # Draw the aircraft outline
            pygame.draw.line(surface, (0, 255, 129), nose, tail, 1)
            pygame.draw.line(surface, (0, 255, 129), wing_left, wing_right, 1)
            pygame.draw.line(surface, (0, 255, 129), elevator_left, elevator_right, 1)
        elif(target.type == 7):
            # draw a helicopter. which will look like a X with a line through it. use nose and tail to draw it.
            # calculate the angle of the helicopter blades.
            # calculate the angle of the helicopter blades.
            blade_angle = math.atan2(tail[1] - nose[1], tail[0] - nose[0])
            # calculate the length of the blades.
            blade_length = scale * 0.7
            # calculate the position of the blades.
            blade_pos = (nose[0] + blade_length * math.cos(blade_angle), 
                            nose[1] + blade_length * math.sin(blade_angle))
            # also draw a light circle around the helicopter.
            pygame.draw.circle(surface, (0, 255, 129), tail, scale * 0.2, 1)
            pygame.draw.circle(surface, (0, 255, 129), blade_pos, scale * 0.8, 1)

            # draw the blades.
            pygame.draw.line(surface, (0, 255, 129), nose, blade_pos, 1)
            pygame.draw.line(surface, (0, 255, 129), tail, blade_pos, 1)
            # draw a line through the middle of the helicopter.
            pygame.draw.line(surface, (0, 255, 129), nose, tail, 1)
        elif(target.type == 101):
            # Draw the Meshtastic logo ( /< )
            logo_color = (0, 255, 129)
            line_thickness = 2 # Adjusted thickness

            # Diagonal line (/) - Adjust coordinates for better representation
            start_diag = (int(xx - scale * 0.7), int(yy + scale * 0.6))
            end_diag = (int(xx - scale * 0.1), int(yy - scale * 0.6))
            pygame.draw.line(surface, logo_color, start_diag, end_diag, line_thickness)

            # Angle line (<) - Adjust coordinates for better representation
            point_top = (int(xx + scale * 0.3), int(yy - scale * 0.6))
            point_mid_left = (int(xx - scale * 0.1), int(yy + scale * 0.6)) # Connects near the bottom-right of the diagonal
            point_bottom_right = (int(xx + scale * 0.7), int(yy + scale * 0.6))

            pygame.draw.line(surface, logo_color, point_top, point_mid_left, line_thickness)
            pygame.draw.line(surface, logo_color, point_mid_left, point_bottom_right, line_thickness)
        else:
            # Draw a smiley face as the default
            # Main circle (face)
            pygame.draw.circle(surface, (70,150,255), (xx, yy), scale, 1)
            
            # Eyes
            eye_offset = scale * 0.3
            eye_size = max(1, int(scale * 0.15))
            pygame.draw.circle(surface, (70,150,255), (int(xx - eye_offset), int(yy - eye_offset)), eye_size, 0)
            pygame.draw.circle(surface, (70,150,255), (int(xx + eye_offset), int(yy - eye_offset)), eye_size, 0)
            
            # Smile
            smile_rect = pygame.Rect(xx - scale * 0.5, yy, scale, scale * 0.5)
            pygame.draw.arc(surface, (70,150,255), smile_rect, math.pi * 0.1, math.pi * 0.9, 1)

        # draw a circle around the target. if it is selected. check if the callsign is in the targetDetails dictionary. 
        # is self.targetDetails[t.callsign]["selected"] even exist?
        if target.callsign in self.targetDetails and self.targetDetails[target.callsign]["selected"]:
            pygame.draw.circle(self.surface2, (120,255,120), (xx, yy), self.icon_scale + 2, 2)



    # called before screen draw.  To clear the screen to your favorite color.
    def clear(self):
        #self.ahrs_bg.fill((0, 0, 0))  # clear screen
        #print("clear")
        pass
    
    # return a dict of objects that are used to configure the module.
    def get_module_options(self):

        # each item in the dict represents a configuration option.  These are variable in this class that are exposed to the user to edit.
        return {
            "show_callsign": {
                "type": "bool",
                "default": False,
                "label": "Show Callsign",
                "description": "Show the callsign of the targets on the scope."
            },
            "show_details": {
                "type": "bool",
                "default": False,
                "label": "Show Details",
                "description": "Show the details of the targets on the scope."
            },
            "details_offset": {
                "type": "int",
                "default": self.details_offset,
                "min": 0,
                "max": 20,
                "label": "Details Offset",
                "description": "Set the offset of the details from the target in pixels."
            },
            "target_show_lat_lon": {
                "type": "bool",
                "default": False,
                "label": "Show Lat/Lon",
                "description": "Show the latitude and longitude of the targets on the scope."
            },
            "scope_scale_miles": {
                "type": "int",
                "default": self.scope_scale_miles,
                "min": 1,
                "max": 50,
                "label": "Scope Scale",
                "description": "Set the scale of the scope in miles.",
                "post_change_function": "setScaleInMiles"
            },
            "draw_icon": {
                "type": "bool",
                "default": True,
                "label": "Draw Target Icon",
                "description": "Draw a symbol for targets."
            },
            "icon_scale": {
                "type": "int",
                "default": 10,
                "min": 10,
                "max": 30,
                "label": "Aircraft Icon Scale",
                "description": "Set the scale of the aircraft icon."
            },
            "enable_smoothing": {
                "type": "bool",
                "default": True,
                "label": "Enable Smoothing",
                "description": "Enable smooth transitions for target movements"
            },
            "smoothing_factor": {
                "type": "float",
                "default": 0.15,
                "min": 0.01,
                "max": 1.0,
                "label": "Smoothing Factor",
                "description": "Amount of smoothing (0.01=most smooth, 1.0=no smoothing)"
            }
        }

    # handle mouse clicks
    def processClick(self, dataship:Dataship, mx, my, buttonNum):
        # check if a button was clicked.
        if self.buttonsCheckClick(dataship, mx, my, buttonNum): # call parent.
            return

        if dataship.debug_mode > 0:
            print("TrafficScope processClick: %d x %d" % (mx, my) + " buttonNum: %d" % buttonNum)
        # clear any selected targets from self.targetDetails
        for target in self.targetDetails:
            self.targetDetails[target]["selected"] = False
        self.targetData.selected_target = None

        # # translate mx,my to same coordinate system as self.targetDetails.  which is based of the center of the surface is 0,0.
        # mx = mx - self.xCenter
        # my = my - self.yCenter
        # if shared.Dataship.debug_mode > 0:
        #     print("mx: %d, my: %d" % (mx, my))

        # check if they clicked near the x,y postion of a target.
        for target in self.targetDetails:
            # translate target x,y to screen coordinates.
            #if shared.Dataship.debug_mode > 0:
                #print("target: %s, x: %d, y: %d" % (target, self.targetDetails[target]["x"], self.targetDetails[target]["y"]))
            if mx >= self.targetDetails[target]["x"] - self.icon_scale and mx <= self.targetDetails[target]["x"] + self.icon_scale and my >= self.targetDetails[target]["y"] - self.icon_scale and my <= self.targetDetails[target]["y"] + self.icon_scale:
                self.targetDetails[target]["selected"] = True
                dataship.targetData[0].selected_target = target # save the callsign of selected target in aircraft.traffic.selected_target
                if shared.Dataship.debug_mode > 0:
                    print("selected target: %s" % target)
                break
            

    # handle mouse wheel events
    def processMouseWheel(self, dataship:Dataship, mx, my, wheel_position):
        #print("TrafficScope processMouseWheel: %d x %d" % (mx, my))
        if wheel_position > 0:
            # zoom in
            self.setScaleInMiles(self.scope_scale_miles + 5)
        else:
            # zoom out
            self.scope_scale_miles = max(1, self.scope_scale_miles - 5)
            self.setScaleInMiles(self.scope_scale_miles)

    # send a message to the selected target (called by self.buttonsCheckClick)
    def sendMsg(self,dataship:Dataship,button):
        # go through all buttons.
        # for b in self.buttons:
        #     if b["id"].startswith("send_yo"):
        #         b["selected"] = False

        # get the text from the button.
        text = button["text"] # remove the "Send " from the text.
        text = text.replace("Send ", "")
        theTarget = self.targetData.get_selected_target()
        if theTarget is not None:
            print("targetScope: Sending Msg ", text, " to ", theTarget.address)
        else:
            print(f"targetScope: sendMsg: {text} to ALL")    
        self.targetData.sendMsg(text, theTarget)
        



# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python

