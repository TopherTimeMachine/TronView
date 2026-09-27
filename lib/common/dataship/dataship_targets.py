import time
import math
from geographiclib.geodesic import Geodesic
from lib.common.dataship.dataship_gps import GPSData
from lib.common import shared # global shared objects stored here.


# class to store messages received from a target.
# used for meshtastic nodes.
class TargetPayloadMessage(object):
    def __init__(self, from_address: str, from_callsign: str, to_address: str = None, payload: str = None):
        self.address = from_address
        self.callsign = from_callsign
        self.to_address = to_address
        self.payload = payload
        self.time = time.time()

# Target class
class Target(object):
    def __init__(self, callsign):
        self.inputSrcName = None
        self.inputSrcNum = None

        self.callsign = callsign
        self.flightNumber = None # if flight has a flight number then set it here.
        self.faa_db_record = None # faa database record for this target (if found)
        self.source = None
        self.aStat = None
        self.type = None
        self.address = None # icao address of ads-b, or meshtastic node id
        self.cat = None # Emitter Category - one of the following values to describe type/weight of aircraft
        self.buoyNum = None
        # 0 = unknown
        # 1 = Light (ICAO) < 15 500 lbs
        # 2 = Small - 15 500 to 75 000 lbs
        # 3 = Large - 75 000 to 300 000 lbs
        # 4 = High Vortex Large (e.g., aircraft 24 such as B757)
        # 5 = Heavy (ICAO) - > 300 000 lbs
        # 7 = Rotor craft
        # 9 = Glider
        # 10 = lighter then air
        # 11 = sky diver
        # 12 = ultra light
        # 14 = drone Unmanned aerial vehicle
        # 15 = space craft and aliens!
        # 100 = buoy
        # 101 = meshtastic node
        # plus more...
        self.misc = None # 4 bit field
        self.NIC = None # Containment Radius (typically HPL).
        self.NACp = None # encoded using the Estimated Position Uncertainty (typically HFOM).
        # Targets with either a NIC or NACp value that is 4 or lower (HPL >= 1.0 NM, or HFOM >= 0.5 NM) should be depicted using an icon that denotes a degraded target.

        self.lat = None
        self.lon = None
        self.alt = None      # altitude above ground in ft.
        self.track = None  # The resolution is in units of 360/256 degrees (approximately 1.4 degrees).
                        # if misc field tt says track is unknown then track should not be used.
        self.speed = 0 # 0xFFF is reserved to convey that no horizontal velocity information is available.
        self.vspeed = 0 # +/- 32,576 FPM, in units of 64 feet per minute (FPM)
                        # The value 0x800 is reserved to convey that no vertical velocity information is available. The values 0x1FF through 0x7FF and 0x801 through 0xE01 are not used.

        # the following are values that this software calculates per target received.
        self.time = 0        # unix time stamp of time last heard.
        self.dist = None     # distance in miles to target from self.
        self.brng = None     # bearing to target from self
        self.altDiff = None  # difference in alt from self. (in feet MSL)

        # last payload message received from this target.
        self.payload_last: TargetPayloadMessage | None = None

        self.age = 0
        self.meshtastic_node = None

    def get_cat_name(self):
        if self.cat == 1:
            return "Light"
        elif self.cat == 2:
            return "Small"
        elif self.cat == 3:
            return "Large"
        elif self.cat == 4:
            return "High Vortex Large"
        elif self.cat == 5:
            return "Heavy"
        elif self.cat == 7:
            return "Rotor craft"
        elif self.cat == 9:
            return "Glider"
        elif self.cat == 10:
            return "Lighter than air"
        elif self.cat == 11:
            return "Sky diver"
        elif self.cat == 12:
            return "Ultralight"
        elif self.cat == 14:
            return "Drone"
        elif self.cat == 15:
            return "Spacecraft"
        elif self.cat == 100:
            return "Buoy"
        elif self.cat == 101:
            return "Meshtastic Node"
        else:
            return "Unknown"

