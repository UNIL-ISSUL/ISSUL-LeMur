#Gestion du tapis de course
#Calcul du elapsed time de start,stop, pause, resume
#Calul de la distance parcourue, du dénivelé
from time import time
try:
    from kivy.logger import Logger
except ImportError:
    import logging
    Logger = logging.getLogger("treadmill")
import math
from random import random

def compute_vertical_speed_mh(tilt_degree,belt_speed_kmh):
    return math.sin(math.radians(tilt_degree)) * belt_speed_kmh * 1000

def compute_belt_speed(tilt_degree,vertical_speed_mh):
     #avoid div by 0
    if tilt_degree == 0:
        Logger.warning("Treadmill: compute_belt_speed : tilt is 0, cannot compute belt speed")
        return 0
    return vertical_speed_mh / (math.sin(math.radians(tilt_degree)) * 1000)

#return False if belt_speed_kmh is 0 else return tilt in degrees
def compute_tilt(belt_speed_kmh,vertical_speed_mh) :
    #check for 0 value to avoid divition by 0 in temp
    if belt_speed_kmh == 0:
        Logger.warning("Treadmill: compute_tilt : belt speed is 0, cannot compute tilt")
        return False
    temp = vertical_speed_mh / (belt_speed_kmh*1000)
    #asin(x) x is in the range [-1, 1]
    #no need to check for negative value since speeds are positive
    if temp > 1 or temp < -1:
        Logger.warning("Treadmill: compute_tilt : vertical speed is higher than belt speed, cannot compute tilt, asin > 1")
        return False
    return math.degrees(math.asin(temp))

def add_noise(value, noise_level=0.01):
    noise = noise_level * value * (2 * (0.5 - random()))
    return float(value + noise)

def split_value(value):
    val_int = int(round(value))
    value_hsb = (val_int >> 16) & 0xFFFF
    value_lsb = val_int & 0xFFFF
    return value_hsb, value_lsb


def describe_modbus_status(code):
    """Return a human-readable interpretation of Kunbus RevPi Modbus Action Status code."""
    if code is None:
        return "Non configuré"
    try:
        c = int(code)
    except (ValueError, TypeError):
        return str(code)

    if c == 0:
        return "OK"
    elif c == 110:
        return "Timeout réponse variateur (110)"
    elif c == 17:
        return "Liaison série / port occupé (17)"
    elif c == 1:
        return "Fonction non supportée (1)"
    elif c == 2:
        return "Adresse registre invalide (2)"
    elif c == 3:
        return "Valeur registre invalide (3)"
    elif c == 4:
        return "Défaut matériel esclave (4)"
    elif c == 6:
        return "Esclave occupé (6)"
    elif c == 104:
        return "Connexion réinitialisée (104)"
    elif c == 255:
        return "Erreur communication générique (255)"
    else:
        return f"Défaut communication ({c})"


import os
import csv
from datetime import datetime
import queue
import threading
from time import sleep
import collections
import yaml
from pathlib import Path

