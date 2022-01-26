import platform

def is_raspberry_pi() -> bool:
    return platform.machine() in ('armv7l', 'armv6l')

import revpimodio2
import numpy as np
import math
from threading import Thread
from pathlib import Path
#READ CONFIGURATION FILE
import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def read_yaml(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

#config dictionary
file = Path(__file__)
config = read_yaml(file.parent/'settings.yaml')

#PARAMETERS FOR LIFT DISPLACEMENT
buffer_size = 1           #nombre de valeur d'inclinaison moyennés
angular_resolution = 0.1    #precision du positionement angulaire

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
        #set lift frequency to config value
        rpi.io.lift_speed_mv.value = config['LIFT_FREQ_HZ']*config['LIFT_HZ2mV'] #mV
        rpi.io.lift_up.value = False
        rpi.io.lift_down.value = False
        #set event to create latch function on belt-start and belt_stop
        rpi.io.belt_start.reg_timerevent(self.latch_output, 100,edge=revpimodio2.RISING)    #start is trigger to 0 after 100ms
        rpi.io.belt_stop.reg_timerevent(self.latch_output, 100,edge=revpimodio2.FALLING)    #stop is trigger to 1 after 100ms
        self.rpi = rpi
    
    def latch_output(self,io_name,io_value) :
        #invert io value
        self.rpi.io[io_name].value = not io_value

    def start_cycle(self) :
        #start cycleloop, read_inclinaison will be call at every 10ms
        #https://revolutionpi.de/forum/viewtopic.php?t=2976
        #Change ADC rate in pictory ADC_DataRate (160Hz, 320Hz, 640Hz Max)
        self.thread=Thread(target=self.rpi.cycleloop,args=[self.loop,config['CYCLETIME_MS'],True],daemon=True)
        self.thread.start()
    
    def loop(self, ct) :
        #self.read_inclinaison(ct)
        self.tilt_current = self.tilt_mv2deg(ct.io.tilt_mv.value)
        if self.tilt_target :
            #print('target defined')
            if self.move_lift :
                #print('move true')
                self.lift(ct)

    def tilt_mv2deg(self,mv) :
        return mv*config['CAL_TILT_A']+config['CAL_TILT_B']

    def set_belt_speed(self,Vkmh) :
        Vms = Vkmh / 3.6 
        F = Vms * 50 * 60 * config['Z_BELT'] / (1450 * 2*np.pi * config['Z_MOTOR'] * config['RADIUS_CYL_MM']*1e-3)
        #int is sent to frequency inverter with 0.01 precision
        self.rpi.io.belt_frequency.value = int(F*100)
    
    def read_belt_speed(self) :
         f = self.rpi.io.belt_current_frequency.value
         f  /= 100  #int is received from controller with 0.01 precision
         Vms = f * 1450 * 2*np.pi * config['Z_MOTOR'] * config['RADIUS_CYL_MM']*1e-3 / (50 * 60 * config['Z_BELT'])
         return Vms*3.6

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
        delta = config['BELT_LENGTH_MM'] * (math.sin(target)-math.sin(current))
        #Compute lift vertical acceleration
        #moteur speed 1400 tr/min @ 50HZ
        #screw step 2.5 mm/tr NSE10-SN-KGT
        acc_mm_s2 = 1400.0 / 60 * 2.5 / config['LIFT_ACC_S']
        #distance travel during acc -> primitive de la vistesse du type f(t)=a.t -> F(t) = a.t^2/2
        dst_acc = acc_mm_s2 * config['LIFT_ACC_S']**2 / 2
        #Check if Max speed is reach during displacement
        if abs(delta/2) < dst_acc :
            #max speed is not reach
            dst_acc = abs(delta/2)
        print('dst_acc ',dst_acc)
        #distance to travel before stopping move command
        #dst_move = delta-math.copysign(dst_acc,delta)
        #target_corrected = math.asin(dst_move/L+math.sin(current))
        target_corrected = math.asin(math.sin(target)-math.copysign(dst_acc/config['BELT_LENGTH_MM'],delta))
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