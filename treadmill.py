#Gestion du tapis de course
#Calcul du elapsed time de start,stop, pause, resume
#Calul de la distance parcourue, du dénivelé
from time import time
from kivy.logger import Logger
import math
from random import random

def compute_vertical_speed_mh(tilt_degree,belt_speed_kmh):
    return math.sin(math.radians(tilt_degree)) * belt_speed_kmh * 1000

def compute_belt_speed(tilt_degree,vertical_speed_mh):
     #avoid div by 0
    if tilt_degree == 0:
        Logger.warning("Treadmill: compute_belt_speed : tilt is 0, cannot compute belt speed")
        return 0
    return vertical_speed_mh / (math.sin(math.radians(tilt_degree)) * 1000)

#return False if belt_speed_kmh is 0 else return tilt in degrees
def compute_tilt(belt_speed_kmh,vertical_speed_mh) :
    #check for 0 value to avoid divition by 0 in temp
    if belt_speed_kmh == 0:
        Logger.warning("Treadmill: compute_tilt : belt speed is 0, cannot compute tilt")
        return False
    temp = vertical_speed_mh / (belt_speed_kmh*1000)
    #asin(x) x is in the range [-1, 1]
    #no need to check for negative value since speeds are positive
    if temp > 1 or temp < -1:
        Logger.warning("Treadmill: compute_tilt : vertical speed is higher than belt speed, cannot compute tilt, asin > 1")
        return False
    return math.degrees(math.asin(temp))

def add_noise(value, noise_level=0.01):
    noise = noise_level * value * (2 * (0.5 - random()))
    return float(value + noise)


import os
import csv
from datetime import datetime

