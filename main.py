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
from kivy.garden.led import Led
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ObjectProperty, ListProperty
import controler
import math
import time
from time import strftime, localtime, gmtime, sleep

#force keyboard to be shown
#Config.set('kivy', 'keyboard_mode', 'systemanddock')

class NumericInput(BoxLayout):
    name = StringProperty("value")
    unit = StringProperty("unit")
    value = NumericProperty(0)
    min_value = NumericProperty(0)
    max_value = NumericProperty(100)
    increment_list = ListProperty([0.1,1,10])
    locked = BooleanProperty(False)
    hidden = BooleanProperty(False)
    increment = None
      
    def set_increment(self,increment) :
        self.increment = increment
    
    def check_increment(self) :
        if self.increment == None :
            self.increment = self.increment_list[1]
            
    def decrease(self) :
        self.check_increment()
        result = self.value - self.increment
        if result >= self.min_value :
            self.value = round(result,1)
        else :
            self.value = self.min_value
            
    def increase(self) :
        self.check_increment()
        result = self.value + self.increment
        if result <= self.max_value :
            self.value = round(result,1)
        else :
            self.value = self.max_value
    
    def slider_change(self,value) :
        self.value = value
    
    def locked_changed(self,instance,value) :
        self.locked = value

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
    belt_speed = NumericProperty(2)
    belt_speed_out = NumericProperty(0)
    tilt = NumericProperty(0)
    tilt_out = NumericProperty(0)
    vertical_speed = NumericProperty()
    elapsed_time = NumericProperty(0)
    elapsed_distance = NumericProperty(0)
    elapsed_elevation = NumericProperty(0)
    safety_left = BooleanProperty(False)
    safety_right = BooleanProperty(False,rebind=True)
    safety_front = BooleanProperty(False)
    safety_back = BooleanProperty(False)
    safety_emergency = BooleanProperty(False)

    revpi = None
    start_time = 0.0
    delta_update_s = 0.1
    running = False
    event_ramp = None
    
    #overcharge init to define rpi instance
    def __init__(self, revpi, **kwargs):
        super(LeMurApp,self).__init__(**kwargs)
        self.revpi = revpi

    def build(self):
        Clock.schedule_interval(self.update_running,self.delta_update_s)
        Clock.schedule_interval(self.update_values,0.1)
        if self.revpi :
            self.tilt = self.revpi.get_lift_angle()
            self.tilt_out = self.revpi.get_lift_angle()
    
    def on_stop(self):
        print('bye bye')
        self.rpi.stop_all()

    def move_lift(self,dt) :
        if self.revpi :
            self.revpi.set_lift_angle(self.tilt)
    
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
            #real time value
            self.tilt_out = self.revpi.get_lift_angle()
            self.belt_speed_out = self.revpi.get_belt_speed()
    
    def update_running(self,_) :
        if self.revpi :
            #update revpi variables
            self.revpi.set_belt_speed(self.belt_speed)

        if self.running : 
            self.elapsed_time += self.delta_update_s
            self.elapsed_distance += (self.belt_speed * 1000 / 3600) * self.delta_update_s
            self.elapsed_elevation += (self.vertical_speed / 3600) * self.delta_update_s

    def start(self) :
        stop_widget = self.root.ids['controller'].ids['stop']
        start_widget = self.root.ids['controller'].ids['start']
        if start_widget.state == 'normal' :
            stop_widget.state = 'normal'
            start_widget.state = 'down'
        self.running = True
        self.elapsed_time = 0
        self.elapsed_distance = 0
        self.elapsed_elevation = 0
        if self.revpi :
            self.revpi.start_belt()
        if self.root.ids['ramp'].state :
            self.event_ramp = Clock.schedule_interval(self.update_ramp,self.root.ids['ramp'].step_duration_s)
    
    def stop(self) :
        stop_widget = self.root.ids['controller'].ids['stop']
        start_widget = self.root.ids['controller'].ids['start']
        if stop_widget.state == 'normal' :
            stop_widget.state = 'down'
            start_widget.state = 'normal'
        self.running = False
        if self.revpi :
            self.revpi.stop_belt()
        if self.root.ids['ramp'].state :
            if self.event_ramp : 
                self.event_ramp.cancel()

    def update_parameters(self,instance) :
        #get locked id to compute parameters
        locked_id = None
        current_id = None
        list = ['tilt','belt_speed','vertical_speed']        
        
        for id in list :
            widget = self.root.ids[id]
            if widget.locked :
                locked_id = id
            if widget == instance :
                current_id = id

        if current_id == 'tilt':
            self.tilt = instance.value 
        if current_id == 'belt_speed':
            self.belt_speed = instance.value 
        if current_id == 'vertical_speed':
            self.vertical_speed = instance.value 

        if locked_id == 'tilt' : 
            self.update_tilt(current_id)
        if locked_id == 'belt_speed' :
            self.update_belt_speed(current_id)
        if locked_id == 'vertical_speed' :
            self.update_vertical_speed(current_id)

    
    def mode_changed(self,instance) :

        if instance.state == 'down' :
            if instance.text == "Manuel" :
                self.root.ids.tilt.hidden = False
                self.root.ids.belt_speed.hidden = False
                self.root.ids.vertical_speed.hidden = False
                self.root.ids.vertical_speed.locked = True
            if instance.text == "Rampe" :
                self.root.ids.tilt.hidden = False
                self.root.ids.belt_speed.hidden = False
                self.root.ids.vertical_speed.hidden = False
                self.root.ids.belt_speed.locked = True
            if instance.text == "Protocole" :
                self.root.ids.tilt.hidden = True
                self.root.ids.belt_speed.hidden = True
                self.root.ids.vertical_speed.hidden = True
            Logger.info("UI : Mode changed : "+instance.text)

    def compute_vertical_speed(self):
        return math.sin(math.radians(self.tilt)) * self.belt_speed * 1000
    
    def compute_belt_speed(self):
        if self.tilt == 0 :
            self.tilt = self.root.ids.tilt.min_value + 0.1
        return self.vertical_speed / (math.sin(math.radians(self.tilt)) * 1000)

    def update_vertical_speed(self,id):
        result = self.compute_vertical_speed()
        if result > self.root.ids.vertical_speed.max_value :
            if id == 'tilt' :
                self.tilt = math.degrees(math.asin(self.root.ids.vertical_speed.max_value / (self.belt_speed*1000)))
            if id == 'belt_speed' :
                self.belt_speed = self.root.ids.vertical_speed.max_value / (math.sin(math.radians(self.tilt)) * 1000 )

        self.vertical_speed = self.compute_vertical_speed()
        Logger.info("UI : Vertical speed updated : "+str(self.vertical_speed))
    
    def update_belt_speed(self,id):
        result = self.compute_belt_speed()
        if result > self.root.ids.belt_speed.max_value :
            if id == 'tilt' :
                self.tilt = math.degrees(math.asin(self.vertical_speed / (self.root.ids.belt_speed.max_value*1000)))
            if id == 'vertical_speed' :
                self.vertical_speed = math.sin(math.radians(self.tilt)) * self.root.ids.belt_speed.max_value * 1000
        self.belt_speed = self.vertical_speed / (math.sin(math.radians(self.tilt)) * 1000)
        Logger.info("UI : Belt speed updated : "+str(self.belt_speed))
    
    def update_tilt(self,id) : 
        if self.belt_speed == 0 :
            self.belt_speed = self.root.ids.belt_speed.min_value + 0.1
        temp = self.vertical_speed / (self.belt_speed*1000)
        #asin(x) x is in the range [-1, 1]
        #no need to check for negative value since spped are positive
        if temp > 1 :
            if id == 'belt_speed' :
                self.belt_speed = self.vertical_speed / 1000
            if id == 'vertical_speed' :
                self.vertical_speed = self.belt_speed*1000

        self.tilt = math.degrees(math.asin(self.vertical_speed / (self.belt_speed*1000)))
        Logger.info("UI : Tilt updated : "+str(self.tilt))
    
if __name__ == '__main__':
    if controler.is_raspberry_pi() : 
        lemur = controler.revPI()
        lemur.mainloop()
    else :
        lemur = None
    LeMurApp(lemur).run()