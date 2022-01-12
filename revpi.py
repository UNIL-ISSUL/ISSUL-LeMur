import platform

def is_raspberry_pi() -> bool:
    return platform.machine() in ('armv7l', 'armv6l')

import revpimodio2
import numpy as np
import math
from threading import Thread

buffer_size = 1           #nombre de valeur d'inclinaison moyennés
angular_resolution = 0.1    #precision du positionement angulaire
L = 2400                    #longueur du tapis en mm
lift_frequency = 50         #lift_frequency
lift_acceleration_s = 6.34     #time to accelerate from stop to 50Hz

class revPI() :
    tilt_mv = np.empty(buffer_size,np.double)
    tilt_current = None
    tilt_target = None
    tilt_stop = None
    move_lift = False

    def __init__(self) -> None:
        #define RevPiModIO instance
        #standard cycle @50hz
        rpi = revpimodio2.RevPiModIO(autorefresh=True)
        #self.rpi.cycletime = 10
        #read current angle
        self.tilt_current = self.tilt_mv2deg(rpi.io.tilt_mv.value)
        #set lift frequency to 50Hz (5V)
        rpi.io.lift_speed_mv.value = 5000
        rpi.io.lift_up.value = False
        rpi.io.lift_down.value = False
        self.rpi = rpi

    def start_cycle(self) :
        #start cycleloop, read_inclinaison will be call at every 10ms
        #https://revolutionpi.de/forum/viewtopic.php?t=2976
        #Change ADC rate in pictory ADC_DataRate (160Hz, 320Hz, 640Hz Max)
        self.thread=Thread(target=self.rpi.cycleloop,args=[self.loop,10,True],daemon=True)
        self.thread.start()
        #self.rpi.cycleloop(self.loop, cycletime=10, blocking=False)
    
    def loop(self, ct) :
        #self.read_inclinaison(ct)
        self.tilt_current = self.tilt_mv2deg(ct.io.tilt_mv.value)
        if self.tilt_target :
            #print('target defined')
            if self.move_lift :
                #print('move true')
                self.lift(ct)

    def tilt_mv2deg(self,mv) :
        return mv*-0.071732393+268.9148431

    def read_inclinaison(self,ct) :
        #read value from sensor
        value_mv = ct.io.tilt_mv.value
        #shift array value to the right, last value is re-introduced first
        self.tilt_mv = np.roll(self.tilt_mv,1)
        #overwrite first value
        self.tilt_mv[0] = value_mv
        #define a counter
        if ct.first :
            ct.var.counter = 0
        #increment counter until buffer is full of value
        if ct.var.counter < buffer_size :
            ct.var.counter += 1

        #Compute mean of analog value to degree
        self.tilt_current = np.mean(self.tilt_mv2deg(self.tilt_mv[0:ct.var.counter]))
    
    def lift(self,ct) :
        #print("enter lift fonction")
        #convert target and current position to radians
        target = math.radians(self.tilt_target)
        current = math.radians(self.tilt_current)
        end_run = math.radians(self.tilt_stop)
        #move lift if target is not reached
        if abs(target-current) > math.radians(angular_resolution): #target not reach yet
            if self.move_up : #move up
                if end_run -current > 0 : #end point not reach
                    ct.io.lift_up.value = True
                    ct.io.lift_down.value = False
                else : #stop motion
                    ct.io.lift_up.value = False
            else : #move down
                if end_run - current < 0 : #end_point not reach
                    ct.io.lift_down.value = True
                    ct.io.lift_up.value = False
                else : #stop motion
                    ct.io.lift_down.value = False
        else : # target is reached
            print('lift displacement done')
            self.move_lift = False
    
    def set_target(self,target) :
        #convert angles in radians
        target = math.radians(target)
        current = math.radians(self.tilt_current)
        #Compute distance to travel on  screw
        delta = L * (math.sin(target)-math.sin(current))
        #Compute lift vertical acceleration
        #moteur speed 1400 tr/min @ 50HZ
        #screw step 2.5 mm/tr NSE10-SN-KGT
        acc_mm_s2 = 1400.0 / 60 * 2.5 / lift_acceleration_s
        #distance travel during acc -> primitive de la vistesse du type f(t)=a.t -> F(t) = a.t^2/2
        dst_acc = acc_mm_s2 * lift_acceleration_s**2 / 2
        #Check if Max speed is reach during displacement
        if abs(delta/2) < dst_acc :
            #max speed is not reach
            dst_acc = abs(delta/2)
        print('dst_acc ',dst_acc)
        #distance to travel before stopping move command
        #dst_move = delta-math.copysign(dst_acc,delta)
        #target_corrected = math.asin(dst_move/L+math.sin(current))
        target_corrected = math.asin(math.sin(target)-math.copysign(dst_acc/L,delta))
        self.tilt_stop = math.degrees(target_corrected)
        self.tilt_target = math.degrees(target)
        self.move_up = 1 if target > current else 0
        print('target received ',math.degrees(target),' corrected target : ',math.degrees(target_corrected))
        self.move_lift = True

if __name__ == '__main__':
    test = revPI()
    test.start_cycle()
    test.set_target(5)
    while(True):
        pass