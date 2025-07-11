# -*- coding: utf-8 -*-
"""
Created on Wed Oct 13 09:42:51 2021

@author: jparent1
"""
import kivy
from kivy.app import App
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.config import Config
from kivy.core.window import Window
from kivy.uix.accordion import Accordion, AccordionItem
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle
from kivy.garden.led import Led
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ObjectProperty, ListProperty, ColorProperty
import controler
import math
import time
from time import strftime, localtime, gmtime, sleep

#force keyboard to be shown
#Config.set('kivy', 'keyboard_mode', 'systemanddock')

def compute_vertical_speed_mh(tilt_degree,belt_speed_kmh):
    return math.sin(math.radians(tilt_degree)) * belt_speed_kmh * 1000

def compute_belt_speed(tilt_degree,vertical_speed_mh):
    return vertical_speed_mh / (math.sin(math.radians(tilt_degree)) * 1000)

def compute_tilt(belt_speed_kmh,vertical_speed_mh) :
    temp = vertical_speed_mh / (belt_speed_kmh*1000)
    return math.degrees(math.asin(temp))

class NumericInput(BoxLayout):
    name = StringProperty("value")
    unit = StringProperty("unit")
    value = NumericProperty(0)
    target = NumericProperty(0)
    min_value = NumericProperty(0)
    max_value = NumericProperty(100)
    increment_list = ListProperty([0.1,1,10])
    auto_update = BooleanProperty(False)
    increment = None
    hidden = BooleanProperty(False)
      
    def set_increment(self,increment) :
        self.increment = increment
    
    def check_increment(self) :
        if self.increment == None :
            self.increment = self.increment_list[1]
            
    def decrease(self) :
        self.check_increment()
        result = self.target - self.increment
        if result >= self.min_value :
            self.target = round(result,1)
        else :
            self.target = self.min_value
            
    def increase(self) :
        self.check_increment()
        result = self.target + self.increment
        if result <= self.max_value :
            self.target = round(result,1)
        else :
            self.target = self.max_value
    
    def slider_change(self,value) :
        self.target = value
    
    def toggle_auto_update(self,state) :
        if state == 'down' :
            self.auto_update = True
        else :
            self.auto_update = False

class NumericInputCompact(BoxLayout) :
    name = StringProperty('value')
    unit = StringProperty('unit')
    value = NumericProperty(0)
    min = NumericProperty(0)
    max = NumericProperty(20)
    step = NumericProperty(1)

    def decrease(self) :
        result = self.value - self.step
        if result < self.min :
            result = self.min
        self.value = result

    def increase(self) : 
        result = self.value + self.step
        if result > self.max :
            result = self.max
        self.value = result


class NumericDisplay(Label):
    name = StringProperty("value")
    unit = StringProperty("unit")
    value = NumericProperty(0)
    target = NumericProperty(0)
    has_target = BooleanProperty(False)

class StatusDisplay(BoxLayout) :
    name = StringProperty("value")
    active = BooleanProperty(False)

    def on_state(self,*args) : 
        instance = args[0]
        value = args[1]
        if value :
            instance.ids.led.state = 'on'
        else :
            instance.ids.led.state = 'off'

class Ramp(BoxLayout) :
    duration_min = NumericProperty(0)
    state = BooleanProperty(False)
    initial_speed = NumericProperty()
    final_speed  = NumericProperty()
    step_speed = NumericProperty()
    step_duration_s = NumericProperty()
    sign = NumericProperty()

    def __init__(self,**kwargs) :
        super(Ramp,self).__init__(**kwargs)
        Clock.schedule_once(self.compute_duration)

    def compute_duration(self,arg) : 
        self.initial_speed = self.ids['start_speed'].value
        self.final_speed = self.ids['stop_speed'].value
        self.step_speed = self.ids['step_speed'].value
        self.step_duration_s = self.ids['step_duration'].value
        self.sign = math.copysign(1,self.final_speed-self.initial_speed)
        paliers = round(abs(self.final_speed-self.initial_speed)/self.step_speed)+1
        self.duration_min = (paliers * self.step_duration_s ) / 60
    
    def toggle_state(self,active) :
        self.state = active

