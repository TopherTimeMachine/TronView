#!/usr/bin/env python

# wifi udp input source
# Stratux UDP
# 1/23/2019 Topher
# 11/4/2024 - Adding debug, and working on AHRS message parsing. 
# 11/6/2024  Added IMU data.
# 1/3/2025  Added dataship refacor
# 2/9/2025  Added gpsData object to the module.

import struct
import binascii
import time
import socket
import re
import traceback
import time
import math
from geographiclib.geodesic import Geodesic
import datetime
import select
from ..common.dataship.dataship import Dataship
from ..common.dataship.dataship_imu import IMUData
from ..common.dataship.dataship_gps import GPSData
from ..common.dataship.dataship_air import AirData
from ..common.dataship.dataship_targets import TargetData, Target
from ._input import Input
from ..common import shared
from . import _input_file_utils
import sqlite3
import os
from ..common.helpers.faa_aircraft_database import find_aircraft_by_n_number, FAA_Aircraft, check_commercial_name

class stratux_wifi(Input):
    def __init__(self):
        self.name = "stratux"
        self.version = 1.0
        self.inputtype = "network"
        self.PlayFile = None
        self.imu_index = 0
        self.imuData = None
        self.gps_index = 0
        self.gpsData = None
        self.airdata_index = 0
        self.airData = None
        self.targetData_index = 0
        self.targetData = None
        self.dataship = None
        self.address_map = {} # Map ICAO address to {'n_number': str, 'flight_number': str | None}

    def initInput(self, num, dataship: Dataship):
        Input.initInput( self,num, dataship )  # call parent init Input.
        self.output_logBinary = True
        self.dataship = dataship

        if(self.PlayFile!=None and self.PlayFile!=False):
            # if in playback mode then load example data file.
            # get file to read from config.  else default to..
            if self.PlayFile==True:
                defaultTo = "stratux_9.dat"
                self.PlayFile = "../data/stratux/"+defaultTo
            self.ser,self.input_logFileName = Input.openLogFile(self,self.PlayFile,"rb")
            self.isPlaybackMode = True
        else:
            self.udpport = _input_file_utils.readConfigInt(self.name, "udpport", "4000")
            # levil bom using port 43211

            # open udp connection.
            self.ser = socket.socket(socket.AF_INET, #Internet
                                    socket.SOCK_DGRAM) #UDP
                             
            #Bind to any available address on port *portNum*
            print("using UDP port:"+str(self.udpport))
            self.ser.bind(("",self.udpport))
            
            #Prevent the socket from blocking until it receives all the data it wants
            #Note: Instead of blocking, it will throw a socket.error exception if it
            #doesn't get any data
            #self.ser.settimeout(.1)
            self.ser.setblocking(0)

        # if this input is not the first input then don't default to read the ahrs input.
        if(num==0): 
            defaultUseAHRS = True
        else: 
            defaultUseAHRS = False
        self.use_ahrs = _input_file_utils.readConfigBool("Stratux", "use_ahrs", defaultUseAHRS)
        if(self.use_ahrs==False):
            print("Skipping AHRS data from Stratux")

        # create a empty imu object.
        self.imuData = IMUData()
        self.imuData.id = "stratux_imu"
        self.imuData.name = self.name
        self.imu_index = len(dataship.imuData)  # Start at 0
        print("new stratux imu "+str(self.imu_index)+": "+str(self.imuData))
        dataship.imuData.append(self.imuData)
        self.last_read_time = time.time()

        # create a empty gps object.
        self.gpsData = GPSData()
        self.gpsData.id = "stratux_gps"
        self.gpsData.inputSrcName = "stratux"
        self.gpsData.name = self.name
        self.gps_index = len(dataship.gpsData)  # Start at 0
        print("new stratux gps "+str(self.gps_index)+": "+str(self.gpsData))
        dataship.gpsData.append(self.gpsData)

        # create a empty aircraft object.
        self.airData = AirData()
        self.airData.id = "stratux_aircraft"
        self.airData.name = self.name
        self.airdata_index = len(dataship.airData)  # Start at 0
        print("new stratux airData "+str(self.airdata_index)+": "+str(self.airData))
        dataship.airData.append(self.airData)

        # create a empty targets object.
        self.targetData = TargetData()
        self.targetData.id = "stratux_targets"
        self.targetData.source = "stratux"
        self.targetData.name = self.name
        self.targetData_index = len(dataship.targetData)  # Start at 0
        print("new stratux targets "+str(self.targetData_index)+": "+str(self.targetData))
        dataship.targetData.append(self.targetData)


    def closeInput(self,aircraft):
        if self.isPlaybackMode:
            self.ser.close()
        else:
            self.ser.close()

    def getNextFileChunck(self,aircraft):
        x = 0
        while x != 126: # read until ~
            t = self.ser.read(1)
            if len(t) != 0:
                x = ord(t)
                #print(str(x), end ="." )
            else:
                self.ser.seek(0)
                print("Stratux file reset")

        #print("first ~", end ="." )
        x = 0
        data = bytearray(b"~")
        while x != 126: # read until ~
            t = self.ser.read(1)
            if len(t) != 0:
                x = ord(t)
                data.extend(t)
                #print(str(x), end ="." )
            else:
                self.ser.seek(0)
                print("Stratux file reset")
        #print("end ~", end ="." )
        return data
        
        #data = self.ser.read(80)
        #if(len(data)==0): 
        #    self.ser.seek(0)
        #    print("Replaying file: "+self.input_logFileName)
        #TODO: read to the next ~ in the file??
        #print(type(data))
        #return data

    #############################################
    ## Function: readMessage
    def readMessage(self, dataship: Dataship):
        if self.shouldExit == True: dataship.errorFoundNeedToExit = True
        if dataship.errorFoundNeedToExit: return dataship
        if self.skipReadInput == True: return dataship

        msg = bytes(0)
        if self.isPlaybackMode:
            # Playback mode: Read next chunk from file
            msg = self.getNextFileChunck(dataship)
        else:
            # Live mode: Wait for data on UDP socket
            readable, _, _ = select.select([self.ser], [], [], 0.1) # Timeout 0.1s
            if self.ser in readable:
                try:
                    #Attempt to receive up to 1024 bytes of data
                    data, addr = self.ser.recvfrom(1024)
                    msg = data
                except socket.timeout:
                    pass # Should not happen with select, but good practice
                except socket.error as e:
                    # If no data is received, you get here, but it's not an error
                    # Ignore and continue
                    print(f"Stratux socket error on recvfrom: {e}") # Log error for debugging
                    pass

        if(len(msg)==0):
            return dataship
        #count = msg.count(b'~~')
        #print("-----------------------------------------------\nNEW Chunk len:" + str(len(msg)) + " seperator count:" + str(count))
        if(dataship.debug_mode>1):
            if len(msg) >= 4:
                print("stratux: "+str(msg[1])+" "+str(msg[2])+" "+str(msg[3])+" "+str(len(msg))+" "+str(msg))
            else:
                print("stratux: BAD? "+str(len(msg))+" "+str(msg))
            

        for line in msg.split(b'~~'):
            theLen = len(line)
            if(theLen>3):
                if(line[0]!=126): # if no ~ then add one...
                    newline = b''.join([b'~',line])
                    theLen += 1
                else:
                    newline = line
                if(newline[theLen-1]!=126): # add ~ on the end if not there.
                    newline = b''.join([newline,b'~'])
                dataship = self.processSingleMessage(newline,dataship)

                if self.output_logFile != None:
                    Input.addToLog(self,self.output_logFile,newline)

        return dataship

    #############################################
    def processSingleMessage(self, msg, dataship):
        try:
            
            if(len(msg)<1):
                pass
            elif(msg[0]==126 and msg[1]==ord('L') and msg[2]==ord('E')):  # Check for Levil specific messages ~LE
                #print(msg)
                #print("Len:"+str(len(msg)))
                #if(dataship.debug_mode>0):
                #    print("Message ID "+format(msg[3]));

                if(msg[3]==0): # status message
                    #print(msg)
                    #print("status message len:"+str(len(msg)))
                    # B          B     H     B    B   
                    FirmwareVer, Batt, Error,WAAS,Aux = struct.unpack(">BBHBB",msg[5:11])
                    self.FirmwareVer = FirmwareVer
                    self.Battery = Batt
                    if(msg[4]==2):
                        if(WAAS==1):
                            self.gpsData.GPSWAAS = True
                        else:
                            self.gpsData.GPSWAAS = False

                elif(msg[3]==1): # ahrs and air data.
                    if(dataship.debug_mode>2):
                        print("ahrs levil :"+str(len(msg))+" "+str(msg[len(msg)-1]))
                    if(len(msg)==28):
                        # //###########################################################################################################################
                        # //                 Stratux AHRS message
                        # //  -------------------------------------------------------------------------------------------------------------------------
                        # //  BOM  |ID/TYP|resvd|roll  |  pitch  |   hdg   |slip |  yaw    |  G's | airspd  | palt   | vspd    | resvd   | chksm | EOM  
                        # //  -------------------------------------------------------------------------------------------------------------------------                   
                        # //  [126, 76, 69, 1, 1, 0, 0, 255, 255, 127, 255, 0, 0, 127, 255, 0, 10, 127, 255, 24, 162, 255, 255, 127, 255, 42, 249, 126]
                        # //############################################################################################################################

                        # h   h     h   h      h         h,    h   H        h     B   B
                        Roll,Pitch,Yaw,Inclin,TurnCoord,GLoad,ias,pressAlt,vSpeed,AOA,OAT = struct.unpack(">hhhhhhhHhBB",msg[5:25]) 

                        # Update IMU data
                        roll = None if Roll == 32767 else Roll / 10
                        pitch = None if Pitch == 32767 else Pitch / 10
                        yaw = None if Yaw == 32767 else Yaw / 10
                        self.imuData.updatePos(pitch, roll, yaw)

                        self.imuData.Slip_Skid = None if TurnCoord == 32767 else TurnCoord / 100
                        self.imuData.Vert_G = None if GLoad == 32767 else GLoad / 10

                        if dataship.debug_mode > 0:
                            current_time = time.time() # calculate hz.
                            self.imuData.hz = round(1 / (current_time - self.last_read_time), 1)
                            self.last_read_time = current_time

                        if(ias != 32767):
                            self.airData.IAS = int(round(ias * 1.15078)) # if ias is 32767 then no airspeed given? (knots -> mph, dataship units are mph)
                            self.airData.Alt_pres = pressAlt -5000 # 5000 is sea level.
                            self.airData.VSI = vSpeed # ft/min

                        if(msg[4]==2): # if version is 2 then read AOA and OAT
                            self.airData.AOA = AOA
                            self.airData.OAT = OAT

                        self.imuData.msg_count += 1

                    else:
                        self.imuData.msg_bad +=1
                        #aircraft.msg_len = len(msg)

                elif(msg[3]==2): # more metrics.. 
                    #print("additonal metrics message len:"+str(len(msg)))
                    AOA,OAT = struct.unpack(">BB",msg[5:7]) 
                    self.airData.AOA = AOA
                    self.airData.OAT = OAT

                elif(msg[3]==7): # WAAS status
                    #print("additonal metrics message len:"+str(len(msg)))
                    WAASstatus, Sats, Power, OutRate = struct.unpack(">BBHB",msg[5:10]) 
                    self.gpsData.SatsTracked = Sats
                    self.gpsData.msg_count += 1
                    self.gpsData.GPSWAAS = WAASstatus

                    if(dataship.debug_mode>1):
                        print(f"stratux GPS status: {WAASstatus} Sats:{Sats} Power:{Power} OutRate:{OutRate}")

                else:
                    #print("unkown message id:"+str(msg[3])+" len:"+str(len(msg)))
                    #print(msg)
                    self.imuData.msg_unknown += 1 #else unknown message.
                    
                if self.isPlaybackMode:  #if playback mode then add a delay.  Else reading a file is way to fast.
                    time.sleep(.02)
                    pass
                else:
                    #else reading realtime data via udp connection
                    pass


            else:
                #print("GDL 90 message id:"+str(msg[1])+" "+str(msg[2])+" "+str(msg[3])+" len:"+str(len(msg)))
                #print(msg.hex())
                #aircraft.msg_bad += 1 #bad message found.
                if(msg[1]==0): # GDL heart beat. 
                    #print("GDL 90 HeartBeat message id:"+str(msg[1])+" len:"+str(len(msg)))
                    if(len(msg)==11):
                        statusByte2 = msg[3]
                        timeStamp = _unsigned16(msg[4:], littleEndian=True)
                        if (statusByte2 & 0b10000000) != 0:
                            timeStamp += (1 << 16)
                        self.gpsData.GPSTime_string = str(datetime.timedelta(seconds=int(timeStamp)))   # get time stamp for gdl hearbeat.
                        timeObj = datetime.datetime.strptime(self.gpsData.GPSTime_string, "%H:%M:%S")
                        self.gpsData.GPSDate_string = datetime.datetime.now().strftime("%m/%d/%y")
                        self.gpsData.GPSTime = timeObj.time

                elif(msg[1]==10): # GDL ownership (Latitude, Longitude, Altitude, Speed, Heading)
                    '''
                    The GDL 90 will always output an Ownship Report message once per second. The message
                    uses the same format as the Traffic Report, with the Message ID set to the value 10

                    The Ownship Report is output by the GDL 90 regardless of whether a valid GPS position fix is
                    available. If the ownship GPS position fix is invalid, the Latitude, Longitude, and NIC fields in
                    the Ownship Report all have the ZERO value.
                    Ownship geometric altitude is provided in a separate message (SW Mod C).

                    Traffic Report data = st aa aa aa ll ll ll nn nn nn dd dm ia hh hv vv tt ee cc cc cc cc cc cc cc cc px
                    Field Definition:
                    s Traffic Alert Status. s = 1 indicates that a Traffic Alert is active for this target.
                    t Address Type: Describes the type of address conveyed in the Participant Address field:
                    aa aa aa Participant Address (24 bits).
                    ll ll ll Latitude: 24-bit signed binary fraction. Resolution = 180 / 223 degrees.
                    nn nn nn Longitude: 24-bit signed binary fraction. Resolution = 180 / 223 degrees.
                    ddd Altitude: 12-bit offset integer. Resolution = 25 feet. Altitude (ft) = ("ddd" * 25) - 1,000
                    m Miscellaneous indicators: (see text)
                    i Navigation Integrity Category (NIC):
                    a Navigation Accuracy Category for Position (NACp):
                    hhh Horizontal velocity. Resolution = 1 kt.
                    vvv Vertical Velocity: Signed integer in units of 64 fpm.
                    tt Track/Heading: 8-bit angular weighted binary. Resolution = 360/256 degrees. 0 = North, 128 = South. See Miscellaneous field for Track/Heading indication.
                    ee Emitter Category
                    cc cc cc cc
                    cc cc cc cc Call Sign: 8 ASCII characters, '0' through '9' and 'A' through 'Z'.
                    p Emergency/Priority Code:
                    x Spare (reserved for future use)
                    
                    '''
                    #print("GDL 90 owership id:"+str(msg[1])+" len:"+str(len(msg)))
                    if(len(msg)==32):

                        # save gps data coming from traffic source..
                        latLongIncrement = 180.0 / (2**23) # == 0.0000001490116119384765625
                        src_lat = _signed24(msg[6:]) * latLongIncrement
                        src_lon = _signed24(msg[9:]) * latLongIncrement
                        # Ownship report altitude is PRESSURE altitude (same datum as traffic report altitudes).
                        # Geometric (GPS) altitude comes separately in message 11.
                        alt = _thunkByte(msg[12], 0xff, 4) + _thunkByte(msg[13], 0xf0, -4)
                        src_alt = None if alt == 0xFFF else (alt * 25) - 1000 # 0xFFF = invalid

                        self.gpsData.set_gps_location(src_lat, src_lon, self.gpsData.Alt) # keep geometric alt from msg 11
                        self.gpsData.AltPressure = src_alt

                        # set source lat/lon/alt. this is what is used to calculate distance and altitude difference to target.
                        # uses pressure altitude so altDiff compares the same datum as the traffic altitudes.
                        self.targetData.src_lat = src_lat
                        self.targetData.src_lon = src_lon
                        self.targetData.src_alt = src_alt

                        horzVelo = _thunkByte(msg[15], 0xff, 4) + _thunkByte(msg[16], 0xf0, -4)
                        if horzVelo == 0xfff:  # no info available
                            self.gpsData.GndSpeed = None
                        else:
                            self.gpsData.GndSpeed = int(round(horzVelo * 1.15078)) # knots -> mph (dataship ground speed is mph)

                        if(msg[18] != 255):
                            self.gpsData.GndTrack = int(msg[18] * 1.40625)  # track/heading, 0-358.6 degrees
                        else:
                            self.gpsData.GndTrack = None

                        # get NIC
                        self.gpsData.Accuracy = _thunkByte(msg[14], 0xf0, -4)

                        self.gpsData.msg_count += 1

                        if(dataship.debug_mode>1):
                            print(f"stratux GPS Data: {self.gpsData.GPSTime_string} {self.gpsData.Lat} {self.gpsData.Lon} {self.gpsData.GndSpeed} {self.gpsData.GndTrack}")


                elif(msg[1]==11): # GDL OwnershipGeometricAltitude
                    # geometric (GPS) altitude. resolution 5 ft.
                    self.gpsData.Alt = _signed16(msg[2:]) * 5
                    if(dataship.debug_mode>1):
                        print(f"stratux GPS Geometric Altitude: {self.gpsData.Alt}ft")

                elif(msg[1]==20): # Traffic report
                    '''
                    The Traffic Report data consists of 27 bytes of binary data as shown in Figure 2. Each field that
                    makes up the report is a multiple of 4 bits. Each lower case character represents a 4-bit value.
                    Each pair of lower-case characters represents a single byte value.
                    For example, Byte 2 of this message is the first byte of the Traffic Report data, and contains the
                    value "0xst", where "s" represents the Traffic Alert Status and occupies Byte 2 bits 7..4, and 't'
                    represents the Address Type and occupies Byte 2 bits 3..0. Similarly, Byte 28 contains the value
                    "0xpx".
                    '''
                    #if(dataship.debug_mode>0):
                    #    print("GDL 90 Traffic message id:"+str(msg[1])+" len:"+str(len(msg)))
                    if(len(msg)==32): 
                        #print(msg.hex())

                        callsign = re.sub(r'[^A-Za-z0-9]+', '', msg[20:28].rstrip().decode('ascii', errors='ignore') ) # clean the N number.
                        targetStatus = _thunkByte(msg[2], 0x0b11110000, -4) # status
                        targetType = _thunkByte(msg[2], 0b00001111) # type
                        address =  (msg[3] << 16) + (msg[4] << 8) + msg[5] # address

                        # --- Logic to handle N-Number vs Flight Number ---
                        n_number, flight_number, faa_db_record = self._get_n_number_and_flight_number(address, callsign)
                        # --- End N-Number/Flight Number Logic ---

                        target = Target(n_number) # Use N-Number as the primary identifier
                        target.flightNumber = flight_number # Set the flight number attribute (needs adding to Target class)
                        target.faa_db_record = faa_db_record

                        target.aStat = targetStatus
                        target.type = targetType
                        target.address = address # Store the address in the target object as well

                        # get lat/lon
                        latLongIncrement = 180.0 / (2**23)
                        target.lat = _signed24(msg[6:]) * latLongIncrement
                        target.lon = _signed24(msg[9:]) * latLongIncrement
                        # alt of target.
                        alt_raw = _thunkByte(msg[12], 0xff, 4) + _thunkByte(msg[13], 0xf0, -4)
                        if alt_raw == 0xFFF: # 4095 indicates invalid/unavailable altitude
                            target.alt = None
                        else:
                            target.alt = (alt_raw * 25) - 1000 # alt in feet MSL (from GDL90 format)


                        target.misc = _thunkByte(msg[13], 0x0f) # misc bits 3..0. Bit 3 is VRSI (0=Baro, 1=GNSS)
                        target.NIC = _thunkByte(msg[14], 0xf0, -4) # NIC bits 7..4
                        target.NACp = _thunkByte(msg[14], 0x0f) # NACp bits 3..0

                        #speed (Horizontal Velocity)
                        horzVelo = _thunkByte(msg[15], 0xff, 4) + _thunkByte(msg[16], 0xf0, -4)
                        if horzVelo == 0xfff:  # 4095 indicates no hvelocity info available
                            target.speed = None
                        else:
                            target.speed = int(round(horzVelo * 1.15078)) # knots -> mph (Target.speed is mph)

                        # heading/track
                        heading_raw = msg[18]
                        if heading_raw == 0xFF: # 255 indicates unavailable
                            target.track = None
                        else:
                            trackIncrement = 360.0 / 256
                            target.track = int(heading_raw * trackIncrement)  # track/heading, 0-358.6 degrees

                        # Vertical Velocity (Rate) - GDL90 Sign/Magnitude format
                        # Combined 12 bits: msg[16] bits 3..0 and msg[17] bits 7..0
                        vertVeloRaw = (_thunkByte(msg[16], 0x0f) << 8) + msg[17]
                        # Sign bit: msg[16] bit 3 (0x08)
                        sign_bit = _thunkByte(msg[16], 0x08) >> 3 # 0 = up/increasing, 1 = down/decreasing

                        magnitude = vertVeloRaw & 0x07FF # Mask out sign bit (which is bit 11 of 12-bit value)

                        if magnitude == 0:
                            target.vspeed = 0 # No vertical rate reported
                        elif magnitude == 0x7FF: # 2047 indicates > +/- 32192 fpm
                            target.vspeed = 32767 if sign_bit == 0 else -32767 # Indicate exceeding limit
                        else:
                            vertVelo = magnitude * 64 # Vertical velocity in fpm
                            if sign_bit == 1: # Downward/decreasing rate is negative
                                vertVelo = -vertVelo
                            target.vspeed = vertVelo

                        # Old vertical speed logic based on comments/possible misinterpretation removed


                        target.cat = int(msg[19]) # emitter category (type/size of aircraft)

                        self.targetData.addTarget(target) # add/update target to traffic list.
                        if(dataship.debug_mode>1):
                            # Updated print statement to include flight number if available and format address as Hex
                            flight_info = f" Flight: {target.flightNumber}" if target.flightNumber else ""
                            addr_hex = f"{target.address:X}"
                            alt_str = f"{target.alt}" if target.alt is not None else "N/A"
                            spd_str = f"{target.speed}" if target.speed is not None else "N/A"
                            trk_str = f"{target.track}" if target.track is not None else "N/A"
                            vs_str = f"{target.vspeed}" if target.vspeed is not None else "N/A"
                            print(f"GDL 90 Target: {target.callsign} ({addr_hex}) Type:{target.type}{flight_info} Loc:({target.lat:.4f}, {target.lon:.4f}) Alt:{alt_str} Spd:{spd_str} Trk:{trk_str} VS:{vs_str}")

                        self.targetData.msg_count += 1
                    else:
                        self.targetData.msg_bad += 1

                elif(msg[1]==101): # Foreflight id?
                    pass
                
                else: # unknown message id
                    if(self.dataship.debug_mode>1):
                        print("stratuxmessage unkown id:"+str(msg[1])+" "+str(msg[2])+" "+str(msg[3])+" len:"+str(len(msg)))
                    pass

                # if(self.textMode_showRaw==True): 
                #     dataship.gdl_msg_last = binascii.hexlify(msg) # save last message.
                #     msgNum = int(msg[1])
                #     if(msgNum!=20 and msgNum != 10 and msgNum != 11 and msgNum != 83):
                #         dataship.gdl_msg_last_id = " "+str(msgNum)+" "



            return dataship
        except ValueError as e :
            print("stratux value error exception")
            dataship.errorFoundNeedToExit = True
            print(e)
            print(traceback.format_exc())
        except struct.error:
            #error with read in length.. ignore for now?
            print("stratux: Error with read in length")
            pass
        except Exception as e:
            dataship.errorFoundNeedToExit = True
            print(e)
            print(traceback.format_exc())
        return dataship

    def _get_n_number_and_flight_number(self, address, callsign):
        """Determines the N-Number and Flight Number based on the address map.
           This is cause the stratux always sends the N-Number when it first sees a new address.
           Then later it will send the flight number if it is available.

        Args:
            address (int): The ICAO 24-bit address.
            callsign (str): The callsign from the current message.

        Returns:
            tuple: (n_number, flight_number)
        """
        n_number = None
        flight_number = None
        faa_db_record = None

        if address in self.address_map:
            # Address seen before
            stored_n_number = self.address_map[address]['n_number']
            stored_flight_number = self.address_map[address].get('flight_number') # Get potentially existing flight number
            self.address_map[address]['last_seen'] = time.time() # Update last seen time

            # Always return the originally stored N-Number
            n_number = stored_n_number
            faa_db_record = self.address_map[address]['faa_db_record']

            if callsign and callsign != stored_n_number and callsign != stored_flight_number:
                #print(f"Flight number changed: old {stored_n_number} new {callsign} flight number: {stored_flight_number} address: {address}")
                # Current non-empty callsign is different from the stored N-Number.
                # Assume this is the flight number.
                flight_number = callsign
                # Update map with the newly found flight number
                self.address_map[address]['flight_number'] = flight_number

                # check FAA database for matching aircraft because the N-Number has changed
                matching_aircraft = find_aircraft_by_n_number(n_number)
                if matching_aircraft:
                    # check if the flight number is a commercial name
                    commercial_name = check_commercial_name(flight_number)
                    #print(f"Commercial name: {commercial_name}")
                    if commercial_name:
                        matching_aircraft.commerical_name = commercial_name

                    self.address_map[address]['faa_db_record'] = matching_aircraft
                else:
                    self.address_map[address]['faa_db_record'] = None

            else:
                # Callsign is the same as N-Number, empty, or hasn't changed to reveal a flight number yet.
                # Keep the previously stored flight number (if any), otherwise it remains None.
                flight_number = stored_flight_number
                # don't search FAA database cause it's time consuming and we already did when we first found the N-Number.

        else:
            # First time seeing this address
            # Assume this non-empty callsign is the N-Number
            n_number = callsign

            # No flight number known yet for this new address
            flight_number = None
            # Store the initial N-Number and last_seen time in the map
            foundNew = {'n_number': n_number, 'flight_number': None, 'last_seen': time.time()}
            # Search for matching aircraft using N-Number
            faa_db_record = find_aircraft_by_n_number(n_number)
            if faa_db_record:
                #print(f"Found {n_number}: {faa_db_record.aircraft_desc_mfr} {faa_db_record.aircraft_desc_model}")
                foundNew['faa_db_record'] = faa_db_record
            else:
                #print(f"No matching aircraft found for {n_number}")
                foundNew['faa_db_record'] = None

            self.address_map[address] = foundNew


        return n_number, flight_number, faa_db_record


