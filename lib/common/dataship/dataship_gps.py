#!/usr/bin/env python

from enum import Enum
import inspect
from typing import List, Any
import time

#############################################
## Class: GPSData
class GPSData(object):
    def __init__(self):
        self.inputSrcName = None
        self.inputSrcNum = None

        self.Source = None # Source Name.

        self.Lat = None   # latitude in decimal degrees
        self.Lon = None   # longitude in decimal degrees
        self.Alt = None   # in feet MSL
        self.GPSTime = None
        self.GPSTime_string = None
        self.GPSDate_string = None
        self.LastUpdate = None
        
        self.Alt = None  # ft MSL
        self.GndTrack = None # True track from GPS.
        self.GndSpeed = None

        self.AltPressure = None # Pressure altitude in feet (some GPS units report this)

        self.Mag_Decl = None # Magnetic variation 10th/deg West = Neg
        self._calc_decl = None # cached declination computed from Lat/Lon (see get_mag_decl)
        self._calc_decl_pos = None

        self.EWVelDir = None  # E or W
        self.EWVelmag = None  # x.x m/s
        self.NSVelDir = None  # N or S
        self.NSVelmag = None  # x.x m/s
        self.VVelDir = None  # U or D
        self.VVelmag = None  # x.xx m/s

        self.SatsTracked = None
        self.SatsVisible = None
        self.GPSStatus = None # GPS status. 0=Acquiring, 1=dead reckoning, 2=2d fix, 3=3dfix, 4=2dfix(imu), 5=3dfix(imu)
        self.GPSWAAS = None # GPS waas.  False, or True
        self.Accuracy = None # GPS accuracy. 0=None, 1=2D, 2=3D

        self.msg_count = 0
        self.msg_last = None
        self.msg_bad = 0
        self.data_format = 0
        
    def get_status_string(self):
        if(self.GPSStatus==None): 
            return "NA"
        elif(self.GPSStatus==0):
            return "Acquiring"
        elif(self.GPSStatus==1):
            return "Acquiring" #GPS internal dead reckoning
        elif(self.GPSStatus==2):
            return "2D fix"
        elif(self.GPSStatus==3):
            return "3D fix"
        elif(self.GPSStatus==4):
            return "2D fix+" #2D fix EFIS dead reckoning (IMU)
        elif(self.GPSStatus==5):
            return "3D fix+" #3D fix EFIS dead reckoning (IMU)

    def set_gps_location(self, lat, lon, alt, timeString=None):
        self.Lat = lat
        self.Lon = lon
        self.Alt = alt
        if timeString is not None:
            self.GPSTime = timeString

        self.LastUpdate = time.time()
    
    def get_mag_decl(self):
        '''
        Magnetic declination in degrees (East = positive, West = negative).
        True = Magnetic + declination.
        Uses Mag_Decl if the input source provides it, else computes it from Lat/Lon
        using the World Magnetic Model. The computed value is cached and only
        recalculated when position moves more than ~0.5 deg, so it is cheap to call per frame.
        Returns 0 if unknown.
        '''
        if self.Mag_Decl is not None:
            return self.Mag_Decl
        if self.Lat is None or self.Lon is None:
            return self._calc_decl or 0
        if (self._calc_decl_pos is None or
                abs(self.Lat - self._calc_decl_pos[0]) > 0.5 or
                abs(self.Lon - self._calc_decl_pos[1]) > 0.5):
            try:
                from lib.geomag import declination
                self._calc_decl = declination(self.Lat, self.Lon)
            except Exception as e:
                print(f"GPSData: declination calc failed: {e}")
                self._calc_decl = 0
            self._calc_decl_pos = (self.Lat, self.Lon)
        return self._calc_decl

    # get ground speed in converted format.
    def get_gs(self):
        if(self.GndSpeed == None):
            return None
        if(self.data_format==0):
            return self.GndSpeed # mph
        if(self.data_format==1):
            return self.GndSpeed * 0.8689758 #knots
        if(self.data_format==2):
            return self.GndSpeed* 1.609 #km/h
    
        # get speed format description
    def get_speed_description(self):
        if(self.data_format==0):
            return "mph"
        if(self.data_format==1):
            return "kts"
        if(self.data_format==2):
            return "km/h"


# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