#READ CONFIGURATION FILE
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def read_yaml(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

#Read config dictionary in current folder
file = Path(__file__)
config = read_yaml(file.parent/'treadmill.yaml')

class TreadmillController:
    # variables
    lift_angle_SP = 0
    lift_angle_PV = 0
    belt_speed_SP = 0
    belt_speed_PV = 0
    vertical_speed_PV = 0
    belt_direction = True
    steps_active = False
    safeties = {
        "top": True,
        "bottom": True,
        "left": True,
        "right": True,
        "emergency": True
    }
    treadmill_points = None

    running = False
    paused = False

    def __init__(self, hardware):
        self.hardware = hardware
        
        # Load configuration first
        config_path = Path(__file__).parent / 'treadmill.yaml'
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        else:
            config = {}
        
        self.default_surface = config.get('default_surface', 'belt')
        self.steps_active = (self.default_surface == 'steps-bars')
        if self.hardware and hasattr(self.hardware, 'set_steps'):
            self.hardware.set_steps(self.steps_active)
        
        self.belt_acc = config.get('BELT_ACC', 0)
        self.current_speed_command = 0
        self.test_name = "manual_test"
        self.subject_name = "sujet"
        # Event and log features
        self.event_list = []
        self.event_file = None
        self.log_event = False
        self.log_file = None
        self.log_writer = None
        self.log_folder = os.path.join(os.path.dirname(__file__), 'log')
        self.event_folder = os.path.join(os.path.dirname(__file__), 'events')
        os.makedirs(self.log_folder, exist_ok=True)
        os.makedirs(self.event_folder, exist_ok=True)
        # Thread-safe queue for logging
        self.log_queue = queue.Queue()
        self.log_thread = None
        self.stop_logging_thread = threading.Event()
        # Belt drift compensation (slow integral controller + low-pass filter)
        self.max_drift_pct = config.get('max_drift_pct', 25)
        self.kp = config.get('belt_kp', 0.0)
        self.drift_tau = config.get('drift_tau_s', None)
        if self.drift_tau is not None and self.drift_tau > 0:
            self.ki = 1.0 / self.drift_tau
        else:
            self.ki = config.get('belt_ki', 0.04)
            self.drift_tau = 1.0 / self.ki if self.ki > 0 else 25.0
        self.drift_filter_tau = config.get('drift_filter_tau_s', 3.0)
        self.integrale_drift = 0.0
        self.belt_speed_PV_filtered = None
        self.drift_pct = 0.0
        # Diagnostic tracking and event history
        self.diagnostic_log = collections.deque(maxlen=100)
        self._last_diagnostic_states = {}
        self.modbus_auto_recovery_enabled = True
        self.modbus_auto_reset_count = 0
        self._last_modbus_auto_reset_time = 0.0
        self._modbus_error_streak = 0
        if self.hardware and hasattr(self.hardware, 'get_io_value'):
            self._last_diagnostic_states["belt_stop"] = bool(self.hardware.get_io_value("belt_stop", False))
            self._last_diagnostic_states["belt_start"] = bool(self.hardware.get_io_value("belt_start", False))
            self._last_diagnostic_states["Modbus_Action_Status_1"] = self.hardware.get_io_value("Modbus_Action_Status_1", 0)
        self.log_diagnostic("TreadmillController initialisé", level="info")
        self.reset_variables()

    def log_diagnostic(self, msg, level="info"):
        """Record a diagnostic event for real-time telemetry display."""
        now_str = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        entry = {
            "time": now_str,
            "msg": msg,
            "level": level
        }
        self.diagnostic_log.appendleft(entry)
        if level == "warning":
            Logger.warning(f"Treadmill Diag: {msg}")
        elif level == "error":
            Logger.error(f"Treadmill Diag: {msg}")
        else:
            Logger.info(f"Treadmill Diag: {msg}")

    def _log_worker(self):
        """Worker thread for writing logs to file."""
        Logger.info("Treadmill: Log worker thread started.")
        while not self.stop_logging_thread.is_set():
            try:
                # Wait for a log entry, with a timeout to allow checking the stop signal
                log_data = self.log_queue.get(timeout=0.1)
                if log_data is None:  # Sentinel value to stop
                    break
                if self.log_writer:
                    self.log_writer.writerow(log_data)
                    # Flush occasionally, not on every write
                    if self.log_queue.qsize() == 0:
                        self.log_file.flush()
                self.log_queue.task_done()
            except queue.Empty:
                continue
        Logger.info("Treadmill: Log worker thread stopped.")

    def record_event(self, event_name=None):
        """Record an event with the current elapsed time and optional name."""
        now = datetime.now()
        event = {
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'time': self.elapsed_time,
            'belt_speed_SP': self.belt_speed_SP,
            'belt_speed_CMD': round(getattr(self, 'commande_finale', 0.0), 3),
            'belt_speed_PV': self.belt_speed_PV,
            'lift_angle_SP': self.lift_angle_SP,
            'lift_angle_PV': self.lift_angle_PV,
            'vertical_speed_SP': compute_vertical_speed_mh(self.lift_angle_SP, self.belt_speed_SP),
            'vertical_speed_PV': self.vertical_speed_PV,
            'distance_m': self.distance_m,
            'elevation_pos_m': self.elevation_pos_m,
            'elevation_neg_m': self.elevation_neg_m,
            'drift_pct': round(self.drift_pct, 2),
            'event': event_name,
        }
        # Append to in-memory list
        self.event_list.append(event)
        #toggle log event
        self.log_event = True
        # Write to event file if open
        if self.event_file:
            # Check if the file is empty to write headers
            is_new_file = self.event_file.tell() == 0
            fieldnames = ['datetime', 'time', 'belt_speed_SP', 'belt_speed_CMD', 'belt_speed_PV', 'lift_angle_SP', 'lift_angle_PV', 'vertical_speed_SP', 'vertical_speed_PV', 'distance_m', 'elevation_pos_m', 'elevation_neg_m', 'drift_pct', 'event']
            writer = csv.DictWriter(self.event_file, fieldnames=fieldnames)
            if is_new_file:
                writer.writeheader()
            writer.writerow(event)
            self.event_file.flush()

    def _open_event_file(self):
        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d-%H%M%S-%f')
        event_folder = os.path.join(self.event_folder, now.strftime('%Y'), now.strftime('%m'), now.strftime('%d'))
        os.makedirs(event_folder, exist_ok=True)
        event_path = os.path.join(event_folder, f'{now_str}_{self.subject_name}_{self.test_name}-events.csv')

        # Open in append mode and write header only if the file is new
        file_exists = os.path.exists(event_path)
        self.event_file = open(event_path, 'a', newline='')
        if not file_exists:
            fieldnames=['datetime', 'time', 'belt_speed_SP', 'belt_speed_CMD', 'belt_speed_PV', 'lift_angle_SP', 'lift_angle_PV', 'vertical_speed_SP', 'vertical_speed_PV', 'distance_m', 'elevation_pos_m', 'elevation_neg_m', 'drift_pct', 'event']
            writer = csv.DictWriter(self.event_file, fieldnames=fieldnames)
            writer.writeheader()
            self.event_file.flush()


    def _close_event_file(self):
        if self.event_file:
            self.event_file.close()
            self.event_file = None

    def _open_log_file(self):
        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d-%H%M%S-%f')
        log_folder = os.path.join(self.log_folder, now.strftime('%Y'), now.strftime('%m'), now.strftime('%d'))
        os.makedirs(log_folder, exist_ok=True)
        log_path = os.path.join(log_folder, f'{now_str}_{self.subject_name}_{self.test_name}-log.csv')
        self.log_file = open(log_path, 'w', newline='')
        self.log_writer = csv.DictWriter(self.log_file, fieldnames=[
            'datetime', 'time', 'belt_speed_SP', 'belt_speed_CMD', 'belt_speed_PV', 'lift_angle_SP', 'lift_angle_PV', 'vertical_speed_SP', 'vertical_speed_PV', 'distance_m', 'elevation_pos_m', 'elevation_neg_m', 'drift_pct', 'event'
        ])
        self.log_writer.writeheader()
        # Start the logging thread
        self.stop_logging_thread.clear()
        self.log_thread = threading.Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()

    def _close_log_file(self):
        if self.log_thread and self.log_thread.is_alive():
            # Signal the thread to stop and wait for it to process the queue
            self.log_queue.put(None)
            self.log_thread.join(timeout=2) # Wait for max 2 seconds
            self.stop_logging_thread.set()


        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.log_writer = None

    def reset_variables(self):
        self.distance_m = 0
        self.elevation_pos_m = 0
        self.elevation_neg_m = 0
        self.elapsed_time = 0
        self.start_time = 0
        self.pause_time = 0
        self.elapsed_pause_time = 0
        self.last_update_time = 0
        self.current_speed_command = 0
        self.commande_finale = 0.0
        self._stall_warning_counter = 0
        self._last_raw_speed = None
        self.treadmill_points = collections.deque(maxlen=16200) # 90 minutes of data at 3Hz
        self.event_list = []
        self.update_counter = 0
        self.integrale_drift = 0.0
        self.belt_speed_PV_filtered = None
        self.drift_pct = 0.0

    def update(self):
        #update PV
        if self.hardware:
            self.lift_angle_PV = self.hardware.get_lift_angle()
            raw_speed = self.hardware.get_belt_speed()
            # Glitch filter on raw encoder speed (max physically plausible acceleration < 5.0 km/h in 100ms)
            if self.is_running() and self._last_raw_speed is not None:
                if abs(raw_speed - self._last_raw_speed) > 5.0:
                    Logger.warning(f"Treadmill: Glitch encodeur aberrant ignoré: {raw_speed:.2f} km/h (conservé: {self._last_raw_speed:.2f} km/h)")
                    raw_speed = self._last_raw_speed
            self._last_raw_speed = raw_speed
            self.belt_speed_PV = raw_speed
            self.safeties = self.hardware.get_safeties()
            self.belt_direction = self.hardware.get_belt_direction()

            # Diagnostic IO transition tracking
            if hasattr(self.hardware, 'get_io_value'):
                curr_stop = bool(self.hardware.get_io_value("belt_stop", False))
                prev_stop = self._last_diagnostic_states.get("belt_stop")
                if prev_stop is not None and prev_stop != curr_stop:
                    self.log_diagnostic(
                        f"Sortie belt_stop: {prev_stop} -> {curr_stop} ({'RUN Permis' if curr_stop else 'ARRÊT Actif / Coupure'})",
                        level="warning" if not curr_stop else "info"
                    )
                self._last_diagnostic_states["belt_stop"] = curr_stop

                curr_start = bool(self.hardware.get_io_value("belt_start", False))
                prev_start = self._last_diagnostic_states.get("belt_start")
                if prev_start is not None and prev_start != curr_start:
                    self.log_diagnostic(
                        f"Sortie belt_start: {prev_start} -> {curr_start} ({'Impulsion Start' if curr_start else 'Fin impulsion'})",
                        level="info"
                    )
                self._last_diagnostic_states["belt_start"] = curr_start

                curr_m1 = self.hardware.get_io_value("Modbus_Action_Status_1", 0)
                prev_m1 = self._last_diagnostic_states.get("Modbus_Action_Status_1")
                if prev_m1 is not None and prev_m1 != curr_m1:
                    lvl = "error" if (curr_m1 and curr_m1 > 0) else "info"
                    desc_curr = describe_modbus_status(curr_m1)
                    self.log_diagnostic(f"Modbus Action 1: {prev_m1} -> {curr_m1} ({desc_curr})", level=lvl)
                self._last_diagnostic_states["Modbus_Action_Status_1"] = curr_m1

                # Modbus Auto-Recovery Watchdog
                if curr_m1 is not None and curr_m1 > 0:
                    self._modbus_error_streak += 1
                    now_ts = time()
                    if (self.modbus_auto_recovery_enabled and 
                        self.running and not self.paused and 
                        (now_ts - self._last_modbus_auto_reset_time) >= 1.5):
                        self._last_modbus_auto_reset_time = now_ts
                        self.modbus_auto_reset_count += 1
                        self.reset_modbus()
                        desc = describe_modbus_status(curr_m1)
                        self.log_diagnostic(
                            f"[AUTO-RÉCUPÉRATION] Acquittement Modbus auto envoyé (code {curr_m1}: {desc})",
                            level="warning"
                        )
                else:
                    self._modbus_error_streak = 0
        #When there is no hardware : PV set to setpoint and 1% of random noise
        else:
            self.lift_angle_PV = add_noise(self.lift_angle_SP, noise_level=0.001)
            if self.running and not self.paused:
                #simulate acceleration
                step = 0.2
                if self.belt_speed_PV < self.belt_speed_SP:
                    self.belt_speed_PV += min(step, self.belt_speed_SP - self.belt_speed_PV)
                elif self.belt_speed_PV > self.belt_speed_SP:
                    self.belt_speed_PV -= min(step, self.belt_speed_PV - self.belt_speed_SP)
                self.belt_speed_PV = add_noise(self.belt_speed_PV)
            else:
                self.belt_speed_PV = 0
            #unlock safeties
            self.safeties = {"top": False,"bottom": False,"left": False,"right": False,"emergency": False }
        #compute vertical speed
        self.vertical_speed_PV = compute_vertical_speed_mh(self.lift_angle_PV,self.belt_speed_PV)

        #update running value
        if self.is_running():
            # Downsample data for the live graph (3Hz)
            self.update_counter += 1
            if self.update_counter % 3 == 0:
                #store treadmill points
                self.treadmill_points.append({
                    'time': self.elapsed_time,
                    'speed': self.belt_speed_PV,
                    'incl': self.lift_angle_PV,
                    'asc': self.vertical_speed_PV
                })

            #update elapsed time
            current_time = time()
            #init time if first loop
            if self.last_update_time == 0:
                self.last_update_time = current_time

            self.elapsed_time = current_time - self.start_time - self.elapsed_pause_time
            delta_time = current_time - self.last_update_time
            
            if delta_time > 0:
                # 1. Low-pass filter on measured belt speed (removes stride/foot contact oscillations)
                if self.belt_speed_PV_filtered is None:
                    self.belt_speed_PV_filtered = self.belt_speed_PV
                else:
                    alpha = delta_time / (self.drift_filter_tau + delta_time)
                    self.belt_speed_PV_filtered += alpha * (self.belt_speed_PV - self.belt_speed_PV_filtered)

                # 2. RAMP LOGIC (Feedforward target speed)
                if self.current_speed_command != self.belt_speed_SP:
                    max_speed_change = self.belt_acc * delta_time
                    diff = self.belt_speed_SP - self.current_speed_command
                    if abs(diff) <= max_speed_change:
                        self.current_speed_command = self.belt_speed_SP
                    else:
                        self.current_speed_command += math.copysign(max_speed_change, diff)

                # 3. SLOW INTEGRAL CONTROLLER + ANTI-WINDUP (Slip / Drift correction)
                erreur = self.current_speed_command - self.belt_speed_PV_filtered
                max_correction = self.current_speed_command * (self.max_drift_pct / 100.0)
                
                # Anti-Windup: Freeze integrator during active feedforward ramping
                is_ramping = abs(self.belt_speed_SP - self.current_speed_command) > 0.05
                # Directional clamping anti-windup: do not accumulate further in saturated direction
                is_saturated_high = (self.integrale_drift >= max_correction) and (erreur > 0)
                is_saturated_low = (self.integrale_drift <= -max_correction) and (erreur < 0)

                if not is_ramping and not (is_saturated_high or is_saturated_low):
                    # Slow, smooth accumulation
                    self.integrale_drift += erreur * delta_time * self.ki

                # Always enforce clamping limits
                self.integrale_drift = max(min(self.integrale_drift, max_correction), -max_correction)
                
                # Proportional correction on filtered error (if kp > 0, default 0)
                correction_p = (erreur * self.kp) if self.kp > 0 else 0.0
                correction_finale = correction_p + self.integrale_drift
                
                # 4. FINAL HARDWARE COMMAND
                # Final command = Feedforward (theoretical ramp) + Trim (slow integral drift correction)
                commande_finale = self.current_speed_command + correction_finale
                commande_finale = max(0.0, commande_finale) # Safety against unwanted reverse command
                self.commande_finale = commande_finale

                if self.hardware:
                    self.hardware.set_belt_speed(commande_finale)

                # Diagnostic check: command active (> 0.5 km/h) but belt stationary (PV < 0.1 km/h) for > 2 seconds
                if self.current_speed_command > 0.5 and self.belt_speed_PV < 0.1:
                    self._stall_warning_counter += 1
                    if self._stall_warning_counter == 20: # 20 ticks * 0.1s = 2.0s
                        msg = (
                            f"ALERTE DÉCROCHAGE: Tapis commandé (SP={self.belt_speed_SP:.2f}, "
                            f"CMD={commande_finale:.2f} km/h, drift={self.drift_pct:.1f}%) "
                            f"mais bande immobile (PV={self.belt_speed_PV:.2f} km/h) ! Variateur désenclenché ou calage ?"
                        )
                        Logger.warning(f"Treadmill DIAGNOSTIC: {msg}")
                        self.log_diagnostic(msg, level="warning")
                else:
                    self._stall_warning_counter = 0

                # Calculate drift percentage (Option A: learned compensation percentage)
                if self.current_speed_command > 0.1:
                    self.drift_pct = (correction_finale/ self.current_speed_command) * 100.0
                else:
                    self.drift_pct = 0.0
            
                #compute distance and elevation
                self.distance_m += (self.belt_speed_PV * 1000 / 3600) * delta_time
                delta_elevation = (self.vertical_speed_PV / 3600) * delta_time
                if not self.belt_direction: #if backward
                    delta_elevation = -delta_elevation
                if delta_elevation > 0:
                    self.elevation_pos_m += delta_elevation
                else:
                    self.elevation_neg_m += delta_elevation
            self.last_update_time = current_time
            
            # Log to file if running by putting data in the queue
            if self.log_thread and self.log_thread.is_alive():
                #add event string only if there was an event
                if self.log_event:
                    event_str = self.event_list[-1]['event'] if self.event_list else ''
                    self.log_event = False
                else:
                    event_str = ''
                
                log_data = {
                    'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                    'time': self.elapsed_time,
                    'belt_speed_SP': self.belt_speed_SP,
                    'belt_speed_CMD': round(self.commande_finale, 3),
                    'belt_speed_PV': self.belt_speed_PV,
                    'lift_angle_SP': self.lift_angle_SP,
                    'lift_angle_PV': self.lift_angle_PV,
                    'vertical_speed_SP': compute_vertical_speed_mh(self.lift_angle_SP, self.belt_speed_SP),
                    'vertical_speed_PV': self.vertical_speed_PV,
                    'distance_m': self.distance_m,
                    'elevation_pos_m': self.elevation_pos_m,
                    'elevation_neg_m': self.elevation_neg_m,
                    'drift_pct': round(self.drift_pct, 2),
                    'event': event_str
                }
                self.log_queue.put(log_data)
            
        #return a dict with all relevant data
        return {
            "lift_angle_PV": self.lift_angle_PV,
            "belt_speed_PV": self.belt_speed_PV,
            "vertical_speed_PV": self.vertical_speed_PV,
            "lift_angle_SP": float(self.lift_angle_SP),
            "belt_speed_SP": float(self.belt_speed_SP),
            "belt_speed_CMD": float(self.commande_finale),
            "vertical_speed_SP": float(compute_vertical_speed_mh(self.lift_angle_SP,self.belt_speed_SP)),
            "safeties": self.safeties,
            "distance_m": self.distance_m,
            "elevation_pos_m": self.elevation_pos_m,
            "elevation_neg_m": self.elevation_neg_m,
            "elapsed_time": self.elapsed_time,
            "belt_direction": self.belt_direction,
            "steps_active": self.steps_active,
            "drift_pct": self.drift_pct
        }

    def start(self, test_name="manual_test", subject_name="sujet"):
        if not self.running:
            self.running = True
            self.test_name = test_name
            self.subject_name = subject_name
            self.reset_variables()
            self.start_time = self.last_update_time = time()
            if self.hardware:
                self.hardware.start_belt()
            Logger.info(f"Treadmill: Starting at {self.start_time}")
            self.log_diagnostic(f"START tapis (test={test_name}, sujet={subject_name}, consigne={self.belt_speed_SP:.2f} km/h)", level="info")
            # Open log and event files
            self._open_log_file()
            self._open_event_file()
            # Write initial event
            self.record_event('start')
        if self.paused:
            self.paused = False
            self.last_update_time = time()
            self.elapsed_pause_time += time() - self.pause_time
            if self.hardware:
                self.hardware.start_belt()
            Logger.info(f"Treadmill: Resumed at {time()}")
            self.log_diagnostic("RESUME tapis après pause", level="info")
            #Write resume event
            self.record_event('resume')

    def pause(self):
        if self.running and not self.paused:
            self.paused = True
            self.pause_time = time()
            self.current_speed_command = 0
            if self.hardware:
                self.hardware.stop_belt()
            Logger.info(f"Treadmill: Paused at {self.pause_time}")
            self.log_diagnostic("PAUSE tapis demandée", level="warning")
            self.record_event('pause')

    def stop(self):
        self.running = False
        self.paused = False
        self.current_speed_command = 0
        if self.hardware:
            self.hardware.stop_belt()
        Logger.info(f"Treadmill: Stopped at {time()}")
        self.log_diagnostic("STOP tapis demandé", level="info")
        self.record_event('stop')
        self._close_log_file()
        self._close_event_file()

    #setpoint functions
    def set_lift_angle(self, angle):
        self.lift_angle_SP = angle
        if self.hardware:   self.hardware.set_lift_angle(angle)
        Logger.info(f"Treadmill: Set angle to {angle}")

    def set_belt_speed(self, speed):
        self.belt_speed_SP = speed
        Logger.info(f"Treadmill: Set belt speed to {speed}")

    def reverse_belt(self, direction):
        self.belt_direction = direction
        if self.hardware:
            self.hardware.set_belt_direction(direction)
        Logger.info(f"Treadmill: Set belt direction to {'forward' if direction else 'backward'}")

    def set_surface(self, is_steps):
        self.steps_active = is_steps
        if self.hardware and hasattr(self.hardware, 'set_steps'):
            self.hardware.set_steps(is_steps)
        Logger.info(f"Treadmill: Set surface to {'steps-bars' if is_steps else 'belt'}")

    #All get functions return the current setpoint or process variable if there is no treadmill attached
    #Caution to self.update() before calling getter
    def get_belt_direction(self):
        return self.belt_direction

    def get_lift_angle(self):
        return self.lift_angle_PV

    def get_belt_speed(self):
        return self.belt_speed_PV
    
    def get_vertical_speed(self):
        return self.vertical_speed_PV

    def get_safeties(self):
        if self.hardware:
            return self.safeties
        return None

    #return running status
    def get_distance(self):
        return self.distance_m

    def get_elevation_pos(self):
        return self.elevation_pos_m

    def get_elevation_neg(self):
        return self.elevation_neg_m

    def get_elapsed_time(self):
        return self.elapsed_time
    
    #return treadmill points
    def get_treadmill_points(self):
        return self.treadmill_points
    
    def is_running(self):
        return self.running and not self.paused
    def is_paused(self):
        return self.paused
    
    #shutdown function
    def shutdown(self):
        if self.hardware:
            self.hardware.stop_all()
            self.hardware.set_belt_speed(0)
        Logger.info(f"Treadmill: Shutdown at {time()}")

    def get_system_info(self):
        """Returns hardware system info enriched with controller state and diagnostic log."""
        if self.hardware and hasattr(self.hardware, 'get_system_info'):
            info = self.hardware.get_system_info()
        else:
            # Simulated telemetry on PC
            cmd_val = round(self.commande_finale, 2)
            calc_val = round(cmd_val * 100 / 40 * 1.8 * 1.025 * 100)
            hsb, lsb = split_value(calc_val)
            info = {
                "connected": False,
                "cycletime_ms": 100,
                "ioerrors": 0,
                "outputs": {
                    "belt_start": False,
                    "belt_stop": bool(self.running and not self.paused),
                    "belt_dir": bool(self.belt_direction),
                    "use_steps": bool(self.steps_active),
                },
                "inputs": {
                    "secu_right": False,
                    "secu_left": False,
                    "secu_front": bool(self.safeties.get("top", False)),
                    "secu_back": bool(self.safeties.get("bottom", False)),
                    "secu_front_back": False,
                    "secu_emergency": False,
                },
                "modbus": {
                    "belt_speed_SP_0": hsb,
                    "belt_speed_SP_1": lsb,
                    "frequency_sent_hz": round(calc_val / 100.0, 2),
                    "encoder_feedback_speed_mms": round(self.belt_speed_PV * 1000 / 3.6),
                    "encoder_feedback_speed_kmh": round(self.belt_speed_PV, 2),
                    "belt_current_frequency": round(calc_val / 100.0, 2),
                    "lift_angle_SP": round(self.lift_angle_SP * 100),
                    "lift_angle_current": round(self.lift_angle_PV * 100),
                    "pid_enable": 1,
                    "Modbus_Master_Status": 0,
                    "Modbus_Action_Status_1": 0,
                    "Modbus_Action_Status_2": 0,
                    "Modbus_Action_Status_3": 0,
                },
                "all_ios": [
                    {"device": "Simu DIO", "name": "belt_start", "value": 0, "type": "OUT", "address": 0, "length": 1},
                    {"device": "Simu DIO", "name": "belt_stop", "value": 1 if (self.running and not self.paused) else 0, "type": "OUT", "address": 1, "length": 1},
                    {"device": "Simu DIO", "name": "belt_dir", "value": 1 if self.belt_direction else 0, "type": "OUT", "address": 2, "length": 1},
                    {"device": "Simu DIO", "name": "use_steps", "value": 1 if self.steps_active else 0, "type": "OUT", "address": 3, "length": 1},
                    {"device": "Simu DIO", "name": "secu_front", "value": 0, "type": "INP", "address": 4, "length": 1},
                    {"device": "Simu DIO", "name": "secu_back", "value": 0, "type": "INP", "address": 5, "length": 1},
                    {"device": "Simu DIO", "name": "secu_left", "value": 0, "type": "INP", "address": 6, "length": 1},
                    {"device": "Simu DIO", "name": "secu_right", "value": 0, "type": "INP", "address": 7, "length": 1},
                    {"device": "Simu DIO", "name": "secu_emergency", "value": 0, "type": "INP", "address": 8, "length": 1},
                    {"device": "Simu Modbus", "name": "belt_speed_SP_0", "value": hsb, "type": "OUT", "address": 100, "length": 2},
                    {"device": "Simu Modbus", "name": "belt_speed_SP_1", "value": lsb, "type": "OUT", "address": 102, "length": 2},
                    {"device": "Simu Modbus", "name": "encoder_feedback_speed", "value": round(self.belt_speed_PV * 1000 / 3.6), "type": "INP", "address": 104, "length": 2},
                    {"device": "Simu Modbus", "name": "Modbus_Master_Status", "value": 0, "type": "INP", "address": 106, "length": 2},
                    {"device": "Simu Modbus", "name": "Modbus_Action_Status_1", "value": 0, "type": "INP", "address": 108, "length": 2},
                    {"device": "Simu Modbus", "name": "Modbus_Action_Status_2", "value": 0, "type": "INP", "address": 110, "length": 2},
                ]
            }

        info["controller"] = {
            "running": self.running,
            "paused": self.paused,
            "belt_speed_SP": self.belt_speed_SP,
            "belt_speed_CMD": round(self.commande_finale, 3),
            "belt_speed_PV": round(self.belt_speed_PV, 3),
            "drift_pct": round(self.drift_pct, 2),
            "stall_warning": self._stall_warning_counter >= 10,
            "modbus_auto_recovery_enabled": self.modbus_auto_recovery_enabled,
            "modbus_auto_reset_count": self.modbus_auto_reset_count,
        }
        info["diagnostic_log"] = list(self.diagnostic_log)
        return info

    def set_modbus_auto_recovery(self, enabled: bool):
        """Enable or disable automatic Modbus error recovery watchdog."""
        self.modbus_auto_recovery_enabled = bool(enabled)
        state_str = "activée" if self.modbus_auto_recovery_enabled else "désactivée"
        self.log_diagnostic(f"Auto-récupération Modbus {state_str}", level="info")

    def toggle_modbus_auto_recovery(self):
        """Toggle automatic Modbus recovery watchdog state."""
        self.set_modbus_auto_recovery(not self.modbus_auto_recovery_enabled)
        return self.modbus_auto_recovery_enabled

    def reset_modbus(self):
        """Send reset pulse to Modbus error flags."""
        if self.hardware and hasattr(self.hardware, 'reset_modbus'):
            count = self.hardware.reset_modbus()
            self.log_diagnostic(f"Réinitialisation Modbus exécutée ({count} drapeaux réinitialisés)", level="info")
            return count
        else:
            self.log_diagnostic("Réinitialisation Modbus (mode simulation)", level="info")
            return 0

    def pulse_start(self):
        """Send a manual start pulse to the VFD."""
        if self.hardware and hasattr(self.hardware, 'start_belt'):
            self.hardware.start_belt("Bouton impulsion start diagnostic")
            self.log_diagnostic("Impulsion START envoyée au variateur", level="info")
        else:
            self.log_diagnostic("Impulsion START simulée envoyée", level="info")

    def clear_diagnostic_log(self):
        """Clear the diagnostic event log."""
        self.diagnostic_log.clear()
        self.log_diagnostic("Journal diagnostic effacé", level="info")