def _unsigned24(data, littleEndian=False):
    """return a 24-bit unsigned integer with selectable Endian"""
    #if(len(data) >= 3): raise Exception("_unsigned24 len(data) >= 3")
    if(len(data)<3): return 0
    if littleEndian:
        b0 = data[2]
        b1 = data[1]
        b2 = data[0]
    else:
        b0 = data[0]
        b1 = data[1]
        b2 = data[2]
    
    val = (b0 << 16) + (b1 << 8) + b2
    return val


def _signed24(data, littleEndian=False):
    """return a 24-bit signed integer with selectable Endian"""
    val = _unsigned24(data, littleEndian)
    if val > 8388607:
        val -= 16777216
    return val


def _unsigned16(data, littleEndian=False):
    """return a 16-bit unsigned integer with selectable Endian"""
    #if(len(data) >= 2): raise Exception("_unsigned16 len(data) >= 2")
    if(len(data)<2): return 0
    if littleEndian:
        b0 = data[1]
        b1 = data[0]
    else:
        b0 = data[0]
        b1 = data[1]
    
    val = (b0 << 8) + b1
    return val


def _signed16(data, littleEndian=False):
    """return a 16-bit signed integer with selectable Endian"""
    val = _unsigned16(data, littleEndian)
    if val > 32767:
        val -= 65536
    return val

def _thunkByte(c, mask=0xff, shift=0):
    """extract an integer from a byte applying a mask and a bit shift
    @c character byte
    @mask the AND mask to get the desired bits
    @shift negative to shift right, positive to shift left, zero for no shift
    """
    val = c & mask
    if shift < 0:
        val = val >> abs(shift)
    elif shift > 0:
        val = val << shift
    return val

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