class TreadmillController:
    # variables
    lift_angle_SP = 0
    lift_angle_PV = 0
    belt_speed_SP = 0
    belt_speed_PV = 0
    vertical_speed_PV = 0
    safeties = {
        "top": True,
        "bottom": True,
        "left": True,
        "right": True,
        "emergency": True
    }
    treadmill_points = {
        'time': 0,
        'speed': 0,
        'incl': 0,
        'asc': 0
    }

    running = False
    paused = False

    def __init__(self, hardware):
        self.hardware = hardware
        self.reset_variables()
        # Event and log features
        self.event_list = []
        self.event_file = None
        self.log_event = False
        self.log_file = None
        self.log_writer = None
        self.log_folder = os.path.join(os.path.dirname(__file__), 'log')
        self.event_folder = os.path.join(os.path.dirname(__file__), 'events')
        os.makedirs(self.log_folder, exist_ok=True)
        os.makedirs(self.event_folder, exist_ok=True)

    def record_event(self, event_name=None):
        """Record an event with the current elapsed time and optional name."""
        event = {'time': self.elapsed_time, 'event': event_name, 'lift_angle_PV': self.lift_angle_PV, 'belt_speed_PV': self.belt_speed_PV, 'vertical_speed_PV': self.vertical_speed_PV}
        # Append to in-memory list
        self.event_list.append(event)
        #toggle log event
        self.log_event = True
        # Write to event file if open
        if self.event_file:
            writer = csv.DictWriter(self.event_file, fieldnames=['time','lift_angle_PV','belt_speed_PV','vertical_speed_PV','event'])
            writer.writerow(event)
            self.event_file.flush()

    def _open_event_file(self):
        now = datetime.now().strftime('%Y-%m-%d-%H%M%S')
        event_path = os.path.join(self.event_folder, f'{now}-events.csv')
        self.event_file = open(event_path, 'w', newline='')
        writer = csv.DictWriter(self.event_file, fieldnames=['time','lift_angle_PV','belt_speed_PV','vertical_speed_PV','event'])
        writer.writeheader()
        self.event_file.flush()

    def _close_event_file(self):
        if self.event_file:
            self.event_file.close()
            self.event_file = None

    def _open_log_file(self):
        now = datetime.now().strftime('%Y-%m-%d-%H%M%S')
        log_path = os.path.join(self.log_folder, f'{now}-log.csv')
        self.log_file = open(log_path, 'w', newline='')
        self.log_writer = csv.DictWriter(self.log_file, fieldnames=[
            'time', 'belt_speed_SP', 'belt_speed_PV', 'lift_angle_SP', 'lift_angle_PV', 'vertical_speed_SP', 'vertical_speed_PV', 'distance_m', 'elevation_m', 'event'
        ])
        self.log_writer.writeheader()
        self.log_file.flush()

    def _close_log_file(self):
        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.log_writer = None

    def reset_variables(self):
        self.distance_m = 0
        self.elevation_m = 0
        self.elapsed_time = 0
        self.start_time = 0
        self.pause_time = 0
        self.elapsed_pause_time = 0
        self.last_update_time = 0
        self.treadmill_points = []
        self.event_list = []

    def update(self):
        #update PV
        if self.hardware:
            self.lift_angle_PV = self.hardware.get_lift_angle()
            self.belt_speed_PV = self.hardware.get_belt_speed()
            self.safeties = self.hardware.get_safeties()

        #When there is no hardware : PV set to setpoint and 1% of random noise
        else:
            self.lift_angle_PV = add_noise(self.lift_angle_SP, noise_level=0.001)
            if self.running and not self.paused:
                #simulate acceleration
                step = 0.2
                if self.belt_speed_PV < self.belt_speed_SP:
                    self.belt_speed_PV += min(step, self.belt_speed_SP - self.belt_speed_PV)
                elif self.belt_speed_PV > self.belt_speed_SP:
                    self.belt_speed_PV -= min(step, self.belt_speed_PV - self.belt_speed_SP)
                self.belt_speed_PV = add_noise(self.belt_speed_PV)
            else:
                self.belt_speed_PV = 0
        #compute vertical speed
        self.vertical_speed_PV = compute_vertical_speed_mh(self.lift_angle_PV,self.belt_speed_PV)
        #store treadmill points
        self.treadmill_points.append({
            'time': self.elapsed_time,
            'speed': self.belt_speed_PV,
            'incl': self.lift_angle_PV,
            'asc': self.vertical_speed_PV
        })


        #update running value
        if self.running and not self.paused:
            #update elapsed time
            current_time = time()
            self.elapsed_time = current_time - self.start_time - self.elapsed_pause_time
            #compute distance and elevation
            delta_time = current_time - self.last_update_time
            if delta_time > 0:
                self.distance_m += (self.belt_speed_PV * 1000 / 3600) * delta_time
                self.elevation_m += (self.vertical_speed_PV / 3600) * delta_time
            self.last_update_time = current_time
            
            # Log to file if running
            if self.log_writer:
                #add event string only if there was an event
                if self.log_event:
                    event_str = self.event_list[-1]['event'] if self.event_list else ''
                    self.log_event = False
                else:
                    event_str = ''
                
                self.log_writer.writerow({
                    'time': self.elapsed_time,
                    'belt_speed_SP': self.belt_speed_SP,
                    'belt_speed_PV': self.belt_speed_PV,
                    'lift_angle_SP': self.lift_angle_SP,
                    'lift_angle_PV': self.lift_angle_PV,
                    'vertical_speed_SP': compute_vertical_speed_mh(self.lift_angle_SP, self.belt_speed_SP),
                    'vertical_speed_PV': self.vertical_speed_PV,
                    'distance_m': self.distance_m,
                    'elevation_m': self.elevation_m,
                    'event': event_str
                })
                self.log_file.flush()
            
        #return a dict with all relevant data
        return {
            "lift_angle_PV": self.lift_angle_PV,
            "belt_speed_PV": self.belt_speed_PV,
            "vertical_speed_PV": self.vertical_speed_PV,
            "lift_angle_SP": float(self.lift_angle_SP),
            "belt_speed_SP": float(self.belt_speed_SP),
            "vertical_speed_SP": float(compute_vertical_speed_mh(self.lift_angle_SP,self.belt_speed_SP)),
            "safeties": self.safeties,
            "distance_m": self.distance_m,
            "elevation_m": self.elevation_m,
            "elapsed_time": self.elapsed_time
        }

    def start(self):
        if not self.running:
            self.running = True
            self.reset_variables()
            self.start_time = self.last_update_time = time()
            if self.hardware:
                self.hardware.start_belt()
            Logger.info(f"Treadmill: Starting at {self.start_time}")
            # Open log and event files
            self._open_log_file()
            self._open_event_file()
            # Write initial event
            self.record_event('start')
        if self.paused:
            self.paused = False
            self.last_update_time = time()
            self.elapsed_pause_time += time() - self.pause_time
            if self.hardware:
                self.hardware.start_belt()
            Logger.info(f"Treadmill: Resumed at {time()}")
            #Write resume event
            self.record_event('resume')

    def pause(self):
        if self.running:
            self.paused = True
            self.pause_time = time()
            if self.hardware:
                self.hardware.stop_belt()
            Logger.info(f"Treadmill: Paused at {self.pause_time}")
            self.record_event('pause')

    def stop(self):
        self.running = False
        self.paused = False
        if self.hardware:
            self.hardware.stop_belt()
        Logger.info(f"Treadmill: Stopped at {time()}")
        self.record_event('stop')
        self._close_log_file()
        self._close_event_file()

    #setpoint functions
    def set_lift_angle(self, angle):
        self.lift_angle_SP = angle
        if self.hardware:   self.hardware.set_lift_angle(angle)
        Logger.info(f"Treadmill: Set angle to {angle}")

    def set_belt_speed(self, speed):
        self.belt_speed_SP = speed
        if self.hardware:   self.hardware.set_belt_speed(speed)
        Logger.info(f"Treadmill: Set belt speed to {speed}")

    #All get functions return the current setpoint or process variable if there is no treadmill attached
    #Caution to self.update() before calling getter
    def get_lift_angle(self):
        return self.lift_angle_PV

    def get_belt_speed(self):
        return self.belt_speed_PV
    
    def get_vertical_speed(self):
        return self.vertical_speed_PV

    def get_safeties(self):
        if self.hardware:
            return self.safeties
        return None

    #return running status
    def get_distance(self):
        return self.distance_m

    def get_elevation(self):
        return self.elevation_m

    def get_elapsed_time(self):
        return self.elapsed_time
    
    #return treadmill points
    def get_treadmill_points(self):
        return self.treadmill_points
    
    def is_running(self):
        return self.running and not self.paused
    def is_paused(self):
        return self.paused
    
    #shutdown function
    def shutdown(self):
        if self.hardware:
            self.hardware.stop_all()
            self.hardware.set_belt_speed(0)
        Logger.info(f"Treadmill: Shutdown at {time()}")
