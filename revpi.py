import platform

def is_raspberry_pi() -> bool:
    return platform.machine() in ('armv7l', 'armv6l')

import revpimodio2
import numpy as np
from scipy import interpolate
import math
from threading import Thread
from pathlib import Path
from average import EWMA
from simple_pid import PID
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
    avg = None
    pid = None
    tilt_current = None
    tilt_target = None
    tilt_stop = None
    move_lift = False
    cycle_thread = None
    ramp = False
    f_lift_speed = None

    def __init__(self) -> None:
        #define RevPiModIO instance
        #standard cycle @50hz
        rpi = revpimodio2.RevPiModIO(autorefresh=True)
        #self.rpi.cycletime = 10
        #define running average
        self.avg = EWMA(beta=0.9)
        #read current angle
        self.tilt_current = self.tilt_mv2deg(rpi.io.tilt_mv.value)
        self.height = self.tilt_to_linear(math.radians(self.tilt_current))
        #define pid
        self.pid = PID(0.75,0.225,0,setpoint = self.tilt_to_linear(math.radians(self.tilt_current)))
        self.pid.output_limits = (-50, 50)
        #set lift frequency to config value
        rpi.io.lift_speed_mv.value = config['LIFT_FREQ_HZ']*config['LIFT_HZ2mV'] #mV
        rpi.io.lift_up.value = False
        rpi.io.lift_down.value = False
        #set belt default value
        rpi.io.belt_stop.value=1
        rpi.io.belt_start.value=0
        rpi.io.belt_dir.value=1
        #set event to create latch function on belt-start and belt_stop
        #rpi.io.belt_start.reg_timerevent(self.latch_output, 100,edge=revpimodio2.RISING)    #start is trigger to 0 after 100ms
        #rpi.io.belt_stop.reg_timerevent(self.latch_output, 100,edge=revpimodio2.FALLING)    #stop is trigger to 1 after 100ms
        #close the program properly
        rpi.handlesignalend(cleanupfunc=self.stop_all)

        self.rpi = rpi
    
    def stop_all(self) :
        #stop lift
        self.stop_lift("exit program")
        #stop belt
        self.rpi.io.belt_stop.value = 0
        #stop cycleloop
        self.rpi.exit()
    
    def latch_output(self,io_name,io_value) :
        #invert io value
        self.rpi.io[io_name].value = not io_value
    
    def stop_lift(self,msg="") :
        print('STOP lift','reason :',msg)
        self.rpi.io.lift_up.value = False
        self.rpi.io.lift_down.value = False
        self.move_lift = False
        #stop ramp if it was active and restore lift speed
        if self.ramp :
            self.ramp = False
            self.rpi.io.lift_speed_mv.value = config['LIFT_FREQ_HZ']*config['LIFT_HZ2mV'] #mV
    
    def update_lift(self,frequency, rpi = None) :
        if rpi is None :
            rpi = self.rpi
        #update motor frequency
        rpi.io.lift_speed_mv.value = int(abs(frequency)*config['LIFT_HZ2mV']) #mV
        #change up / down according to frequency sign
        if frequency > 0 :
            rpi.io.lift_down.value = False
            rpi.io.lift_up.value = True
        elif frequency < 0 :
            rpi.io.lift_up.value = False
            rpi.io.lift_down.value = True 
        else :
            rpi.io.lift_up.value = False
            rpi.io.lift_down.value = False    

    def set_lift_height(self,height_mm) :
        self.height_target = height_mm
        self.pid.setpoint = height_mm   

    def start_cycle(self) :
        #start cycleloop, read_inclinaison will be call at every 10ms
        #https://revolutionpi.de/forum/viewtopic.php?t=2976
        #Change ADC rate in pictory ADC_DataRate (160Hz, 320Hz, 640Hz Max)
        self.cycle_thread=Thread(target=self.rpi.cycleloop,args=[self.loop,config['CYCLETIME_MS'],True],daemon=True,name="RevPICycleLoop")
        self.cycle_thread.start()
    
    def loop(self, ct) :

        #Look change on safety input to stop lift if moving
        if ct.changed(ct.io.lift_safety,edge=revpimodio2.FALLING) :
            self.stop_lift()
        
        if ct.changed(ct.io.belt_start,edge=revpimodio2.RISING) :
            ct.io.belt_start.value = 0
            pass

        if ct.changed(ct.io.belt_stop,edge=revpimodio2.FALLING) :
            ct.io.belt_stop.value = 1
            pass

        #update avg with new value
        readout = ct.io.tilt_mv.value
        avg_value = self.avg.update(readout)
        self.tilt_current = self.tilt_mv2deg(avg_value)
        #print("mv_tilt :"+str(self.tilt_mv2deg(readout))+" avg_value :"+str(self.tilt_mv2deg(avg_value)))

        #move lift
       # if self.tilt_target and self.move_lift :
       #     self.lift(ct)

        #test pid
        height = self.tilt_to_linear(math.radians(self.tilt_current))
        self.height = height
        frequency = self.pid(height)
        self.update_lift(frequency,ct)


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
        #adjust lift speed is ramp mode active
        if self.ramp :
            speed_mm_s = self.f_lift_speed(self.tilt_current)
            ct.io.lift_speed_mv.value = int(self.convert_lift_speed_to_mV(speed_mm_s))
        #move lift if target is not reached
        if abs(target-current) > math.radians(angular_resolution): #target not reach yet
            if self.move_up : #move up
                if end_run - current > 0 : #end point not reach
                    ct.io.lift_up.value = True
                    ct.io.lift_down.value = False
                else : #stop motion
                    self.stop_lift('end of motion')
            else : #move down
                if end_run - current < 0 : #end_point not reach
                    ct.io.lift_down.value = True
                    ct.io.lift_up.value = False
                else : #stop motion
                    self.stop_lift('end of motion')
        else : # target is reached
            print('lift displacement done')
            self.stop_lift('target reached')
    
    def horizontal_position(self,angle_rad) :
        disp = config['BELT_LENGTH_MM']*math.cos(angle_rad)-config['BELT_HEIGHT_MM']*math.cos(np.pi/2-angle_rad)
        return disp

    def tilt_to_linear(self,angle_rad) :
        height = config['BELT_LENGTH_MM']*math.sin(angle_rad)+config['BELT_HEIGHT_MM']*math.sin(np.pi/2-angle_rad)
        temp = 0
        if math.degrees(angle_rad) > 80 :
            temp = math.tan(0.1337)*self.horizontal_position(angle_rad) - self.horizontal_position(math.radians(80))
        height -= temp
        #print('linear_dist', length, math.degrees(angle_rad))
        return height
    
    def find_stop_angle_rad(self,x,target_rad,dst_stop_signed) : 
        #print('args',math.degrees(x),math.degrees(target_rad),dst_stop_signed)
        temp = self.tilt_to_linear(target_rad)-self.tilt_to_linear(x)-dst_stop_signed
        #print('result ',temp)
        return temp

    def set_target(self,target) :
        #set new target if lift is not moving
        if (not self.rpi.io.lift_up.value) and (not self.rpi.io.lift_down.value) :
            #convert angles in radians
            target = math.radians(target)
            current = math.radians(self.tilt_current)
            #Compute distance to travel on  screw
            delta = self.tilt_to_linear(target)-self.tilt_to_linear(current)
            print('delta :',delta)
            #Compute lift vertical acceleration
            #moteur speed 1400 tr/min @ 50HZ
            #screw step 2.5 mm/tr NSE10-SN-KGT
            acc_mm_s2 = 1400.0 / 60 * 2.5 / config['LIFT_ACC_S']
            #distance travel during acc -> primitive de la vistesse du type f(t)=a.t -> F(t) = a.t^2/2
            dst_stop = acc_mm_s2 * config['LIFT_ACC_S']**2 / 2
            #Check if Max speed is reach during displacement
            if abs(delta/2) < dst_stop :
                #max speed is not reach
                dst_stop = abs(delta/2)
            print('dst_stop ',dst_stop)
            #distance to travel before stopping move command
            from scipy.optimize import root
            res = root(self.find_stop_angle_rad,x0=target,args=(target,math.copysign(dst_stop,delta)))
            target_stop = res.x
            self.tilt_stop = math.degrees(target_stop)
            self.tilt_target = math.degrees(target)
            self.move_up = 1 if target > current else 0
            print('target received ',math.degrees(target),' corrected target : ',math.degrees(target_stop))
            self.move_lift = True
        #stop motion
        else :
            #stop lift motion
            self.stop_lift()
    
    def set_ramp(self,start_angle_deg,stop_angle_deg,angular_speed_deg_min) :
        #define ramp mode
        self.ramp = True
        #compute speed lookup table as a fonction of inclinaison
        angular_speed_deg_s = angular_speed_deg_min / 60
        duration_s = int(abs(stop_angle_deg-start_angle_deg) / angular_speed_deg_s)
        step_s = 1
        #time vector for ramp experiment, 2 steps are added to stop because arange exclude stop value and to add one value prior to differatiation
        time = np.arange(start=0,stop=duration_s+step_s,step=step_s)
        #get direction of motion
        direction = math.copysign(1,stop_angle_deg-start_angle_deg)
        lift_angle = direction*time*angular_speed_deg_s + start_angle_deg
        lift_height = np.zeros_like(time,dtype=np.float)
        for i, angle in enumerate(lift_angle) :
            lift_height[i] = self.tilt_to_linear(math.radians(angle))
        lift_speed = np.diff(lift_height,n=1)
        #remove last element form angle value (use to compte diff)
        lift_angle = np.delete(lift_angle,-1)
        print(lift_angle)
        #print(lift_speed.shape,lift_angle.shape)
        #get function to interpolate during motion
        self.f_lift_speed = interpolate.interp1d(lift_angle,lift_speed,fill_value='extrapolate')
        self.set_target(stop_angle_deg)
    
    def convert_lift_speed_to_mV(self, speed_mm_s) :
        omega_tr_min = 60 * speed_mm_s / config["LIFT_MM_TR"]
        freq_Hz = omega_tr_min * 50 / config["LIFT_TR_MIN"]
        freq_mV = abs(freq_Hz * config["LIFT_HZ2mV"])
        print("frequnecy [Hz]"+str(freq_Hz)+" consigne [mV]"+str(freq_mV))
        return freq_mV


if __name__ == '__main__':
    import sys, select, os
    os.system('cls' if os.name == 'nt' else 'clear')
    lemur = revPI()
    lemur.start_cycle()
    lemur.pid.tunings = (0.5, 0, 0)
    lemur.set_lift_height(850)
    target = []
    height = []
    while(1) :
        target.append(lemur.height_target)
        height.append(lemur.height)
        print("error :"+str(lemur.height_target-lemur.height))
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            break
    lemur.stop_lift("exit")
    #import matplotlib.pyplot as plt
    #plt.plot(height)
    #plt.plot(height_target)
    #plt.show()