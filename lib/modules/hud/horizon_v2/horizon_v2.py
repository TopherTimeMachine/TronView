#!/usr/bin/env python

#################################################
# Module: Hud Horizon
# Topher 2021.
# Adapted from F18 HUD Screen code by Brian Chesteen.

from lib.modules._module import Module
from lib import hud_graphics
from lib import hud_utils
from lib import smartdisplay
import pygame
import math
from lib.common import shared
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_targets import TargetData
from lib.common.dataship.dataship_gps import GPSData
from lib.common.dataship.dataship_imu import IMUData
from lib.common.dataship.dataship_air import AirData

# constants for the +/-10 degree pitch ladder winglets
_COS10 = math.cos(math.radians(10))
_SIN10 = math.sin(math.radians(10))


class horizon_v2(Module):
    # called only when object is first created.
    def __init__(self):
        Module.__init__(self)
        self.name = "HUD Horizon V2"  # set name
        self.flight_path_color = (255, 0, 255)  # Default color, can be changed via settings
        self.show_targets = True
        self.target_distance_threshold = 10
        self.fov_x = hud_utils.readConfigFloat("HUD", "fov_x", 13.942) # Field of View X in degrees
        #self.fov_y = hud_utils.readConfigInt("HUD", "fov_y", 13.942) # Field of View y in degrees
        self.target_positions = {}  # Store smoothed positions for each target
        self.target_smoothing = 0.2  # Default smoothing factor (0-1), lower = smoother
        self.fpm_smoothing = 0.1  # flight path marker smoothing (0-1), lower = smoother
        self.fpm_min_speed_mph = 20  # below this speed track and flight path angle are not meaningful

        # Add new settings for horizon line
        self.horizon_line_color = (255, 165, 0)  # Default default to orange
        self.horizon_line_thickness = 4  # Default thickness
        self.horizon_line_length = 0.8  # Percentage of screen width
       
        self.source_imu_index_name = ""  # name of the primary imu. used to the aircraft heading, pitch, roll
        self.source_imu_index = 0  # index of the primary imu.
        self.source_imu_index2_name = "NONE"  # name of the secondary imu. (optional)
        self.source_imu_index2 = None  # index of the secondary imu. (optional)
        self.camera_head_imu = None  # IMU object for camera head. Human Head view.

        self.pxy_div = hud_utils.readConfigInt("HUD", "vertical_pixels_per_degree", 30)  # Y axis number of pixels per degree divisor
        self.y_offset = hud_utils.readConfigInt("HUD", "Horizon_Offset", 0)  #  Horizon/Waterline Pixel Offset from HUD Center Neg Numb moves Up, Default=0               

        # Add smoothing variables for horizon lines
        self.horizon_smoothing = 0.25  # Smoothing factor (0-1), lower = smoother
        self.prev_horizon_state = {
            'pitch': 0,
            'roll': 0,
            'camera_yaw': 0,
            'camera_pitch': 0,
            'camera_roll': 0
        }

        self.imuData = IMUData()
        self.gpsData = GPSData()
        self.airData = AirData()
        self.targetData = TargetData()

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
        target_font_size = hud_utils.readConfigInt("HUD", "target_font_size", 12)

        # fonts
        self.font = pygame.font.SysFont(None, 30)
        self.font_target = pygame.font.SysFont("monospace", target_font_size, bold=False)

        self.surface = None  # set each frame in draw(). normally maps directly onto the display.
        self.MainColor = (0, 255, 0)  # main color of hud graphics
        self.line_thickness = hud_utils.readConfigInt("HUD", "line_thickness", 2)
        self.ahrs_line_deg = hud_utils.readConfigInt("HUD", "vertical_degrees", 5)

        self.line_mode = hud_utils.readConfigInt("HUD", "line_mode", 1)
        self.caged_mode = 1 # default on
        self.center_circle_mode = hud_utils.readConfigInt("HUD", "center_circle", 4)

        # flight path marker smoothing state.
        self.fpm_fpa = None
        self.fpm_drift = None
        self.pitch_label_cache = {}  # rendered pitch ladder numbers
        self.offscreen_surface = None  # only used when we can't draw directly to the display

        self.x_offset = 0
        self.xCenter = self.width // 2
        self.yCenter = self.height // 2
        
        # Initialize local data objects with defaults
        self.imuData = IMUData()
        self.gpsData = GPSData() 
        self.airData = AirData()
        self.targetData = TargetData()

        # Set references to first available data sources if they exist
        if shared.Dataship.imuData:
            self.imuData = shared.Dataship.imuData[0]
        if shared.Dataship.gpsData:
            self.gpsData = shared.Dataship.gpsData[0]
        if shared.Dataship.airData:
            self.airData = shared.Dataship.airData[0]
        if shared.Dataship.targetData:
            self.targetData = shared.Dataship.targetData[0]

    #############################################
    ## Function: generateHudReferenceLineArray
    ## create array of horz lines based on pitch, roll, etc.
    ## cos_roll/sin_roll can be passed in so trig is computed once per frame instead of once per line.
    def generateHudReferenceLineArray(
        self,screen_width, screen_height, ahrs_center, pxy_div, pitch=0, roll=0, deg_ref=0, line_mode=1,
        cos_roll=None, sin_roll=None,
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

        if cos_roll is None or sin_roll is None:
            roll_rad = math.radians(roll)
            cos_roll = math.cos(roll_rad)
            sin_roll = math.sin(roll_rad)

        ahrs_center_x, ahrs_center_y = ahrs_center
        px_per_deg_y = screen_height / pxy_div
        pitch_offset = px_per_deg_y * (-pitch + deg_ref)

        # cos(90 - roll) == sin(roll), sin(90 - roll) == cos(roll)
        center_x = ahrs_center_x - (pitch_offset * sin_roll)
        center_y = ahrs_center_y - (pitch_offset * cos_roll)

        half_x_len = length * cos_roll / 2
        half_y_len = length * sin_roll / 2

        start_x = center_x - half_x_len
        end_x = center_x + half_x_len
        start_y = center_y + half_y_len
        end_y = center_y - half_y_len

        # winglets: line end points rotated +/-10 degrees about the line center.
        c, s = _COS10, _SIN10
        sdx, sdy = start_x - center_x, start_y - center_y
        edx, edy = end_x - center_x, end_y - center_y
        xRot = center_x + c * sdx + s * sdy
        yRot = center_y - s * sdx + c * sdy
        xRot1 = center_x + c * edx - s * edy
        yRot1 = center_y + s * edx + c * edy
        xRot2 = center_x + c * edx + s * edy
        yRot2 = center_y - s * edx + c * edy
        xRot3 = center_x + c * sdx - s * sdy
        yRot3 = center_y + s * sdx + c * sdy

        return [[xRot, yRot],[start_x, start_y],[end_x, end_y],[xRot1, yRot1],[xRot2, yRot2],[xRot3, yRot3]]


    #############################################
    ## Function: draw_dashed_line
    ## plain float math (no temporary Point objects per dash).
    def draw_dashed_line(self,surf, color, start_pos, end_pos, width=1, dash_length=10):
        x0, y0 = start_pos
        dx = end_pos[0] - x0
        dy = end_pos[1] - y0
        length = int(math.hypot(dx, dy))
        if length == 0:
            return
        ux = dx / length
        uy = dy / length
        draw_line = pygame.draw.line
        for index in range(0, length // dash_length, 2):
            a = index * dash_length
            b = a + dash_length
            draw_line(surf, color, (x0 + ux * a, y0 + uy * a), (x0 + ux * b, y0 + uy * b), width)

    #############################################
    ## Function: get_pitch_label
    ## pitch ladder numbers are cached instead of being rendered every frame.
    def get_pitch_label(self, value, color):
        key = (value, tuple(color))
        label = self.pitch_label_cache.get(key)
        if label is None:
            label = self.font.render(str(value), False, color)
            self.pitch_label_cache[key] = label
        return label

    def draw_circle(self,surface,color,center,radius,width):
        pygame.draw.circle(
            surface,
            color,
            (int(center[0]),int(center[1])),
            radius,
            width,
        )

    #############################################
    ## Function draw aircraft horizon lines
    def draw_aircraft_horz_lines(
        self,
        width,
        height,
        ahrs_center,
        ahrs_line_deg,
        pitch,
        roll,
        color,
        line_thickness,
        line_mode,
        font,
        pxy_div,
        pos
    ):
        # Apply smoothing to aircraft and camera attitudes
        def smooth_angle(current, previous, smoothing):
            # Handle angle wrapping for heading/yaw
            diff = ((current - previous + 180) % 360) - 180
            return previous + diff * smoothing

        # Get current values
        current_pitch = pitch or 0
        current_roll = roll or 0
        
        # Calculate camera offsets
        camera_yaw = 0
        camera_pitch = 0
        camera_roll = 0
        if self.camera_head_imu is not None and self.camera_head_imu.yaw is not None:
            camera_yaw = ((self.camera_head_imu.yaw - self.imuData.yaw + 180) % 360) - 180
            camera_pitch = -self.camera_head_imu.pitch
            camera_roll = self.camera_head_imu.roll

        # Calculate effective roll angle just like in draw_horizon_line()
        cam_yaw_rad = math.radians(camera_yaw)
        effective_roll = (-(current_roll - camera_roll) * math.cos(cam_yaw_rad)) /2
        
        # When looking up/down, horizon line should curve
        pitch_induced_curve = camera_pitch * math.sin(cam_yaw_rad) * 0.5
        effective_roll += pitch_induced_curve

        # Smooth all angles
        smoothed_pitch = smooth_angle(current_pitch, self.prev_horizon_state['pitch'], self.horizon_smoothing)
        smoothed_roll = smooth_angle(effective_roll, self.prev_horizon_state['roll'], self.horizon_smoothing)
        smoothed_cam_yaw = smooth_angle(camera_yaw, self.prev_horizon_state['camera_yaw'], self.horizon_smoothing)
        smoothed_cam_pitch = smooth_angle(camera_pitch, self.prev_horizon_state['camera_pitch'], self.horizon_smoothing)
        smoothed_cam_roll = smooth_angle(camera_roll, self.prev_horizon_state['camera_roll'], self.horizon_smoothing)

        # Store current values for next frame
        self.prev_horizon_state.update({
            'pitch': smoothed_pitch,
            'roll': smoothed_roll,
            'camera_yaw': smoothed_cam_yaw,
            'camera_pitch': smoothed_cam_pitch,
            'camera_roll': smoothed_cam_roll
        })

        # Calculate pixel offset based on smoothed yaw difference
        pixels_per_degree = width / self.fov_x
        x_offset = -smoothed_cam_yaw * pixels_per_degree
        
        # Adjust center point based on camera yaw
        center_x = width // 2 + x_offset
        center_y = height // 2
        adjusted_center = (center_x, center_y)

        # roll trig computed once per frame (not once per ladder line)
        roll_rad = math.radians(smoothed_roll)
        cos_roll = math.cos(roll_rad)
        sin_roll = math.sin(roll_rad)

        # Calculate visible bounds
        left_bound = 0
        right_bound = width
        surface = self.surface
        draw_lines = pygame.draw.lines
        text_margin = int(width / 100)

        # Draw lines centered on the screen using smoothed values
        for l in range(-60, 61, ahrs_line_deg):
            if abs(l) > 45:
                if l % 5 == 0 and l % 10 != 0:
                    continue

            line_coords = self.generateHudReferenceLineArray(
                width,
                height,
                adjusted_center,
                pxy_div,
                pitch=smoothed_pitch,
                deg_ref=l,
                line_mode=line_mode,
                cos_roll=cos_roll,
                sin_roll=sin_roll,
            )

            # Check if any part of the line is within the visible area
            # Convert line endpoints to screen-relative coordinates
            screen_x1 = line_coords[1][0] - x_offset
            screen_x2 = line_coords[2][0] - x_offset

            # Skip if line is completely outside visible area
            if (screen_x1 < left_bound and screen_x2 < left_bound) or \
               (screen_x1 > right_bound and screen_x2 > right_bound):
                continue

            # Skip lines that are completely above or below the module
            min_y = min(line_coords[1][1], line_coords[2][1])
            max_y = max(line_coords[1][1], line_coords[2][1])
            if max_y < -20 or min_y > height + 20:
                continue

            # Draw lines
            if l < 0:
                self.draw_dashed_line(
                    surface,
                    color,
                    line_coords[1],
                    line_coords[2],
                    width=line_thickness,
                    dash_length=5,
                )
                # Only draw end markers if they're within view
                if left_bound <= screen_x2 <= right_bound:
                    draw_lines(surface, color, False, (line_coords[2], line_coords[4]), line_thickness)
                if left_bound <= screen_x1 <= right_bound:
                    draw_lines(surface, color, False, (line_coords[1], line_coords[5]), line_thickness)
            else:
                visible_points = []
                for point in (line_coords[0], line_coords[1], line_coords[2], line_coords[3]):
                    screen_x = point[0] - x_offset
                    if left_bound <= screen_x <= right_bound:
                        visible_points.append(point)

                if len(visible_points) >= 2:
                    draw_lines(surface, color, False, visible_points, line_thickness)

            # Draw degree text if within view
            if l != 0 and l % 5 == 0:
                text = self.get_pitch_label(l, color)
                text_width, text_height = text.get_size()
                text_x = int(line_coords[1][0]) - (text_width + text_margin)
                text_screen_x = text_x - x_offset

                if left_bound <= text_screen_x <= right_bound:
                    surface.blit(text, (text_x, int(line_coords[1][1]) - text_height / 2))


    def draw_center(self,smartdisplay, x_offset, y_offset):
        '''
        Draw the center circle.
        '''
        center_x = self.width // 2
        center_y = self.height // 2

        if self.center_circle_mode == 1:
            pygame.draw.circle(
                self.surface,
                self.MainColor,
                (center_x, center_y),
                3,
                1,
            )
        elif self.center_circle_mode == 2:
            pygame.draw.circle(
                self.surface,
                self.MainColor,
                (center_x, center_y),
                15,
                1,
            )
        # draw center + Gun Cross
        elif self.center_circle_mode == 3:
            pygame.draw.circle(
                self.surface,
                self.MainColor,
                (center_x, center_y),
                50,
                1,
            )
        # draw water line center.
        elif self.center_circle_mode == 5:
            pygame.draw.line(
                self.surface,
                self.MainColor,
                [center_x - 10, center_y + 20],
                [center_x, center_y],
                3,
            )
            pygame.draw.line(
                self.surface,
                self.MainColor,
                [center_x - 10, center_y + 20],
                [center_x - 20, center_y],
                3,
            )
            pygame.draw.line(
                self.surface,
                self.MainColor,
                [center_x - 35, center_y],
                [center_x - 20, center_y],
                3,
            )
            pygame.draw.line(
                self.surface,
                self.MainColor,
                [center_x + 10, center_y + 20],
                [center_x, center_y],
                3,
            )
            pygame.draw.line(
                self.surface,
                self.MainColor,
                [center_x + 10, center_y + 20],
                [center_x + 20, center_y],
                3,
            )
            pygame.draw.line(
                self.surface,
                self.MainColor,
                [center_x + 35, center_y],
                [center_x + 20, center_y],
                3,
            )

    def get_true_heading(self):
        '''
        Aircraft heading referenced to TRUE north (so it can be compared with GPS ground track and
        ADS-B bearings, which are both true). IMU heading is magnetic, so declination is added.
        Falls back to GPS ground track if there is no heading. Returns None if neither is available.
        '''
        mag_heading = self.imuData.mag_head if self.imuData.mag_head is not None else self.imuData.yaw
        if mag_heading is not None:
            return (mag_heading + self.gpsData.get_mag_decl()) % 360
        return self.gpsData.GndTrack

    def get_flight_path_angle(self):
        '''
        Flight path angle (gamma) in degrees, derived from vertical speed and ground speed.
        Returns None if vertical speed is unknown.
        '''
        if self.airData.VSI is None:
            return None
        speed_mph = self.gpsData.GndSpeed
        if speed_mph is None:
            speed_mph = self.airData.TAS if self.airData.TAS is not None else self.airData.IAS
        if speed_mph is None or speed_mph < self.fpm_min_speed_mph:
            return 0.0  # on the ground / too slow to get a meaningful angle.
        return math.degrees(math.atan2(self.airData.VSI, speed_mph * 88.0))  # 1 mph = 88 ft/min

    def get_drift_angle(self):
        '''
        Drift angle in degrees (GPS true ground track - true heading). Positive = track right of nose.
        Returns 0 when there is no track or the aircraft is too slow for track to be valid.
        '''
        track = self.gpsData.GndTrack
        if track is None or self.gpsData.GndSpeed is None or self.gpsData.GndSpeed < self.fpm_min_speed_mph:
            return 0.0
        heading = self.get_true_heading()
        if heading is None:
            return 0.0
        return ((track - heading + 180) % 360) - 180

    def draw_flight_path(self, dataship:Dataship, smartdisplay, x_offset, y_offset):
        '''
        Draw the flight path marker (FPM) and ghost FPM.
        Vertical: flight path angle referenced to aircraft pitch (the waterline is the screen center),
        using the same pixels/degree as the pitch ladder.
        Horizontal: drift angle (true track vs true heading) using the same pixels/degree as the FOV.
        Caged mode keeps the FPM centered laterally and shows the ghost FPM at the drift position.
        '''
        fpa = self.get_flight_path_angle()
        if fpa is None or self.imuData.pitch is None:
            return

        # smooth (exponential moving average)
        a = self.fpm_smoothing
        self.fpm_fpa = fpa if self.fpm_fpa is None else self.fpm_fpa + (fpa - self.fpm_fpa) * a
        drift = self.get_drift_angle()
        self.fpm_drift = drift if self.fpm_drift is None else self.fpm_drift + (drift - self.fpm_drift) * a

        px_per_deg_x = self.width / self.fov_x
        px_per_deg_y = self.height / self.pxy_div
        pitch = self.prev_horizon_state['pitch']  # same (smoothed) pitch used to draw the ladder

        center_x = self.width // 2
        center_y = self.height // 2

        # clamp so the marker stays on the display at the edge of the FOV
        max_x = max(0, center_x - 30)
        max_y = max(0, center_y - 30)
        gfpv_dx = max(-max_x, min(max_x, self.fpm_drift * px_per_deg_x))
        fpv_dy = max(-max_y, min(max_y, (self.fpm_fpa - pitch) * px_per_deg_y))

        fpv_x = center_x if self.caged_mode == 1 else center_x + gfpv_dx
        fpv_y = center_y - fpv_dy
        color = self.flight_path_color

        self.draw_circle(self.surface, color, (fpv_x, fpv_y), 15, 4)
        pygame.draw.line(self.surface, color, [fpv_x - 15, fpv_y], [fpv_x - 30, fpv_y], 2)
        pygame.draw.line(self.surface, color, [fpv_x + 15, fpv_y], [fpv_x + 30, fpv_y], 2)
        pygame.draw.line(self.surface, color, [fpv_x, fpv_y - 15], [fpv_x, fpv_y - 30], 2)

        if self.caged_mode == 1:
            # ghost FPM at the actual (uncaged) drift position
            gfpv_x = center_x + gfpv_dx
            pygame.draw.line(self.surface, color, [gfpv_x - 15, fpv_y], [gfpv_x - 30, fpv_y], 2)
            pygame.draw.line(self.surface, color, [gfpv_x + 15, fpv_y], [gfpv_x + 30, fpv_y], 2)
            pygame.draw.line(self.surface, color, [gfpv_x, fpv_y - 15], [gfpv_x, fpv_y - 30], 2)

    # called every redraw for this screen module
    def draw(self, dataship:Dataship, smartdisplay, pos=(0, 0)):
        '''
        Draw method to draw all the elements of the horizon.
        Draws directly onto the display (through a subsurface at pos) so there is no full size
        surface to clear and blit every frame.
        '''
        x, y = pos

        self.surface = self.getDrawSurface(pos)
        use_offscreen = self.surface is None
        if use_offscreen:
            # module is partly off the top/left of the screen. fall back to an offscreen surface.
            if self.offscreen_surface is None or self.offscreen_surface.get_size() != (self.width, self.height):
                self.offscreen_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.surface = self.offscreen_surface
            self.surface.fill((0, 0, 0, 0))

        if self.imuData.roll is None or self.imuData.pitch is None or self.imuData.yaw is None:
            # draw a red X on the screen.
            pygame.draw.line(self.surface, (255,0,0), (0,0), (self.width,self.height), 4)
            pygame.draw.line(self.surface, (255,0,0), (self.width,0), (0,self.height), 4)

            # if no yaw then say no yaw
            if self.imuData.yaw is None:
                self.surface.blit(self.font.render("No Yaw", True, (255,255,255)), (self.width // 2, self.height // 2 - 100))
            # if no pitch then say no pitch
            if self.imuData.pitch is None:
                self.surface.blit(self.font.render("No Pitch", True, (255,255,255)), (self.width // 2, self.height // 2 - 50))
            # if no roll then say no roll
            if self.imuData.roll is None:
                self.surface.blit(self.font.render("No Roll", True, (255,255,255)), (self.width // 2, self.height // 2 + 50))
        else:
            # Calculate camera head offsets if present
            camera_pitch = 0
            camera_roll = 0
            camera_yaw = 0

            if self.camera_head_imu is not None and self.camera_head_imu.pitch is not None and self.camera_head_imu.roll is not None and self.camera_head_imu.yaw is not None:
                camera_pitch = -self.camera_head_imu.pitch
                camera_roll = self.camera_head_imu.roll
                camera_yaw = ((self.camera_head_imu.yaw - self.imuData.yaw + 180) % 360) - 180

                # Draw the horizon line from camera perspective
                self.draw_horizon_line(dataship, camera_yaw, camera_pitch, camera_roll)

                # Apply camera offsets to aircraft attitude for the rest of the display
                adjusted_pitch = self.imuData.pitch - camera_pitch
                adjusted_roll = self.imuData.roll - camera_roll
            else:
                adjusted_pitch = self.imuData.pitch
                adjusted_roll = self.imuData.roll

            # Draw aircraft horizon lines with adjusted angles
            self.draw_aircraft_horz_lines(
                self.width,
                self.height,
                ((self.width // 2), self.height // 2),
                self.ahrs_line_deg,
                adjusted_pitch,
                adjusted_roll,
                self.MainColor,
                self.line_thickness,
                self.line_mode,
                self.font,
                self.pxy_div,
                (x, y)
            )

            # Only show targets if camera is roughly aligned with aircraft heading
            if self.show_targets and abs(camera_yaw) < 45:
                heading = self.get_true_heading()
                if heading is not None:
                    for t in self.targetData.targets:
                        if t.dist is not None and t.dist < self.target_distance_threshold and t.brng is not None:
                            self.draw_target(t, heading)

            # Draw center and flight path
            self.draw_center(smartdisplay, x, y)
            if abs(camera_yaw) < 45:  # Only show flight path when looking forward
                self.draw_flight_path(dataship, smartdisplay, x, y)

        if use_offscreen:
            self.pygamescreen.blit(self.surface, pos)

    def draw_target(self, t, heading):
        '''
        Draw a traffic target on the HUD.
        heading is the aircraft TRUE heading, because target bearings (t.brng) are true.
        Target position uses the same geometry as the pitch ladder (pixels/degree, pitch and roll)
        so targets stay registered to the ladder.
        '''
        # Calculate the relative bearing to the target
        relative_bearing = (t.brng - heading + 180) % 360 - 180

        # Check if the target is within the field of view
        if abs(relative_bearing) > self.fov_x / 2:
            return  # Target is outside the field of view, don't draw it

        if t.altDiff is None:
            return

        # elevation angle to the target (both in feet). t.dist is in statute miles.
        elevation_deg = math.degrees(math.atan2(t.altDiff, t.dist * 5280.0))
        pitch = self.prev_horizon_state['pitch']
        roll = self.prev_horizon_state['roll']

        # position relative to the screen center before roll (same scale as the ladder)
        dx = relative_bearing * (self.width / self.fov_x)
        dy = -(elevation_deg - pitch) * (self.height / self.pxy_div)

        # rotate with the ladder roll
        roll_rad = math.radians(roll)
        cos_r = math.cos(roll_rad)
        sin_r = math.sin(roll_rad)
        rotated_x = self.xCenter + dx * cos_r + dy * sin_r
        rotated_y = self.yCenter - dx * sin_r + dy * cos_r

        # Apply smoothing
        target_key = t.callsign
        if target_key not in self.target_positions:
            self.target_positions[target_key] = (rotated_x, rotated_y)
        else:
            # Interpolate between old and new positions
            old_x, old_y = self.target_positions[target_key]
            smooth_x = old_x + (rotated_x - old_x) * self.target_smoothing
            smooth_y = old_y + (rotated_y - old_y) * self.target_smoothing
            self.target_positions[target_key] = (smooth_x, smooth_y)

        # Use smoothed position for drawing
        xx, yy = self.target_positions[target_key]

        # Draw target using smoothed positions
        pygame.draw.circle(self.surface, (200,255,255), (int(xx), int(yy)), 6, 0)
        labelCallsign = self.font_target.render(t.callsign, False, (200,255,255), (0,0,0))
        labelCallsign_rect = labelCallsign.get_rect()
        self.surface.blit(labelCallsign, (int(xx) + 10, int(yy)))
        labelInfo = self.font_target.render(f"{t.dist:.1f}mi {t.altDiff:+,}ft", False, (200,255,255), (0,0,0))
        self.surface.blit(labelInfo, (int(xx) + 10, int(yy) + labelCallsign_rect.height))


    # cycle through the modes.
    def cyclecaged_mode(self):
        self.caged_mode = self.caged_mode + 1
        if self.caged_mode > 1:
            self.caged_mode = 0

    def clear(self):
        #self.ahrs_bg.fill((0, 0, 0))  # clear screen
        print("clear")

    # return a dict of objects that are used to configure the module.
    def get_module_options(self):
        imu_list = shared.Dataship.imuData
        self.imu_ids = []
        for imu in imu_list:  # iterate through the list directly
            if hasattr(imu, 'id'):  # check if imu has id attribute
                self.imu_ids.append(str(imu.id))
            
        if len(self.source_imu_index_name) == 0 and self.imu_ids: # if primary imu name is not set and we have IMUs
            self.source_imu_index_name = self.imu_ids[self.source_imu_index]  # select first one
            
        self.imu_ids2 = self.imu_ids.copy()  # duplicate the list for the secondary imu
        self.imu_ids2.append("NONE")

        # each item in the dict represents a configuration option.  These are variable in this class that are exposed to the user to edit.
        options = {
            "source_imu_index_name": {
                "type": "dropdown",
                "label": "Primary IMU",
                "description": "IMU to use for the 3D object.",
                "options": self.imu_ids,
                "post_change_function": "changeSource1IMU"
            },
            "source_imu_index": {
                "type": "int",
                "hidden": True,  # hide from the UI, but save to json screen file.
                "default": 0
            },
            "source_imu_index2_name": {
                "type": "dropdown",
                "label": "Secondary IMU (Camera Head)",
                "description": "If selected then 2nd IMU will be position camera. As if it was mounted on the Primary IMU.",
                "options": self.imu_ids2,
                "post_change_function": "changeSource2IMU"
            },
            "source_imu_index2": {
                "type": "int",
                "hidden": True,  # hide from the UI, but save to json screen file.
                "default": 0
            },
            "line_mode": {
                "type": "bool",
                "default": False,
                "label": "Line Mode",
                "description": ""
            },
            "line_thickness": {
                "type": "int",
                "default": 2,
                "min": 1,
                "max": 4,
                "label": "Line Thickness",
                "description": ""
            },
            "MainColor": {
                "type": "color",
                "default": (255, 255, 255),
                "label": "Line Color", 
            },
            "flight_path_color": {
                "type": "color",
                "default": (255, 0, 255),
                "label": "Flight Path Color",
            },
            "show_targets": {
                "type": "bool",
                "default": True,
                "label": "Show Targets",
                "description": ""
            },
            "target_distance_threshold": {
                "type": "int",
                "default": self.target_distance_threshold,
                "min": 1,
                "max": 150,
                "label": "Target Dist Thres",
                "description": ""
            },
            "fov_x": {
                "type": "float",
                "default": self.fov_x,
                "min": 5,
                "max": 60,
                "label": "FOV X",
                "description": "Field of View X in degrees"
            },
            "pxy_div": {    
                "type": "int",
                "default": self.pxy_div,
                "min": 20,
                "max": 60,
                "label": "Vert Pixels Per Degree",
                "description": "Number of pixels per degree divisor"
            },
            "target_smoothing": {
                "type": "float",
                "default": 0.2,
                "min": 0.01,
                "max": 1.0,
                "label": "Target Smoothing",
                "description": "Target position smoothing (0.01-1.0, lower = smoother)"
            },
            "horizon_line_color": {
                "type": "color",
                "default": (255, 165, 0),  # Orange
                "label": "Horizon Line Color",
                "description": "Color of the true horizon reference line"
            },
            "horizon_line_thickness": {
                "type": "int",
                "default": 4,
                "min": 1,
                "max": 10,
                "label": "Horizon Line Thickness",
                "description": "Thickness of the horizon reference line"
            },
            "horizon_smoothing": {
                "type": "float",
                "default": 0.15,
                "min": 0.01,
                "max": 1.0,
                "label": "Horizon Smoothing",
                "description": "Horizon movement smoothing (0.01-1.0, lower = smoother)"
            }
        }
        
        return options

    def update_flight_path_color(self, new_color):
        self.flight_path_color = new_color

    def changeSource1IMU(self):
        '''
        Change the primary IMU.
        '''
        # source_imu_index_name got changed. find the index of the imu id in the imu list.
        self.source_imu_index = self.imu_ids.index(self.source_imu_index_name)
        self.imuData = shared.Dataship.imuData[self.source_imu_index]
        self.imuData.home(delete=True) 

    def changeSource2IMU(self):
        if self.source_imu_index2_name == "NONE":
            self.source_imu_index2 = None
            self.camera_head_imu = None
        else:
            self.source_imu_index2 = self.imu_ids2.index(self.source_imu_index2_name)
            self.imuData2 = shared.Dataship.imuData[self.source_imu_index2]
            self.imuData2.home(delete=True)
            self.camera_head_imu = self.imuData2

    def draw_horizon_line(self, dataship:Dataship, camera_yaw=0, camera_pitch=0, camera_roll=0):
        """
        Draw a single line representing the true horizon from the camera's perspective.
        Takes into account both aircraft attitude and camera head position.
        """
        # Screen center coordinates
        center_x = self.width // 2
        center_y = self.height // 2
        
        # Convert all angles to radians
        pitch_rad = math.radians(self.imuData.pitch)
        roll_rad = math.radians(self.imuData.roll)
        cam_yaw_rad = math.radians(camera_yaw)
        cam_pitch_rad = math.radians(camera_pitch) 
        cam_roll_rad = math.radians(camera_roll)

        # Calculate effective pitch angle (how far horizon appears from center)
        # When looking straight ahead, aircraft pitch directly affects horizon position
        # When looking to the side, pitch effect diminishes with cos of yaw angle
        effective_pitch = self.imuData.pitch * math.cos(cam_yaw_rad) - camera_pitch
        
        # Calculate vertical offset in pixels
        pixels_per_degree = self.height / self.pxy_div
        pitch_offset = effective_pitch * pixels_per_degree
        
        # Calculate effective roll angle
        # When looking straight ahead, use aircraft roll minus camera roll
        # When looking to the side (90°), horizon appears level regardless of aircraft roll
        effective_roll = (self.imuData.roll - camera_roll) * math.cos(cam_yaw_rad)
        
        # When looking up/down, horizon line should curve
        # This creates the effect of horizon curvature when looking up/down
        pitch_induced_curve = camera_pitch * math.sin(cam_yaw_rad) * 0.5
        effective_roll += pitch_induced_curve
        
        # Calculate line endpoints based on effective roll
        roll_rad = math.radians(effective_roll)
        line_length = self.width * self.horizon_line_length / 2
        
        # Calculate endpoints with roll rotation
        x1 = center_x - (line_length * math.cos(roll_rad))
        y1 = (center_y + pitch_offset) - (line_length * math.sin(roll_rad))
        x2 = center_x + (line_length * math.cos(roll_rad))
        y2 = (center_y + pitch_offset) + (line_length * math.sin(roll_rad))

        # Draw the horizon line
        pygame.draw.line(
            self.surface,
            self.horizon_line_color,
            (x1, y1),
            (x2, y2),
            self.horizon_line_thickness
        )

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python


