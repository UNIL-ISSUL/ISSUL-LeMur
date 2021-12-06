import platform

def is_raspberry_pi() -> bool:
    return platform.machine() in ('armv7l', 'armv6l')

import revpimodio2
import numpy as np
import math

buffer_size = 100           #nombre de valeur d'inclinaison moyennés
angular_resolution = 0.1    #precision du positionement angulaire
L = 2500                    #longueur du tapis en mm
lift_frequency = 500        #lift_frequency

class revPI() :
    angle_mv = np.empty(buffer_size,np.double)
    tilt_current = None
    tilt_target = None
    move_lift = False

    def __init__(self) -> None:
        #define RevPiModIO instance
        #standard cycle @50hz
        rpi = revpimodio2.RevPiModIO(autorefresh=True)
    
    def start(self) :
        #start cycleloop, read_inclinaison will be call at every 10ms
        #https://revolutionpi.de/forum/viewtopic.php?t=2976
        #Change ADC rate in pictory ADC_DataRate (160Hz, 320Hz, 640Hz Max)
        self.rpi.cycleloop(self.read_inclinaison, cycletime=10, blocking=False)
    
    def loop(self, ct) :
        self.read_inclinaison(ct)
        if self.move_lift & self.tilt_target :
            self.lift(ct)

    def read_inclinaison(self,ct) :
        #read value from sensor
        value_mv = ct.angle_mv.value
        #shift array value to the right, last value is re-introduced first
        self.angle_mv.roll(1)
        #overwrite first value
        self.angle_mv[0] = value_mv
        #define a counter
        if ct.first() :
            ct.var.counter = 0
        #increment counter until buffer is full of value
        if ct.var.counter < buffer_size :
            ct.var.counter += 1

        #Compute mean of analog value to degree
        a = 1.0
        b = 0 
        self.tilt = np.mean(self.angle_mv[0:ct.var.counter]) * a + b
        print(self.tilt)
    
    def lift(self,ct) :
        #convert target and current position to radians
        target = math.radians(self.tilt_target)
        current = math.radians(self.tilt_current)
        #move lift if target is not reached
        if abs(target-current) > math.radians(angular_resolution) :
            #delta distance to travel on the screw
            delta = L * (math.sin(target)-math.sin(current))
            #compute frequency : frequency if displacement is >= 1/4 of screw length
            frequency = delta * lift_frequency / (L/4)
            #limit frequency to lift_frequency
            if frequency > lift_frequency :
                frequency = lift_frequency
            #send new frequency to controller
            lift_freq_to_mv = 1
            ct.lift_speed = frequency * lift_freq_to_mv
            #move the lift
            ct.io.lift_dir = True if delta >0 else False
            ct.io.lift_start = True
        #target is reached stop the lift and change move_lift flag
        else :
            self.move_lift = False
            ct.io.lift_start = False
    
    def set_target(self,target) : 
        self.tilt_target = target
        self.move_lift = True

if __name__ == '__main__':
    test = revPI()