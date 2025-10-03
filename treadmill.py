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
import queue
import threading
from time import sleep
import collections
import yaml
from pathlib import Path

#READ CONFIGURATION FILE
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def read_yaml(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

#Read config dictionary in current folder
file = Path(__file__)
config = read_yaml(file.parent/'treadmill.yaml')


class TreadmillController:
    # variables
    lift_angle_SP = 0
    lift_angle_PV = 0
    belt_speed_SP = 0
    belt_speed_PV = 0
    vertical_speed_PV = 0
    belt_direction = True
    safeties = {
        "top": True,
        "bottom": True,
        "left": True,
        "right": True,
        "emergency": True
    }
    treadmill_points = None

    running = False
    paused = False

    def __init__(self, hardware):
        self.hardware = hardware
        self.reset_variables()
        self.belt_acc = config['BELT_ACC']
        self.current_speed_command = 0
        self.test_name = "manual_test"
        self.subject_name = "sujet"
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
        # Thread-safe queue for logging
        self.log_queue = queue.Queue()
        self.log_thread = None
        self.stop_logging_thread = threading.Event()

    def _log_worker(self):
        """Worker thread for writing logs to file."""
        Logger.info("Treadmill: Log worker thread started.")
        while not self.stop_logging_thread.is_set():
            try:
                # Wait for a log entry, with a timeout to allow checking the stop signal
                log_data = self.log_queue.get(timeout=0.1)
                if log_data is None:  # Sentinel value to stop
                    break
                if self.log_writer:
                    self.log_writer.writerow(log_data)
                    # Flush occasionally, not on every write
                    if self.log_queue.qsize() == 0:
                        self.log_file.flush()
                self.log_queue.task_done()
            except queue.Empty:
                continue
        Logger.info("Treadmill: Log worker thread stopped.")

    def record_event(self, event_name=None):
        """Record an event with the current elapsed time and optional name."""
        now = datetime.now()
        event = {
            'datetime': now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'time': self.elapsed_time,
            'belt_speed_SP': self.belt_speed_SP,
            'belt_speed_PV': self.belt_speed_PV,
            'lift_angle_SP': self.lift_angle_SP,
            'lift_angle_PV': self.lift_angle_PV,
            'vertical_speed_SP': compute_vertical_speed_mh(self.lift_angle_SP, self.belt_speed_SP),
            'vertical_speed_PV': self.vertical_speed_PV,
            'distance_m': self.distance_m,
            'elevation_pos_m': self.elevation_pos_m,
            'elevation_neg_m': self.elevation_neg_m,
            'event': event_name,
        }
        # Append to in-memory list
        self.event_list.append(event)
        #toggle log event
        self.log_event = True
        # Write to event file if open
        if self.event_file:
            # Check if the file is empty to write headers
            is_new_file = self.event_file.tell() == 0
            fieldnames = ['datetime', 'time', 'belt_speed_SP', 'belt_speed_PV', 'lift_angle_SP', 'lift_angle_PV', 'vertical_speed_SP', 'vertical_speed_PV', 'distance_m', 'elevation_pos_m', 'elevation_neg_m', 'event']
            writer = csv.DictWriter(self.event_file, fieldnames=fieldnames)
            if is_new_file:
                writer.writeheader()
            writer.writerow(event)
            self.event_file.flush()

    def _open_event_file(self):
        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d-%H%M%S-%f')
        event_folder = os.path.join(self.event_folder, now.strftime('%Y'), now.strftime('%m'), now.strftime('%d'))
        os.makedirs(event_folder, exist_ok=True)
        event_path = os.path.join(event_folder, f'{now_str}_{self.subject_name}_{self.test_name}-events.csv')

        # Open in append mode and write header only if the file is new
        file_exists = os.path.exists(event_path)
        self.event_file = open(event_path, 'a', newline='')
        if not file_exists:
            fieldnames=['datetime', 'time', 'belt_speed_SP', 'belt_speed_PV', 'lift_angle_SP', 'lift_angle_PV', 'vertical_speed_SP', 'vertical_speed_PV', 'distance_m', 'elevation_pos_m', 'elevation_neg_m', 'event']
            writer = csv.DictWriter(self.event_file, fieldnames=fieldnames)
            writer.writeheader()
            self.event_file.flush()


    def _close_event_file(self):
        if self.event_file:
            self.event_file.close()
            self.event_file = None

    def _open_log_file(self):
        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d-%H%M%S-%f')
        log_folder = os.path.join(self.log_folder, now.strftime('%Y'), now.strftime('%m'), now.strftime('%d'))
        os.makedirs(log_folder, exist_ok=True)
        log_path = os.path.join(log_folder, f'{now_str}_{self.subject_name}_{self.test_name}-log.csv')
        self.log_file = open(log_path, 'w', newline='')
        self.log_writer = csv.DictWriter(self.log_file, fieldnames=[
            'datetime', 'time', 'belt_speed_SP', 'belt_speed_PV', 'lift_angle_SP', 'lift_angle_PV', 'vertical_speed_SP', 'vertical_speed_PV', 'distance_m', 'elevation_pos_m', 'elevation_neg_m', 'event'
        ])
        self.log_writer.writeheader()
        # Start the logging thread
        self.stop_logging_thread.clear()
        self.log_thread = threading.Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()

    def _close_log_file(self):
        if self.log_thread and self.log_thread.is_alive():
            # Signal the thread to stop and wait for it to process the queue
            self.log_queue.put(None)
            self.log_thread.join(timeout=2) # Wait for max 2 seconds
            self.stop_logging_thread.set()


        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.log_writer = None

    def reset_variables(self):
        self.distance_m = 0
        self.elevation_pos_m = 0
        self.elevation_neg_m = 0
        self.elapsed_time = 0
        self.start_time = 0
        self.pause_time = 0
        self.elapsed_pause_time = 0
        self.last_update_time = 0
        self.current_speed_command = 0
        self.treadmill_points = collections.deque(maxlen=16200) # 90 minutes of data at 3Hz
        self.event_list = []
        self.update_counter = 0

    def update(self):
        #update PV
        if self.hardware:
            self.lift_angle_PV = self.hardware.get_lift_angle()
            self.belt_speed_PV = self.hardware.get_belt_speed()
            self.safeties = self.hardware.get_safeties()
            self.belt_direction = self.hardware.get_belt_direction()
        #When there is no hardware : PV set to setpoint and 1% of random noise
        else:
            self.lift_angle_PV = add_noise(self.lift_angle_SP, noise_level=0.001)
            self.belt_speed_PV = add_noise(self.current_speed_command)
        #compute vertical speed
        self.vertical_speed_PV = compute_vertical_speed_mh(self.lift_angle_PV,self.belt_speed_PV)

        # Downsample data for the live graph (3Hz)
        self.update_counter += 1
        if self.update_counter % 3 == 0:
            #store treadmill points
            self.treadmill_points.append({
                'time': self.elapsed_time,
                'speed': self.belt_speed_PV,
                'incl': self.lift_angle_PV,
                'asc': self.vertical_speed_PV
            })
            
        # RAMP LOGIC
        if self.current_speed_command != self.belt_speed_SP:
            max_speed_change = self.belt_acc * 0.1
            diff = self.belt_speed_SP - self.current_speed_command

            if abs(diff) <= max_speed_change:
                self.current_speed_command = self.belt_speed_SP
            else:
                self.current_speed_command += math.copysign(max_speed_change, diff)

            if self.hardware:
                self.hardware.set_belt_speed(self.current_speed_command)
            #print(f"Ramp: current {self.current_speed_command}, target {self.belt_speed_SP}, diff {diff}, max change {max_speed_change}")


        #update running value
        if self.is_running():
            #update elapsed time
            current_time = time()
            #init time if first loop
            if self.last_update_time == 0:
                self.last_update_time = current_time

            self.elapsed_time = current_time - self.start_time - self.elapsed_pause_time
            delta_time = current_time - self.last_update_time
            
            #compute distance and elevation
            if delta_time > 0:
                self.distance_m += (self.belt_speed_PV * 1000 / 3600) * delta_time
                delta_elevation = (self.vertical_speed_PV / 3600) * delta_time
                if not self.belt_direction: #if backward
                    delta_elevation = -delta_elevation
                if delta_elevation > 0:
                    self.elevation_pos_m += delta_elevation
                else:
                    self.elevation_neg_m += delta_elevation
            self.last_update_time = current_time
            
            # Log to file if running by putting data in the queue
            if self.log_thread and self.log_thread.is_alive():
                #add event string only if there was an event
                if self.log_event:
                    event_str = self.event_list[-1]['event'] if self.event_list else ''
                    self.log_event = False
                else:
                    event_str = ''
                
                log_data = {
                    'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                    'time': self.elapsed_time,
                    'belt_speed_SP': self.belt_speed_SP,
                    'belt_speed_PV': self.belt_speed_PV,
                    'lift_angle_SP': self.lift_angle_SP,
                    'lift_angle_PV': self.lift_angle_PV,
                    'vertical_speed_SP': compute_vertical_speed_mh(self.lift_angle_SP, self.belt_speed_SP),
                    'vertical_speed_PV': self.vertical_speed_PV,
                    'distance_m': self.distance_m,
                    'elevation_pos_m': self.elevation_pos_m,
                    'elevation_neg_m': self.elevation_neg_m,
                    'event': event_str
                }
                self.log_queue.put(log_data)
            
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
            "elevation_pos_m": self.elevation_pos_m,
            "elevation_neg_m": self.elevation_neg_m,
            "elapsed_time": self.elapsed_time,
            "belt_direction": self.belt_direction
        }

    def start(self, test_name="manual_test", subject_name="sujet"):
        if not self.running:
            self.running = True
            self.test_name = test_name
            self.subject_name = subject_name
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
        if self.running and not self.paused:
            self.paused = True
            self.pause_time = time()
            self.current_speed_command = 0
            if self.hardware:
                self.hardware.stop_belt()
            Logger.info(f"Treadmill: Paused at {self.pause_time}")
            self.record_event('pause')

    def stop(self):
        self.running = False
        self.paused = False
        self.current_speed_command = 0
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
        Logger.info(f"Treadmill: Set belt speed to {speed}")

    def reverse_belt(self, direction):
        self.belt_direction = direction
        if self.hardware:
            self.hardware.set_belt_direction(direction)
        Logger.info(f"Treadmill: Set belt direction to {'forward' if direction else 'backward'}")

    #All get functions return the current setpoint or process variable if there is no treadmill attached
    #Caution to self.update() before calling getter
    def get_belt_direction(self):
        return self.belt_direction

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

    def get_elevation_pos(self):
        return self.elevation_pos_m

    def get_elevation_neg(self):
        return self.elevation_neg_m

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
