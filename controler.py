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

from kivy.logger import Logger

def read_yaml(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

#config dictionary
file = Path(__file__)
config = read_yaml(file.parent/'settings.yaml')

def merge_registers(reg_hsb, reg_lsb) :
    value = (reg_hsb << 16)  + reg_lsb
    return value

def split_value(value) :
    value_hsb = value >> 16
    value_lsb = value & 0xFFFF
    return value_hsb, value_lsb

class revPI() :

    #define running state
    running = False

    def __init__(self) -> None:
        #define RevPiModIO instance
        self.rpi = revpimodio2.RevPiModIO(autorefresh=True)
        #reduce cylce time to 10Hz
        self.rpi.cycletime = 200
        
        #set belt default value
        self.rpi.io.belt_stop.value=1
        self.rpi.io.belt_start.value=0
        self.rpi.io.belt_dir.value=1
        self.running = False
        #set current speed to 
        
        #set lift default value
        self.set_lift_angle(self.get_lift_angle())

        #enable PID
        self.enable_pid(0,True)      

        #set event to create latch function on belt-start and belt_stop
        self.rpi.io.belt_start.reg_timerevent(self.latch_output, 100,edge=revpimodio2.RISING,as_thread=False)    #start is trigger to 0 after 100ms
        self.rpi.io.belt_stop.reg_timerevent(self.latch_output, 100,edge=revpimodio2.FALLING,as_thread=False)    #stop is trigger to 1 after 100ms
        #set event to handle safety input
        self.rpi.io.lift_safety.reg_event(self.stop_all,edge=revpimodio2.FALLING,as_thread=True)
        #close the program properly
        self.rpi.handlesignalend(cleanupfunc=self.stop_all)
    
    def mainloop(self) :
        self.rpi.mainloop(blocking=False)
    
    def stop_all(self) :
        #stop lift
        self.stop_lift("exit program")
        #stop belt
        self.stop_belt("exit program")
        #disable distance PID
        self.enable_pid(2,False)
        #stop cycleloop
        self.rpi.exit()
    
    def latch_output(self,io_name,io_value) :
        #invert io value
        self.rpi.io[io_name].value = not io_value
    
    def stop_lift(self,msg="") :
        print('STOP lift','reason :',msg)
        self.enable_pid(0,False)
    
    def set_lift_angle(self,angle) :
        print(self.rpi.io.pid_enable.value)
        self.rpi.io.lift_angle_SP.value = round(angle * 100)

    def get_lift_angle(self) :
        return float(self.rpi.io.lift_angle_current.value/100)

    def enable_pid(self,index,bool) :
        if bool :
            self.rpi.io.pid_enable.value = self.rpi.io.pid_enable.value | (1 << index)
        else :
            self.rpi.io.pid_enable.value = self.rpi.io.pid_enable.value & ~(1 << index)

    def start_belt(self,msg="") :
        #start only if belt is not running
        if not self.running :
            self.rpi.io.belt_start.value = 1
            self.running = True
            print('START belt','reason :',msg)

    def stop_belt(self,msg="") :
        #stop only if belt is running
        if self.running :
            self.rpi.io.belt_stop.value=0
            self.running = False
            print('STOP belt','reason :',msg)

    #set belt speed to controller via modbus
    def set_belt_speed(self,Vkmh, steps = False) :
        if steps :
            Hz = Vkmh * config['CONV_STEPS2HZ']
        else :
            Hz = Vkmh *  config['CONV_BELT2HZ']
        value = round(Hz * 100) #int is sent to frequency inverter with 0.01 precision
        Logger.info("belt frequency updated : " + str(value))
        self.rpi.io.belt_speed_SP_0.value, self.rpi.io.belt_speed_SP_1.value = split_value(value)
    
    #return belt spped in km/h
    def get_belt_speed(self, steps = False) :
        #read modbus value in hundred of m/s
        value = merge_registers(self.rpi.io.belt_speed_current_0.value,self.rpi.io.belt_speed_current_1.value)
        value = 1.0 * value / 100
        if steps :
            return value * config['CONV_HZ2STEPS']
        else :
            return value * config['CONV_HZ2BELT']
        #return value in km/h
        return value

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