class LeMurApp(App):
    #revpi reference
    revpi = None
    #UI properties
    belt_speed_target = NumericProperty(2.5)
    belt_speed_value = NumericProperty(0)
    tilt_target = NumericProperty(27.5)
    tilt_value = NumericProperty(0)
    vertical_speed_target = NumericProperty(1000)
    vertical_speed_value = NumericProperty()
    elapsed_time = NumericProperty(0)
    elapsed_distance = NumericProperty(0)
    elapsed_elevation = NumericProperty(0)
    safety_left = BooleanProperty(False)
    safety_right = BooleanProperty(False,rebind=True)
    safety_front = BooleanProperty(False)
    safety_back = BooleanProperty(False)
    any_safety = BooleanProperty(False)
    safety_emergency = BooleanProperty(False)
    steps_active = BooleanProperty(False)
    speed_text = StringProperty("Vitesse bande")
    steps_background_color = ColorProperty([0, 0, 0,1])
    #vertical_speed_control
    vertical_speed_mode = 0 #0 = manula, 1 = tilt, 2 = belt speed
    #running properties
    running_event = None
    start_time = 0
    last_time = 0
    #ramp properties
    event_ramp = None
    #status widgets
    steps_widget = StatusDisplay(name="Marches",active=steps_active)
    safety_F_widget = safety_B_widget = safety_L_widget = safety_R_widget = safety_E_widget = ObjectProperty(None)
    
    #overcharge init to define rpi instance
    def __init__(self, revpi, **kwargs):
        super(LeMurApp,self).__init__(**kwargs)
        self.revpi = revpi

    def build(self):
        Clock.schedule_interval(self.update_values,0.1)
        if self.revpi :
            self.tilt_target = self.revpi.get_lift_angle()
        self.change_belt_speed()

    def on_stop(self):
        print('bye bye')
        if self.revpi :
            self.rpi.stop_all()

    def move_lift(self,_=None) :
        Logger.info("Tilt target updated : " + str(self.tilt_target))
        if self.revpi :
            self.revpi.set_lift_angle(self.tilt_target)
        else :
            self.tilt_value = self.tilt_target
            
    
    def change_belt_speed(self,_=None) :
        Logger.info("belt speed target updated : " + str(self.belt_speed_target))

        if self.revpi :
            self.revpi.set_belt_speed(self.belt_speed_target)
        else :
            self.belt_speed_value = self.belt_speed_target
    
    def toggle_steps(self,active) :
        color = [0, 0, 0]
        self.steps_background_color = [0, 0, 0,1]
        self.speed_text = "Vitesse bande"
        if active :
            color = [204/255, 82/255, 0/255]
            self.steps_background_color = [204/255, 82/255, 0/255,1]
            self.speed_text = "Vitesse marches"

        #update belt speed according to new status
        self.steps_active = active

        #change background color
        #with self.root.ids['steps_grid'].canvas.before:
        #    Color(color[0], color[1], color[2], 1)
        #    Rectangle(pos=self.root.ids['steps_grid'].pos, size=self.root.ids['steps_grid'].size)
    
    def init_ramp(self,start_speed) :
        #lock tilt screen
        self.root.ids['tilt'].locked = True
        #set initial speed
        self.root.ids['belt_speed'].value = start_speed
        #move lift to initial value
        self.move_lift(0)
    
    def update_ramp(self,dt)  :
        #cancel event scheduling if ramp is over
        ramp = self.root.ids['ramp']
        belt_speed = self.root.ids['belt_speed'].value
        if  (belt_speed >= ramp.final_speed and ramp.sign > 0) or (belt_speed <= ramp.final_speed and ramp.sign < 0) :
            if self.event_ramp : 
                Clock.unschedule(self.event_ramp)
                Clock.schedule_once(self.stop)
                return 
        #update 
        self.root.ids['belt_speed'].value += self.root.ids['ramp'].sign * self.root.ids['ramp'].step_speed
        Clock.schedule_once(self.move_lift)
    
    def update_values(self,_) :
        if self.revpi :
            #safety
            self.safety_right = self.revpi.rpi.io.secu_right.value
            self.safety_left = self.revpi.rpi.io.secu_left.value
            self.safety_front = self.revpi.rpi.io.secu_front.value
            self.safety_back = self.revpi.rpi.io.secu_back.value
            self.safety_emergency = self.revpi.rpi.io.secu_emergency.value
            self.any_safety = self.safety_right or self.safety_left or self.safety_front or self.safety_back or self.safety_emergency
            #real time value
            self.tilt_value = self.revpi.get_lift_angle()
            self.belt_speed_value = self.revpi.get_belt_speed(self.steps_active)
            self.vertical_speed_value = compute_vertical_speed_mh(self.tilt_value,self.belt_speed_value)
            #modbus status
            self.revpi.rpi.io.use_steps.value = self.steps_active   #send steps status to modbus
            #copy encoder feedback to VFD PID disable (inverted logic) pin
            self.revpi.rpi.io.belt_pid_enable.value = self.revpi.rpi.io.encoder_feedback.value

        else :
            self.vertical_speed_value = compute_vertical_speed_mh(self.tilt_value,self.belt_speed_value)
            self.any_safety = False
        
        #update speed target
        #self.change_belt_speed()
    
    def update_running(self,_) :

        self.elapsed_time = time.time() - self.start_time
        delta_t = time.time() - self.last_time
        self.elapsed_distance += (self.belt_speed_value * 1000 / 3600) * delta_t
        self.elapsed_elevation += (self.vertical_speed_value / 3600) * delta_t
        self.last_time = time.time()

    def start(self) :
        stop_widget = self.root.ids['controller'].ids['stop']
        start_widget = self.root.ids['controller'].ids['start']
        if start_widget.state == 'down' :
            self.running_event = Clock.schedule_interval(self.update_running,0.1)
            stop_widget.state = 'normal'
            start_widget.state = 'down'
            self.start_time = time.time()
            self.last_time = time.time()
            self.elapsed_time = 0
            self.elapsed_distance = 0
            self.elapsed_elevation = 0
            if self.revpi :
                self.revpi.start_belt()
        else :
            start_widget.state = 'down'
        #if self.root.ids['ramp'].state :
        #    self.event_ramp = Clock.schedule_interval(self.update_ramp,self.root.ids['ramp'].step_duration_s)
    
    def stop(self) :
        stop_widget = self.root.ids['controller'].ids['stop']
        start_widget = self.root.ids['controller'].ids['start']
        if stop_widget.state == 'down' :
            stop_widget.state = 'down'
            start_widget.state = 'normal'
            if self.revpi :
                self.revpi.stop_belt()
            if self.running_event :
                self.running_event.cancel()
        else :
            stop_widget.state = 'down'
        #if self.root.ids['ramp'].state :
        #    if self.event_ramp : 
        #        self.event_ramp.cancel()

    def update_targets(self,instance,manual=False) :
        if self.vertical_speed_mode == 0 :  #vertical speed in manual mode
            #update tilt
            if instance == self.root.ids['tilt'] :
                self.tilt_target = instance.target
                if instance.auto_update or manual :
                    self.move_lift()
            #update belt speed
            if instance == self.root.ids['belt_speed'] :
                self.belt_speed_target = instance.target
                if instance.auto_update or manual:
                    self.change_belt_speed()
            #update and compute vertical speed
            self.vertical_speed_target = compute_vertical_speed_mh(self.tilt_target,self.belt_speed_target)
        
        if self.vertical_speed_mode == 1 :  #vertical speed in tilt mode
            #update tilt
            if instance == self.root.ids['tilt'] :
                if instance.value == 0 :
                    instance.value = 0.01
                #compute belt speed target to check for max value
                belt_speed_target = compute_belt_speed(instance.target,self.vertical_speed_target)
                if belt_speed_target > self.root.ids['belt_speed'].max_value:
                    instance.target = compute_tilt(self.root.ids['belt_speed'].max_value,self.vertical_speed_target)
                    pass
                self.tilt_target = instance.target
                #compute acutal belt speed target
                #belt_speed_target = compute_belt_speed(instance.value,self.vertical_speed_target)
                self.belt_speed_target = compute_belt_speed(self.tilt_target,self.vertical_speed_target)
                if instance.auto_update or manual :
                    self.move_lift()
                    self.change_belt_speed()
            #update vertical speed
            if instance == self.root.ids['vertical_speed'] :
                #compute belt speed target to check for max value
                belt_speed_target = compute_belt_speed(self.tilt_target,instance.target)
                if belt_speed_target > self.root.ids['belt_speed'].max_value :
                    instance.target = compute_vertical_speed_mh(self.tilt_target,self.root.ids['belt_speed'].max_value)
                    pass
                self.vertical_speed_target = instance.target
                #compute acutal belt speed target
                #belt_speed_target = compute_belt_speed(self.tilt_target,instance.value)
                self.belt_speed_target = compute_belt_speed(self.tilt_target,self.vertical_speed_target)
                if self.root.ids['vertical_speed'].auto_update or manual:
                    self.change_belt_speed()
            
            #update and compute belt speed
            #belt_speed_target = compute_belt_speed(self.tilt_target,self.vertical_speed_target)
            #self.belt_speed_target = belt_speed_target
            #if instance == self.root.ids['vertical_speed'] :
            #    if self.root.ids['vertical_speed'].auto_update or manual:
            #        self.change_belt_speed()
            #if instance == self.root.ids['tilt'] :
            #    if self.root.ids['tilt'].auto_update or manual:
            #        self.change_belt_speed()
        
        if self.vertical_speed_mode == 2 :  #vertical speed in belt speed mode
            #update belt speed
            if instance == self.root.ids['belt_speed'] :
                #check for 0 value to avoid divition by 0 in temp
                if instance.target == 0 :
                    instance.target = 0.1
                temp = self.vertical_speed_target / (instance.target*1000)
                #asin(x) x is in the range [-1, 1]
                #no need to check for negative value since spped are positive
                if temp > 1 :
                    instance.target = self.vertical_speed_target / 1000  #then temp is 1
                #compute estimated tilt
                tilt_target = compute_tilt(instance.target,self.vertical_speed_target)
                #check for max value
                if tilt_target > self.root.ids['tilt'].max_value :
                    instance.target = compute_belt_speed(self.root.ids['tilt'].max_value,self.vertical_speed_target)
                #check for min value    
                if tilt_target < self.root.ids['tilt'].min_value :
                    instance.target = compute_belt_speed(self.root.ids['tilt'].min_value,self.vertical_speed_target)
                #apply value
                self.belt_speed_target = instance.target
                #move if applicable
                if instance.auto_update or manual:
                    self.change_belt_speed()
            #update vertical speed
            if instance == self.root.ids['vertical_speed'] :
                #check for 0 value to avoid divition by 0 in temp
                temp = instance.target / (self.belt_speed_target*1000)
                #asin(x) x is in the range [-1, 1]
                #no need to check for negative value since spped are positive
                if temp > 1 :
                    instance.target = self.belt_speed_target * 1000  #then temp is 1
                #compute estimated tilt
                tilt_target = compute_tilt(self.belt_speed_target,instance.target)
                #check for max value
                if tilt_target > self.root.ids['tilt'].max_value :
                    instance.target = compute_vertical_speed_mh(self.root.ids['tilt'].max_value,self.belt_speed_target)
                #check for min value
                if tilt_target < self.root.ids['tilt'].min_value :
                    instance.target = compute_vertical_speed_mh(self.root.ids['tilt'].min_value,self.belt_speed_target)
                #apply value
                self.vertical_speed_target = instance.target
            
            #compute tilt
            tilt_target = compute_tilt(self.belt_speed_target,self.vertical_speed_target)
            #set tilt to UI
            self.root.ids['tilt'].target = tilt_target
            #set tilt to backend
            self.tilt_target = tilt_target
            #move if applicable
            if self.root.ids['vertical_speed'].auto_update or manual:
                self.move_lift()   
    
    def mode_changed(self,instance) :
        if instance.state == 'down' :
            if instance.text == "Aucun" :
                self.root.ids.tilt.hidden = False
                self.root.ids.belt_speed.hidden = False
                self.root.ids.vertical_speed.hidden = True
                self.vertical_speed_mode = 0
            if instance.text == "Inclinaison" :
                self.root.ids.tilt.hidden = False
                self.root.ids.belt_speed.hidden = True
                self.root.ids.vertical_speed.hidden = False
                self.root.ids.belt_speed.auto_update = True #force auto update on speed ! compute speed based on real time tilt
                self.vertical_speed_mode = 1
            if instance.text == "Vitesse tapis" :
                self.root.ids.tilt.hidden = True
                self.root.ids.belt_speed.hidden = False
                self.root.ids.vertical_speed.hidden = False
                self.root.ids.tilt.auto_update = True #force auto update on tilt ! compute speed based on real time speed
                self.vertical_speed_mode = 2
            Logger.info("UI : Mode changed : "+instance.text)
 
if __name__ == '__main__':
    if controler.is_raspberry_pi() : 
        lemur = controler.revPI()
        lemur.mainloop()
    else :
        print("I am a PC")
        lemur = None
    LeMurApp(lemur).run()