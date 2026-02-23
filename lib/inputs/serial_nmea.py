#!/usr/bin/env python

# Serial input source
# NMEA 0183 V3.01
# 2/10/2025 - new dataship refactor

from ._input import Input
from . import _utils
import serial
import struct
import time
from lib.common.dataship.dataship import Dataship
from lib.common.dataship.dataship_gps import GPSData
from lib.common.dataship.dataship_nav import NavData
#import airportsdata
import traceback
from lib import hud_utils


#######################################
###     FAA Mode indicator decoder  ###
## A = Autonomous Mode               ##
## C = Caution                       ##
## D = Differential (WAAS)           ##
## E = Estimated/Dead-Reckoning Mode ##
## F = RTK Float Mode                ##
## M = Manual Input Mode             ##
## N = Invalid                       ##
## R = RTK Integer Mode              ##
## S = Simulated Mode                ##
## U = Unsafe                        ##
#######################################

#######################################
###   GPS Quality Indicator Decoder ###
## 0 = No Fix                        ##
## 1 = GPS Fix                       ##
## 2 = Differential (WAAS)           ##
## 3 = PPS Fix                       ##
## 4 = Realtime Kinematic            ##
## 5 = Float RTK                     ##
## 6 = Estimated (Dead-Reckoning)    ##
## 7 = Manual Input Mode             ##
## 8 = Simulated Mode                ##
#######################################

#############################################
### NMEA Sentences Not Used Intentionally ###
## GPGSA = GPS Degree of Precision         ##
## GPGSV = GPS Satellites In View          ##
## GPAP A/B = Autopilot Type A/B           ##
## Most proprietary sentences              ##
#############################################