# def _distance(la1,lo1, la2,lo2):
#     R = 6370 # in KM.
#     lat1 = math.radians(la1)  #insert value
#     lon1 = math.radians(lo1)
#     lon2 = math.radians(lo2)
#     dlon = lon2 - lon1
#     dlat = lat2 - lat1

#     a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
#     c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
#     distance = (R * c) * 0.6213712 # convert to miles.
#     return distance

        

#############################################
## Function: _read_ignore_traffic_beyond_distance
## read [Main] ignore_traffic_beyond_distance from config (statute miles).
## also accepts the old misspelled key "ignore_traffic_beyound_distance" so existing configs keep working.
def _read_ignore_traffic_beyond_distance(default=30):
    from lib import hud_utils
    value = hud_utils.readConfig("Main", "ignore_traffic_beyond_distance", None)
    if value is None:
        value = hud_utils.readConfig("Main", "ignore_traffic_beyound_distance", None)
        if value is not None:
            print("config: 'ignore_traffic_beyound_distance' is misspelled. Please rename it to 'ignore_traffic_beyond_distance'")
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        print(f"config: invalid ignore_traffic_beyond_distance '{value}'. Using {default}")
        return default

#############################################
## Class: TargetData
class TargetData(object):
    def __init__(self):
        self.id = None
        self.name = None

        self.count = 0
        self.src_lat = None     # traffic source lat/lon.. 
        self.src_lon = None
        self.src_alt = None
        self.src_gndtrack = None
        self.src_gndspeed = None
        self.lcl_time_string = ""
        self.src_gps: GPSData | None = None  # if set then use this gps data as the source gps.

        # meshtastic input source (if set then use this meshtastic input source to send messages to targets.)
        from lib.inputs.meshtastic import meshtastic

        self.src_meshtastic_input: meshtastic | None = None

        self.targets: list[Target] = [] # list of targets
        self.buoyCount = 0
        self.selected_target = None

        # messages count (number of input messages received from this source)
        self.msg_count = 0
        self.msg_last = None
        self.msg_bad = 0

        # meshtastic node id (if this is a meshtastic source)
        self.meshtastic_node_num = None
        self.meshtastic_node_id = None
        self.meshtastic_node_name = None
        self.meshtastic_node_device_id = None
        self.meshtastic_node_device_name = None

        # check if we should ignore traffic beyond a certain distance (in statute miles, same as Target.dist). 0 = no limit.
        self.ignore_traffic_beyond_distance = _read_ignore_traffic_beyond_distance()

        # list of target messages
        self.target_payload_messages: list[TargetPayloadMessage] = []

    def add_target_payload_message(self, from_address: str, from_callsign: str, to_address: str, payload: str):
        tPayload = TargetPayloadMessage(from_address, from_callsign, to_address, payload)
        self.target_payload_messages.append(tPayload)
        # only keep the last 10 messages for each callsign.
        self.target_payload_messages = self.target_payload_messages[-10:]
        # check if the callsign is in the list of targets.
        for target in self.targets:
            if target.address == to_address:
                target.payload_last = self.target_payload_messages[-1]
                break
        #print(f"add_target_payload_message: {self.target_payload_messages}")

    def get_target_payload_messages(self, address: str) -> list[TargetPayloadMessage]:
        # get all messages for a given address.
        return [ msg for msg in self.target_payload_messages if msg.address == address ]

    def get_all_messages_as_text(self) -> str:
        # go through self.target_payload_messages and get the last payload message and add it to a list.
        messages = []
        for msg in self.target_payload_messages:
            time_ago = time.time() - msg.time
            messages.append(f"{msg.address}({msg.callsign}): {msg.payload} {time_ago:.0f}s ago")
        return "\n".join(messages)

    def get_last_target_payload_message(self, address: str) -> TargetPayloadMessage | None:
        #print(f"get_last_target_payload_message: {address}")
        messages = self.get_target_payload_messages(address)
        if len(messages) > 0:
            #print(f"get_last_target_payload_message(): {messages[-1]}")
            return messages[-1]
        return None

    def get_selected_target(self) -> Target | None:
        # find the target that has the same address as the selected target.
        for target in self.targets:
            if target.callsign == self.selected_target:
                return target
        return None

    def contains(self, target: Target): # search for callsign
        for x in self.targets:
            if x.address == target.address:
                return True
            if x.callsign == target.callsign:
                return True
        return False

    def remove(self, callsign): # callsign to remove
        for i, t in enumerate(self.targets):
            if t.callsign == callsign:
                del self.targets[i]
                return

    def replace(self,target:Target): # replace target with new one..
        for i, t in enumerate(self.targets):
            if t.address == target.address:
                self.targets[i] = target
                return

    # add or replace a target.
    def addTarget(self, target:Target):
        target.time = int(time.time()) # always update the time when this target was added/updated..

        # check if the target.callsign is set.. if not then set it to the address.
        if target.callsign == None or target.callsign == "":
            if target.address != None and target.address != "":
                target.callsign = str(target.address)
            else:
                target.callsign = "Unknown"

        # if dist&brng was not calculated... check distance and brng to target. if we know our location..
        # use geographiclib to solve this.
        # https://geographiclib.sourceforge.io/1.46/python/code.html#geographiclib.geodesic.Geodesic.Direct
        # use lat/lon from traffic source.

        # check if target does not have a lat/lon.  if so then check if we have that target.address in our list of targets. and use that target's lat/lon.
        if target.lat == None or target.lon == None:
            for t in self.targets:
                if t.address == target.address:
                    target.lat = t.lat
                    target.lon = t.lon
                    break

        if(self.src_gps != None):
            self.src_lat = self.src_gps.Lat
            self.src_lon = self.src_gps.Lon
            self.src_alt = self.src_gps.Alt
            self.src_gndtrack = self.src_gps.GndTrack
            self.src_gndspeed = self.src_gps.GndSpeed

        if(self.src_lat != None and self.src_lon != None and target.lat != None and target.lon != None):
            solve = Geodesic.WGS84.Inverse(self.src_lat,self.src_lon,target.lat,target.lon)
            brng = solve['azi1'] # forward azimuth.
            dist = solve['s12'] * 0.0006213712 # convert to miles.
            #print(f"{target.callsign} dist:{dist} brng:{brng}")
            if(dist!=dist):
                # NaN. no distance found.  
                pass
            elif(dist<500):
                target.dist = round(dist, 3)
                if(brng<0): target.brng = 360 - (abs(brng)) # convert foward azimuth to bearing to.
                elif(brng!=brng):
                    #its NaN.
                    target.brng = None
                else: target.brng = round(brng, 2)

        # target is beyond distance that we want to listen to.. so bye bye baby!
        # don't ignore meshtastic nodes.
        if(target.type != 101):
            if(self.ignore_traffic_beyond_distance != 0):
                if(target.dist == None or target.dist > self.ignore_traffic_beyond_distance):
                    # remove it.
                    if(self.contains(target)):
                        self.remove(target.callsign)
                    self.count = len(self.targets)
                    #print(f"ignoring target: {target.callsign} dist:{target.dist} > ignore_traffic_beyond_distance:{self.ignore_traffic_beyond_distance}")
                    return
            
        # check difference in altitude from self.
        if(target.alt != None):
            if(self.src_alt != None ):  # default to using alt from traffic source...
                target.altDiff = target.alt - self.src_alt
            # elif(aircraft.PALT != None ):
            #     target.altDiff = target.alt - aircraft.PALT
            # elif(aircraft.gps.GPSAlt != None):
            #     target.altDiff = target.alt - aircraft.gps.GPSAlt

        # update the last payload message received from this target.
        target.payload_last = self.get_last_target_payload_message(target.address)

        if(self.contains(target)==False):
            #print(f"Adding target: {target.callsign}")
            self.targets.append(target)
        else:
            #print(f"Replacing target: {target.callsign}")
            self.replace(target)

        self.count = len(self.targets)

    # get nearest target (if any)
    def getNearestTarget(self,lessThenMilage=15) -> Target | None: 
        nearest = None
        for i, t in enumerate(self.targets):
            if(self.targets[i].dist != None and self.targets[i].dist <= lessThenMilage):
                if(nearest != None):
                    if (self.targets[i].dist < nearest.dist):
                        nearest = self.targets[i]
                else:
                    nearest = self.targets[i]
        
        return nearest

    # go through targets, update,  and remove old ones.
    def cleanUp(self,dataship):
        # iterate over a copy. removing items from the list while enumerating it skips targets.
        now = time.time()
        for t in list(self.targets):
            t.age = int(now - t.time) # track age last time this target was updated.
            # check if it's a buoy we dropped.. if so update it.
            if(t.buoyNum != None):
                self.addTarget(t) # update it by adding it again.
            # if old target then remove it...
            if(t.age > 100):
                t.old = True
                self.remove(t.callsign)
        self.count = len(self.targets)

    # clear all buoy targets
    def clearBuoyTargets(self):
        numCleared = 0
        for i, t in enumerate(self.targets):
            if(self.targets[i].buoyNum != None):
                numCleared += 1
                del self.targets[i]
        if(numCleared>0): self.clearBuoyTargets()

    def dropTargetBuoy(self,dataship,name=None,speed=None,direction=None,distance=None,alt=None):
        self.buoyCount += 1
        if(name==None): name = "Buoy"+str(self.buoyCount)
        t = Target(name)
        t.buoyNum  = self.buoyCount
        t.address = self.buoyCount
        t.type = 100 # buoy
        t.cat = 100
        if(direction=="ahead"):
            if(distance!=None): distance = distance * 1609.344 # convert to meters.
            else: distance = 1 * 1609.344 # default to 1 mile. (1609.344 meters)
            # check if we have a gpsData object in the dataship object.
            if(len(dataship.gpsData) > 0):
                solve = Geodesic.WGS84.Direct(dataship.gpsData[0].Lat,dataship.gpsData[0].Lon,dataship.gpsData[0].GndTrack,distance)  
                t.lat = solve['lat2']
                t.lon = solve['lon2']
            else:
                print("no gpsData object in dataship")
                return
        else:
            if(len(dataship.gpsData) > 0):
                t.lat = dataship.gpsData[0].Lat
                t.lon = dataship.gpsData[0].Lon
            else:
                print("no gpsData object in dataship")
                return
            
        # if alt was passed in then add it to the altitude of the aircraft.
        # use the same altitude datum as altDiff is calculated from (traffic source alt) so the buoy is not
        # offset by the difference between pressure and GPS altitude.
        base_alt = self.src_alt if self.src_alt is not None else dataship.gpsData[0].Alt
        if base_alt is None: base_alt = 0
        if(alt != None): t.alt = base_alt + alt
        else: t.alt = base_alt

        # check if mag_head is set.  if not then use the gndTrack from the gpsData object.
        if(len(dataship.imuData) > 0): t.track = dataship.imuData[0].mag_head
        elif(dataship.gpsData[0].GndTrack): t.track = dataship.gpsData[0].GndTrack

        if(speed != None and speed != -1): t.speed = speed
        elif(speed == -1 ):  # if they pass in -1 then use the current speed of aircraft. 
            if(len(dataship.airspeedData) > 0): t.speed = int(dataship.airspeedData[0].IAS)
            elif(dataship.gpsData[0].GndSpeed != None and dataship.gpsData[0].GndSpeed != 0 ): t.speed = int(dataship.gpsData[0].GndSpeed)
            else: t.speed = 0
        else:
            t.speed = 100 # default speed?
        self.addTarget(t)
        pass

    # send a message to a target.
    def sendMsg(self,text:str, target:Target=None):
        # find the target that has the same address as the selected target.
        if target is None:
            # sending to all targets?
            print("sending to all targets..")
        else:
            if self.src_meshtastic_input is not None:
                self.src_meshtastic_input.sendPayloadMsg(text, target)
            else:
                print("no meshtastic input source set")


