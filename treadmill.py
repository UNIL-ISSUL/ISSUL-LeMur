#Gestion du tapis de course
#Calcul du elapsed time de start,stop, pause, resume
#Calul de la distance parcourue, du dénivelé
from time import time
from kivy.logger import Logger
import math

def compute_vertical_speed_mh(tilt_degree,belt_speed_kmh):
    return math.sin(math.radians(tilt_degree)) * belt_speed_kmh * 1000

class TreadmillController:
    #variables
    angle_SP = 0
    angle_PV = 0
    belt_speed_SP = 0
    belt_speed_PV = 0
    vertical_speed_SP = 0
    vertical_speed_PV = 0

    #status
    is_running = False
    is_paused = False

    def __init__(self, hardware):
        self.hardware = hardware
        self.reset_variables()

    def reset_variables(self):
        self.distance_m = 0
        self.elevation_m = 0
        self.elapsed_time = 0
        self.start_time = 0
        self.pause_time = 0
        self.elapsed_pause_time = 0
        self.last_update_time = 0

    def update(self):
        #update PV
        if self.hardware:
            self.angle_PV = self.hardware.get_lift_angle()
            self.belt_speed_PV = self.hardware.get_belt_speed()
            self.vertical_speed_PV = compute_vertical_speed_mh(self.angle_PV,self.belt_speed_PV)

        #update running value
        if self.is_running and not self.is_paused:
            #update elapsed time
            current_time = time()
            self.elapsed_time = current_time - self.start_time - self.elapsed_pause_time
            #compute distance and elevation
            delta_time = current_time - self.last_update_time
            if delta_time > 0:
                self.distance_m += (self.belt_speed_PV * 1000 / 3600) * delta_time
                self.elevation_m += (self.vertical_speed_PV / 3600) * delta_time
            self.last_update_time = current_time

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.reset_variables()
            self.start_time = self.last_update_time = time()
            if self.hardware:   self.hardware.start_belt()
            Logger.info(f"Treadmill: Starting at {self.start_time}")
        if self.is_paused:
            self.is_paused = False
            self.elapsed_pause_time += time() - self.pause_time
            if self.hardware:   self.hardware.start_belt()
            Logger.info(f"Treadmill: Resumed at {time()}")


    def pause(self):
        if self.is_running:
            self.is_paused = True
            self.pause_time = time()
            if self.hardware:   self.hardware.stop_belt()
            Logger.info(f"Treadmill: Paused at {self.pause_time}")

    def stop(self):
        self.is_running = False
        if self.hardware:   self.hardware.stop_belt()
        Logger.info(f"Treadmill: Stopped at {time()}")