class serial_nmea(Input):
    def __init__(self):
        self.name = "serial_nmea"
        self.version = 3.01
        self.inputtype = "serial"

        # Setup moving averages to smooth a bit
        self.readings = []
        self.max_samples = 10
        self.readings1 = []
        self.max_samples1 = 20
        self.EOL = 10
        self.gpsData = GPSData()
        self.navData = NavData()

    def safe_float(self, value, default=0.0):
        """Safely convert a string to float, returning default if empty or invalid."""
        try:
            return float(value) if value else default
        except (ValueError, TypeError):
            return default
    
    def safe_int(self, value, default=0):
        """Safely convert a string to int, returning default if empty or invalid."""
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default

    def initInput(self,num, dataship: Dataship):
        Input.initInput(self,num, dataship)  # call parent init Input.
        self.efis_data_port = hud_utils.readConfig(  # serial input... example: "/dev/cu.PL2303G-USBtoUART110"
            self.name, "port", "/dev/ttyUSB0"
        )
        self.efis_data_baudrate = hud_utils.readConfigInt(
            self.name, "baudrate", 9600
        )
        print("nmea_data_port: "+self.efis_data_port)
        print("nmea_data_baudrate: "+str(self.efis_data_baudrate))

        # open serial connection.
        self.ser = serial.Serial(
            port=self.efis_data_port,
            baudrate=self.efis_data_baudrate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=None,
        )

        # check for system platform??
        #if sys.platform.startswith('win'):
        #    self.EOL = 10
        #else:
        #    self.EOL = 13
        self.EOL = 13

        # create a empty gps object.
        self.gpsData = GPSData()
        self.gpsData.id = "nmea_gps"
        self.gpsData.inputSrcName = "nmea"
        self.gpsData.name = self.name
        self.gps_index = len(dataship.gpsData)  # Start at 0
        print("new nmea gps "+str(self.gps_index)+": "+str(self.gpsData))
        dataship.gpsData.append(self.gpsData)

        # create a empty nav object.
        self.navData = NavData()
        self.navData.id = "nmea_nav"
        self.navData.name = self.name
        self.nav_index = len(dataship.navData)  # Start at 0
        print("new nmea nav "+str(self.nav_index)+": "+str(self.navData))
        dataship.navData.append(self.navData)

    # close this input source
    def closeInput(self, dataship: Dataship):
        self.ser.close()

    def convert_nmea_to_decimal_degrees(self, nmea_string, hemi):
        # Handle empty or invalid input
        if not nmea_string:
            return 0.0
            
        try:
            # For longitude (3 digits), use first 3 chars; for latitude (2 digits) use first 2
            if hemi in "WE":  # Longitude
                degrees = self.safe_float(nmea_string[0:3])
                minutes = self.safe_float(nmea_string[3:])
            else:  # Latitude
                degrees = self.safe_float(nmea_string[0:2])
                minutes = self.safe_float(nmea_string[2:])
                
            decimal_degrees = degrees + (minutes / 60)
            
            # Make negative for West/South
            if hemi in "WS":
                decimal_degrees = -decimal_degrees
                
            return decimal_degrees
            
        except (ValueError, IndexError):
            return 0.0  # Return 0 if conversion fails

    #############################################
    ## Function: readMessage
    def readMessage(self, dataship: Dataship):
        #airports = airportsdata.load()
        def mean(nums):
            return float(sum(nums)) / max(len(nums), 1)

        if dataship.errorFoundNeedToExit:
            return dataship
        try:
            x = 0
            t = self.ser.read(1)
            if len(t) != 0:
                x = ord(t)
            if x == 36:
                msg = self.ser.readline()
                checksum = None
                self.gpsData.msg_last = msg
                if self.output_logFile != None:
                    Input.addToLog(self,self.output_logFile,bytes([64]))
                    Input.addToLog(self,self.output_logFile,msg)
                msg = msg.rstrip(b'\r\n')
                try:
                    msg = msg.decode('utf-8')
                except:
                    self.gpsData.msg_bad += 1
                    return self
                try:
                    msg = msg.split('*')
                    checksum = msg[1:]
                    # print(checksum)
                    msg = msg[0]
                    # print(msg)
                    if(self.calcChecksum(msg,checksum)):
                        self.gpsData.msg_count += 1
                    else:
                        self.gpsData.msg_bad += 1
                        return self
                    msg = msg.split(",")
                    # print(msg)
                except:
                   msg = msg.split(",")
                   self.gpsData.msg_count += 1
                sentence = msg[0] # break out sentence ID from the list so we can perform a switch action on it
                match sentence:
                    case "GPRMC": # Recommended Minimum Navigation Info Sentence C
                        utctime = msg[1] # UTC Time in format hhmmss
                        status = msg[2] # GPS Status, A = Acive, V = Warning
                        #lat = msg[3] # Latitude in format ddmm.mmmm (dd = degrees, mm.mmmm = minutes) convert to decimal degrees
                        lat = self.convert_nmea_to_decimal_degrees(msg[3], msg[4])
                        #lon = msg[5] # Longitude in format dddmm.mmmm
                        lon = self.convert_nmea_to_decimal_degrees(msg[5], msg[6])

                        gs = msg[7] # GPS Groundspeed
                        truetrack = msg[8] # GPS Track in true heading
                        date = msg[9] # UTC date in ddmmyy (split into day, month, year)
                        day = date[0:2]
                        month = date[2:4]
                        year = date[4:6]
                        magvar = msg[10] # Magnetic variation x.x degrees
                        magvardir = msg[11] # magnetic variation E or W
                        #mode = msg[12] # FAA Mode, explained at top of file
                        self.gpsData.LastUpdate = time.time()
                        self.gpsData.GPSTime_string = "%s:%s:%s"%(utctime[0:2],utctime[2:4],utctime[4:6])
                        self.gpsData.GPSDate_string = "%s/%s/%s"%(month,day,year)
                        self.time_stamp_string = self.gpsData.GPSTime_string
                        # self.time_stamp_min = int(utctime[2:3])
                        # self.time_stamp_sec = int(utctime[4:5])
                        # dataship.gps.LatHemi = lathemi
                        # dataship.gps.LatDeg = int(lat[0:1])
                        # dataship.gps.LatMin = float(lat[2:8])
                        # dataship.gps.LonHemi = lonhemi
                        # dataship.gps.LonDeg = int(lon[0:2])
                        # dataship.gps.LonMin = int(lon[3:9])
                        self.gpsData.Lat = lat
                        self.gpsData.Lon = lon
                        #self.gpsData.Mag_Decl = float(magvar)

                        # Handle empty ground speed and true track values
                        self.gpsData.GndSpeed = self.safe_float(gs)
                        self.gpsData.GndTrack = self.safe_float(truetrack)
                        # if magvardir is E, then we need to subtract the magvar from the true track?? need to verify this
                        if(magvardir == "E"):
                            self.gpsData.Mag_Decl = (self.gpsData.Mag_Decl - (self.gpsData.Mag_Decl * 2))
                        # self.gpsData.GndTrack = (truetrack + self.gpsData.Mag_Decl)
                        # self.gpsData.GndTrack = self.gpsData.GndTrack

                    case "GPRMB": # Recommended Minimum Navigation Info Sentence B - Note: Destination waypoint is NOT related to the actual flight plan - it is the waypoint currently being navigated to
                        status = msg[1] # A = Active, V = Invalid
                        xtkerror = msg[2] # Crosstrack error NM x.x
                        steerdir = msg[3] # Steer left or right for course? L/R
                        originwpt = msg[4] # Origin Waypoint ID xxxxx
                        destwpt = msg[5] # Destination Waypoint ID xxxxx
                        destlat = self.convert_nmea_to_decimal_degrees(msg[6], msg[7])
                        destlon = self.convert_nmea_to_decimal_degrees(msg[8], msg[9])
                        distwpt = msg[10] # Distance to destination waypoint xx.x
                        destbrg = msg[11] # Bearing in degrees TRUE to destination waypoint xxx.x
                        wptclosure = msg[12] # Closure rate to destination waypoint xxx.x
                        wptarrival = msg[13] # Arrival alarm for destination waypoint A = arriving, V = not arriving
                        mode = msg[14] # FAA Mode, explained at top of file

                        self.navData.WPName = destwpt
                        self.navData.WPDist = self.safe_float(distwpt)
                        self.navData.WPTrack = self.safe_float(destbrg)
                        self.navData.WPLat = destlat
                        self.navData.WPLon = destlon
                    case "GPGGA": # GPS Pos and Altitude
                        utctime = msg[1] # hhmmss
                        lat = self.convert_nmea_to_decimal_degrees(msg[2], msg[3])
                        lon = self.convert_nmea_to_decimal_degrees(msg[4], msg[5])
                        quality = msg[6] # GPS Quality explained at top of file x
                        satnum = msg[7] # Number of satellites used in solution xx
                        hprecision = msg[8] # Horizontal precision in meters x.x
                        gpsalt = msg[9] # GPS Altitude in MSL (geoid) xx.x
                        altunit = msg[10] # GPS Altitude unit of measure X
                        geosep = msg[11] # Geoidal separation between WGS-84 and MSL xx.x
                        geosepunit = msg[12] # unit of measure for geoidal separation X
                        diffage = msg[13] # Age of differential (WAAS) GPS data in seconds x.x
                        diffstation = msg[14] # Station ID of differential reference station (WAAS Station)
                        self.gpsData.LastUpdate = time.time()
                        #self.gpsData.GPSTime_string = "%s/%s/%s %d:%d:%d"%(month,day,year,int(utctime[0:1]),int(utctime[2:3]),int(utctime[4:5]))
                        # self.time_stamp_string = self.gpsData.GPSTime_string
                        # self.time_stamp_min = int(utctime[2:3])
                        # self.time_stamp_sec = int(utctime[4:5])
                        self.gpsData.Lat = lat
                        self.gpsData.Lon = lon
                        self.gpsData.SatsTracked = self.safe_int(satnum)
                        # Handle empty altitude value
                        self.gpsData.Alt = int(round(self.safe_float(gpsalt)))
                        if(quality == "1"):
                            self.gpsData.GPSStatus = 2
                            self.gpsData.GPSWAAS = False
                        if(quality == "2"):
                            self.gpsData.GPSStatus = 3
                            self.gpsData.GPSWAAS = True
                    case "GPGLL": # GPS Lat/Long
                        lat = self.convert_nmea_to_decimal_degrees(msg[1], msg[2])
                        lon = self.convert_nmea_to_decimal_degrees(msg[3], msg[4])
                        utctime = msg[5] # hhmmss
                        status = msg[6] # A = Active, V = Invalid
                        mode = msg[7] # FAA Mode, explained at top of file
                        dataship.sys_time_string = "%d:%d:%d"%(int(utctime[0:1]),int(utctime[2:3]),int(utctime[4:5]))
                        self.time_stamp_string = dataship.sys_time_string
                        # self.time_stamp_min = int(utctime[2:3])
                        # self.time_stamp_sec = int(utctime[4:5])
                        # self.gpsData.LatHemi = lathemi
                        # self.gpsData.LatDeg = int(lat[0:1])
                        # self.gpsData.LatMin = float(lat[2:8])
                        # self.gpsData.LonHemi = lonhemi
                        # self.gpsData.LonDeg = int(lon[0:2])
                        # dataship.gps.LonMin = int(lon[3:9])

                        self.gpsData.Lat = lat
                        self.gpsData.Lon = lon

                        if(mode == "D"):
                            self.gpsData.GPSWAAS = True
                        else:
                            self.gpsData.GPSWAAS = False
                    case "GPBOD": # Bearing waypoint to waypoint
                        brgtrue = msg[1] # Bearing to waypoint in degrees True xx.x
                        brgmag = msg[3] # bearing to waypoint in degrees Magnetic xx.x
                        nextwpt = msg[5] # Destination (next) waypoint XXXX
                        originwpt = msg[6] # Origin (from) waypoint XXXX
                    case "GPBWC": # bearing and distance to waypoint - Great Circle
                        utctime = msg[1] # hhmmss
                        lat = self.convert_nmea_to_decimal_degrees(msg[2], msg[3])
                        lon = self.convert_nmea_to_decimal_degrees(msg[4], msg[5])
                        brgtrue = msg[6] # bearing to next waypoint degrees true xx.x
                        brgmag = msg[8] # bearing to next waypoint degrees magnetic xx.x 
                        distwpt = msg[10] # Distance to next waypoint in nautical miles xx.x
                        nextwpt = msg[12] # Next waypoint ID XXXX
                        mode = msg[13] # FAA Mode, explained at top of file
                        #self.gpsData.GPSTime_string = "%d:%d:%d"%(int(utctime[0:1]),int(utctime[2:3]),int(utctime[4:5]))
                        # self.time_stamp_string = self.gpsData.GPSTime_string
                        # self.time_stamp_min = int(utctime[2:3])
                        # self.time_stamp_sec = int(utctime[4:5])


                        # dataship.gps.LatHemi = lathemi
                        # dataship.gps.LatDeg = int(lat[0:1])
                        # dataship.gps.LatMin = float(lat[2:8])
                        # dataship.gps.LonHemi = lonhemi
                        # dataship.gps.LonDeg = int(lon[0:2])
                        # dataship.gps.LonMin = int(lon[3:9])

                        # set waypoint name, distance, and track
                        self.navData.WPName = nextwpt
                        self.navData.WPDist = self.safe_float(distwpt)
                        self.navData.WPTrack = self.safe_float(brgmag)
                        self.navData.WPLat = self.safe_float(lat)
                        self.navData.WPLon = self.safe_float(lon)

                    case "GPVTG": # GPS Track made good and ground speed, Intentionally omitted KM/H Ground speed
                        coursetrue = msg[1] # GPS Course over ground degrees true xxx.x
                        coursemag = msg[3] # GPS Course over ground degrees magnetic xxx.x
                        gs = msg[5] # GPS Groundspeed, knots xxx.x
                        mode = msg[9] # FAA Mode, explained at top of file
                        self.gpsData.GndSpeed = self.safe_float(gs)
                        self.gpsData.GndTrack = self.safe_float(coursemag)
                    case "GPXTE": # GPS Cross-track error, measured
                        status1 = msg[1] # GPS Status, A = Valid, V = Invalid
                        xtkerror = msg[3] # Cross track distance NM xx.x
                        steerdir = msg[4] # Cross track direction to steer, L/R
                        mode = msg[6] # FAA Mode, explained at top of file
                    case "PGRMZ": # Garmin-proprietary altitude in feet. Pressure altitude, or GPS if unavailable
                        alt = msg[1] # Altitude in feet
                        alttype = msg[3] # 2 if Pressure altitude, 3 if GPS altitude
            return dataship

        except:
            print("NMEA serial exception")
            traceback.print_exc()
            #dataship.errorFoundNeedToExit = True

        return dataship




# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
