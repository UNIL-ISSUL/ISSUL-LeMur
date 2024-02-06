import platform

def is_raspberry_pi() -> bool:
    return platform.machine() in ('armv7l', 'armv6l')

import revpimodio2
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

class revPI() :

    def __init__(self) -> None:
        #define RevPiModIO instance
        rpi = revpimodio2.RevPiModIO(autorefresh=True)
        #set belt default value
        rpi.io.belt_stop.value=1
        rpi.io.belt_start.value=0
        rpi.io.belt_dir.value=1
        #set current speed to 0
        #
        #enable speed PID
        self.enable_belt(True)
        #disable distance PID
        #

        #set lift default value
        #read current lift angle et set it as set point
        #
        #enable lift PID
        self.enable_lift(True)

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
        self.stop_belt("exit program")
        #disable distance PID
        self.enable_dist(False)
        #stop cycleloop
        self.rpi.exit()
    
    def latch_output(self,io_name,io_value) :
        #invert io value
        self.rpi.io[io_name].value = not io_value
    
    def stop_lift(self,msg="") :
        print('STOP lift','reason :',msg)
        self.enable_lift(False)
    
    def set_lift_angle(self,angle) :
        pass

    def get_lift_angle(self) :
        pass

    def enable_lift(self,bool) : 
        #set first bit of enable_pids register to bool
        self.rpi.io.enable_pids.value = self.rpi.io.enable_pids.value & (bool << 0)

    def enable_belt(self,bool) : 
        #set second bit of enable_pids register to bool
        self.rpi.io.enable_pids.value = self.rpi.io.enable_pids.value & (bool << 1)

    def enable_dist(self,bool) : 
        #set second bit of enable_pids register to bool
        self.rpi.io.enable_pids.value = self.rpi.io.enable_pids.value & (bool << 2)

    def start_belt(self,msg="") :
        print('START belt','reason :',msg)
        self.enable_belt(True)
        self.rpi.io.belt_start.value=1

    def stop_belt(self,msg="") :
        print('STOP belt','reason :',msg)
        self.rpi.io.belt_stop.value=1
        self.enable_belt(False)

    #set belt speed to controller via modbus
    def set_belt_speed(self,Vkmh) :
        Vms = Vkmh / 3.6 
        value = Vms *100 #int is sent to frequency inverter with 0.01 precision
        #int is sent to frequency inverter with 0.01 precision
    
    #return belt spped in km/h
    def get_belt_speed(self) :
        #read modbus value in hundred of m/s 
        value = 0.0 / 100
        #return value in km/h
        return value * 3.6

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

