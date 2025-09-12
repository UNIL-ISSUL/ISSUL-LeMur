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
from kivy.uix.screenmanager import ScreenManager
from utils.treadmill_layout import TreadmillLayout



from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ObjectProperty, ListProperty, ColorProperty
#import controler
import hardware
import treadmill
from treadmill import compute_vertical_speed_mh, compute_belt_speed, compute_tilt
from incremental_widget import IncrementalWidget
import math
import time
from time import strftime, localtime, gmtime, sleep

#force keyboard to be shown
#Config.set('kivy', 'keyboard_mode', 'systemanddock')

class MainScreenManager(ScreenManager):
    pass

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

class Controller(BoxLayout):
    font_size = NumericProperty(24)  # valeur par défaut

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
    #manual_widget_ids
    manual_widget_ids = None
    #treadmill Object
    revpi = None
    treadmill_status = ObjectProperty(None) 
    #UI properties
    belt_speed_target = NumericProperty(2.5)
    tilt_target = NumericProperty(27.5)
    vertical_speed_target = NumericProperty(1000)
    #vertical_speed_control
    vertical_speed_mode = 0 #0 = manula, 1 = tilt, 2 = belt speed
    #steps management
    steps_active = BooleanProperty(False)
    speed_text = StringProperty("Vitesse bande")
    steps_background_color = ColorProperty([0, 0, 0,1])
    
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
    def __init__(self, treadmill, **kwargs):
        super(LeMurApp,self).__init__(**kwargs)
        self.treadmill = treadmill
        self.treadmill_status = treadmill.update()

    def build(self):
        #define manual widget ids
        self.screen_manager = self.root.ids.screen_manager
        self.manual_widget_ids = self.screen_manager.ids.manual_widget.ids
        self.incremental_widget = self.screen_manager.ids.incr_widget
        #attach treadmill to widget
        self.incremental_widget.set_treadmill(self.treadmill)
        #attach update event
        Clock.schedule_interval(self.update_values,0.1)
        #update treadmill
        self.treadmill.update()
        self.tilt_target = self.treadmill.get_lift_angle()
        self.change_belt_speed()

    def on_stop(self):
        self.treadmill.shutdown()
        Logger.info(f"Main: on_stop signal received")

    def move_lift(self,_=None) :
        Logger.info("Main : Tilt target updated " + str(self.tilt_target))
        self.treadmill.set_lift_angle(self.tilt_target)

    def change_belt_speed(self,_=None) :
        Logger.info("Main : belt speed target updated " + str(self.belt_speed_target))
        self.treadmill.set_belt_speed(self.belt_speed_target)
    
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
    
    def update_values(self,_) :
        #update incremental widget graph and setpoints if on incremental tab and treadmill is running
        if self.screen_manager.current == 'incremental_tab' and self.treadmill.is_running() :
            #update test return true if test is finished
            test_finished = self.incremental_widget.update_test(0.1)
            if test_finished:
                Logger.info("Main : Test finished")
                self.root.ids.controller.ids.stop.trigger_action()  #stop treadmill if test is done

        #update treadmill status
        self.treadmill_status = self.treadmill.update()
        
        
        if self.revpi :
            #modbus status
            self.revpi.set_steps(self.steps_active)   #send steps status to modbus
            #copy encoder feedback to VFD PID disable (inverted logic) pin
            self.revpi.rpi.io.belt_pid_enable.value = self.revpi.rpi.io.encoder_feedback.value

    def start(self, instance) :
        #configure incremental widget
        if self.screen_manager.current == 'incremental_tab' :
            #reset event if any
            if not self.treadmill.is_paused() :
                self.incremental_widget.delete_event()
        #start treadmill
        if instance.state == 'down' :
            self.treadmill.start()
    
    def pause(self, instance) :
        #pause treadmill
        if instance.state == 'down' :
            self.treadmill.pause()

    def stop(self, instance) :
        #stop treadmill
        if instance.state == 'down' :
            self.treadmill.stop()

    def update_targets(self,instance,manual=False) :
        if self.vertical_speed_mode == 0 :  #vertical speed in manual mode
            #update tilt
            if instance == self.manual_widget_ids.tilt :
                self.tilt_target = instance.target
                if instance.auto_update or manual :
                    self.move_lift()
            #update belt speed
            if instance == self.manual_widget_ids.belt_speed :
                self.belt_speed_target = instance.target
                if instance.auto_update or manual:
                    self.change_belt_speed()
            #update and compute vertical speed
            self.vertical_speed_target = compute_vertical_speed_mh(self.tilt_target,self.belt_speed_target)
        
        if self.vertical_speed_mode == 1 :  #vertical speed in tilt mode
            
            #update tilt
            if instance == self.manual_widget_ids.tilt :
                #compute belt speed target to check for max value
                belt_speed_target = compute_belt_speed(instance.target,self.vertical_speed_target)
                if belt_speed_target == False :
                    return
                if belt_speed_target > self.manual_widget_ids.belt_speed.max_value:
                    target  = compute_tilt(self.manual_widget_ids.belt_speed.max_value,self.vertical_speed_target)
                    if target == False :
                        return
                    instance.target = target
                
                self.tilt_target = instance.target
                #compute acutal belt speed target
                self.belt_speed_target = compute_belt_speed(self.tilt_target,self.vertical_speed_target)
                if instance.auto_update or manual :
                    self.move_lift()
                    self.change_belt_speed()
            #update vertical speed
            if instance == self.manual_widget_ids.vertical_speed :
                #compute belt speed target to check for max value
                belt_speed_target = compute_belt_speed(self.tilt_target,instance.target)
                if belt_speed_target == False :
                    return
                #check for max value
                if belt_speed_target > self.manual_widget_ids.belt_speed.max_value :
                    instance.target = compute_vertical_speed_mh(self.tilt_target,self.manual_widget_ids.belt_speed.max_value)
                self.vertical_speed_target = instance.target
                #compute acutal belt speed target
                #belt_speed_target = compute_belt_speed(self.tilt_target,instance.value)
                self.belt_speed_target = compute_belt_speed(self.tilt_target,self.vertical_speed_target)
                if self.manual_widget_ids.vertical_speed.auto_update or manual:
                    self.change_belt_speed()
    
        
        if self.vertical_speed_mode == 2 :  #vertical speed in belt speed mode
            
            #update belt speed
            if instance == self.manual_widget_ids.belt_speed :
                #compute estimated tilt
                tilt_target = compute_tilt(instance.target,self.vertical_speed_target)
                if tilt_target == False :
                    return
                #check for max value
                if tilt_target > self.manual_widget_ids.tilt.max_value :
                    instance.target = compute_belt_speed(self.manual_widget_ids.tilt.max_value,self.vertical_speed_target)
                #check for min value    
                if tilt_target < self.manual_widget_ids.tilt.min_value :
                    instance.target = compute_belt_speed(self.manual_widget_ids.tilt.min_value,self.vertical_speed_target)
                #apply value
                self.belt_speed_target = instance.target
                    
            #update vertical speed
            if instance == self.manual_widget_ids['vertical_speed'] :
                #compute estimated tilt
                tilt_target = compute_tilt(self.belt_speed_target,instance.target)
                if tilt_target == False :
                    return
                #check for max value
                if tilt_target > self.manual_widget_ids['tilt'].max_value :
                    instance.target = compute_vertical_speed_mh(self.manual_widget_ids['tilt'].max_value,self.belt_speed_target)
                #check for min value
                if tilt_target < self.manual_widget_ids['tilt'].min_value :
                    instance.target = compute_vertical_speed_mh(self.manual_widget_ids['tilt'].min_value,self.belt_speed_target)
                #apply value
                self.vertical_speed_target = instance.target

            self.tilt_target = compute_tilt(self.belt_speed_target,self.vertical_speed_target)
            #move if applicable
            if self.manual_widget_ids['vertical_speed'].auto_update or manual:
                self.move_lift()   
    
    def mode_changed(self,instance) :
        if instance.state == 'down' :
            if instance.text == "Aucun" :
                self.manual_widget_ids.tilt.hidden = False
                self.manual_widget_ids.belt_speed.hidden = False
                self.manual_widget_ids.vertical_speed.hidden = True
                self.vertical_speed_mode = 0
            if instance.text == "Inclinaison" :
                self.manual_widget_ids.tilt.hidden = False
                self.manual_widget_ids.belt_speed.hidden = True
                self.manual_widget_ids.vertical_speed.hidden = False
                self.manual_widget_ids.belt_speed.auto_update = True #force auto update on speed ! compute speed based on real time tilt
                self.vertical_speed_mode = 1
            if instance.text == "Vitesse tapis" :
                self.manual_widget_ids.tilt.hidden = True
                self.manual_widget_ids.belt_speed.hidden = False
                self.manual_widget_ids.vertical_speed.hidden = False
                self.manual_widget_ids.tilt.auto_update = True #force auto update on tilt ! compute speed based on real time speed
                self.vertical_speed_mode = 2
            Logger.info("UI : Mode changed : "+instance.text)
 
if __name__ == '__main__':
    if hardware.is_raspberry_pi() : 
        revpi = hardware.revPI()
        #revpi.mainloop()
        Logger.info("Main.py : Execute on a revpi")
    else :
        Logger.info("Main.py : Execute on a PC")
        revpi = None
    treadmill = treadmill.TreadmillController(revpi)
    LeMurApp(treadmill).run()