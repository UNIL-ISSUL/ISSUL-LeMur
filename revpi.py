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
    pid_control = True

    def __init__(self) -> None:
        #define RevPiModIO instance
        #standard cycle @50hz
        rpi = revpimodio2.RevPiModIO(autorefresh=True)
        #set belt default value
        rpi.io.belt_stop.value=1
        rpi.io.belt_start.value=0
        rpi.io.belt_dir.value=1
        #set event to create latch function on belt-start and belt_stop
        rpi.io.belt_start.reg_timerevent(self.latch_output, 100,edge=revpimodio2.RISING,as_thread=True)    #start is trigger to 0 after 100ms
        rpi.io.belt_stop.reg_timerevent(self.latch_output, 100,edge=revpimodio2.FALLING,as_thread=True)    #stop is trigger to 1 after 100ms
        #set event to handle safety input
        rpi.io.lift_safety.reg_event(self.stop_all,edge=revpimodio2.FALLING,as_thread=True)
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
        #call to be defined   
    
    def set_target(self,target) :
        #call to be defined
        pass

    #no longer used keep for reference
    def start_cycle(self) :
        #start cycleloop, read_inclinaison will be call at every 10ms
        #https://revolutionpi.de/forum/viewtopic.php?t=2976
        #Change ADC rate in pictory ADC_DataRate (160Hz, 320Hz, 640Hz Max)
        self.cycle_thread=Thread(target=self.rpi.cycleloop,args=[self.loop,config['CYCLETIME_MS'],True],daemon=True,name="RevPICycleLoop")
        self.cycle_thread.start()

    #set belt speed to controller via modbus
    def set_belt_speed(self,Vkmh) :
        Vms = Vkmh / 3.6 
        F = Vms * 50 * 60 * config['Z_BELT'] / (1450 * 2*np.pi * config['Z_MOTOR'] * config['RADIUS_CYL_MM']*1e-3)
        #int is sent to frequency inverter with 0.01 precision
        self.rpi.io.belt_frequency.value = int(F*100)
    
    #to be updated to read encoder value
    def read_belt_speed(self) :
         f = self.rpi.io.belt_current_frequency.value
         f  /= 100  #int is received from controller with 0.01 precision
         Vms = f * 1450 * 2*np.pi * config['Z_MOTOR'] * config['RADIUS_CYL_MM']*1e-3 / (50 * 60 * config['Z_BELT'])
         return Vms*3.6

if __name__ == '__main__':
    import sys, select, os
    import time
    os.system('cls' if os.name == 'nt' else 'clear')
    lemur = revPI()
    print("right :"+str(lemur.rpi.io.secu_right.value),"left :"+str(lemur.rpi.io.secu_left.value))
    lemur.start_cycle()
    Ku = 4  # old 4
    Tu = 3    # 3.3 at 4
    #lemur.pid.tunings = (0.2*Ku, 1/(0.5*Tu), 1/(0.33*Tu))
    lemur.pid.tunings = (0.6,0.0,1/8)
    #gain critique 4
    lemur.set_lift_height(lemur.height+500)
    #lemur.set_lift_height(1000)
    target = []
    h = []
    t = []
    t0 = time.time()
    print("error :"+str(lemur.height_target-lemur.height))
    print("press any key to stop test")
    while(1) :
        target.append(lemur.height_target)
        h.append(lemur.height)
        t.append(time.time()-t0)
        print("error :"+str(lemur.height_target-lemur.height))#,"components :"+str(lemur.pid.components))
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            break
    print("error :"+str(lemur.height_target-lemur.height))
    lemur.rpi.exit()
    lemur.stop_lift("exit")
    import hipsterplot as hplot
    hplot.plot(h,x_vals=t,num_x_chars=150,num_y_chars=20)
    #import plotille
    #print(plotille.plot(t, height))
    #import plotext as plt
    #plt.scatter(t,h)
    #plt.title("Scatter Plot")
    #plt.show()
    #response = np.array([t,h])
    #np.savetxt('response.txt',np.column_stack((t,h)),delimiter=',')

