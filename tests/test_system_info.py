import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ast
if not hasattr(ast, 'Str'):
    class AstStrShim: pass
    ast.Str = AstStrShim

import treadmill
from system_info_widget import SystemInfoWidget

class MockIO:
    def __init__(self, value=0):
        self.value = value
        self.address = 0
        self.length = 1
        self.type = 300

class MockDevice:
    def __init__(self, name, position, ios):
        self.name = name
        self.position = position
        self._ios = ios
    def __iter__(self):
        return iter(self._ios)

class MockHardware:
    def __init__(self):
        self.speed = 0.0
        self.angle = 12.0
        self.direction = True
        self.steps = False
        self.safeties = {'top': False, 'bottom': False, 'left': False, 'right': False, 'emergency': False}
        self.io_dict = {
            'belt_start': MockIO(False),
            'belt_stop': MockIO(True),
            'belt_dir': MockIO(True),
            'use_steps': MockIO(False),
            'secu_front': MockIO(False),
            'secu_back': MockIO(False),
            'secu_left': MockIO(False),
            'secu_right': MockIO(False),
            'secu_emergency': MockIO(False),
            'secu_front_back': MockIO(False),
            'belt_speed_SP_0': MockIO(0),
            'belt_speed_SP_1': MockIO(1500),
            'encoder_feedback_speed': MockIO(833), # ~3.0 km/h
            'lift_angle_SP': MockIO(1200),
            'lift_angle_current': MockIO(1200),
            'pid_enable': MockIO(1),
            'Modbus_Master_Status': MockIO(0),
            'Modbus_Action_Status_1': MockIO(0),
            'Modbus_Action_Status_2': MockIO(0),
            'Modbus_Action_Status_3': MockIO(0),
            'Master_Status_Reset': MockIO(0),
            'Action_Status_Reset_1': MockIO(0),
            'Action_Status_Reset_2': MockIO(0),
            'Action_Status_Reset_3': MockIO(0),
            'belt_current_frequency': MockIO(2500),
        }
        self.rpi = type('RpiObj', (), {
            'cycletime': 100,
            'ioerrors': 0,
            'io': type('IoObj', (), self.io_dict)(),
            'device': [
                MockDevice('RevPi DIO', 1, [
                    type('IOEntry', (), {'name': 'belt_start', 'value': False, 'type': 301, 'address': 0, 'length': 1})(),
                    type('IOEntry', (), {'name': 'belt_stop', 'value': True, 'type': 301, 'address': 1, 'length': 1})(),
                    type('IOEntry', (), {'name': 'secu_front', 'value': False, 'type': 300, 'address': 2, 'length': 1})(),
                ])
            ]
        })()

    def get_lift_angle(self): return self.angle
    def set_lift_angle(self, a): self.angle = a
    def get_belt_speed(self): return self.speed
    def set_belt_speed(self, s): self.speed = s
    def get_belt_direction(self): return self.direction
    def set_belt_direction(self, d): self.direction = d
    def get_safeties(self): return self.safeties
    def set_steps(self, s): self.steps = s
    def start_belt(self, msg=None): self.io_dict['belt_start'].value = True
    def stop_belt(self, msg=None): self.io_dict['belt_stop'].value = False
    def stop_all(self): pass

    def get_io_value(self, name, default=None):
        if name in self.io_dict:
            return self.io_dict[name].value
        return default

    def reset_modbus(self):
        count = 0
        for name in ['Master_Status_Reset', 'Action_Status_Reset_1', 'Action_Status_Reset_2', 'Action_Status_Reset_3']:
            if name in self.io_dict:
                self.io_dict[name].value = 1
                count += 1
        return count

    def get_system_info(self):
        import hardware
        return hardware.revPI.get_system_info(self)

class TestSystemInfo(unittest.TestCase):
    def test_simulation_system_info(self):
        """Verify get_system_info works in simulation (PC mode)."""
        tm = treadmill.TreadmillController(None)
        info = tm.get_system_info()
        self.assertFalse(info['connected'])
        self.assertIn('outputs', info)
        self.assertIn('inputs', info)
        self.assertIn('modbus', info)
        self.assertIn('diagnostic_log', info)
        self.assertIn('all_ios', info)
        self.assertEqual(info['outputs']['belt_start'], False)
        self.assertEqual(info['outputs']['belt_stop'], False)

    def test_hardware_system_info(self):
        """Verify get_system_info works with simulated RevPi hardware."""
        hw = MockHardware()
        tm = treadmill.TreadmillController(hw)
        info = tm.get_system_info()
        self.assertTrue(info['connected'])
        self.assertEqual(info['outputs']['belt_stop'], True)
        self.assertEqual(info['outputs']['belt_start'], False)
        self.assertEqual(info['modbus']['belt_speed_SP_1'], 1500)
        self.assertEqual(info['modbus']['Modbus_Master_Status'], 0)

    def test_reset_modbus(self):
        """Verify reset_modbus resets master & action flags."""
        hw = MockHardware()
        tm = treadmill.TreadmillController(hw)
        count = tm.reset_modbus()
        self.assertEqual(count, 4)
        self.assertEqual(hw.io_dict['Master_Status_Reset'].value, 1)
        self.assertEqual(hw.io_dict['Action_Status_Reset_1'].value, 1)

    def test_describe_modbus_status(self):
        """Verify describe_modbus_status decodes error and OK codes correctly."""
        self.assertEqual(treadmill.describe_modbus_status(0), "OK")
        self.assertIn("Timeout", treadmill.describe_modbus_status(110))
        self.assertIn("occupé", treadmill.describe_modbus_status(17))
        self.assertIn("non supportée", treadmill.describe_modbus_status(1))
        self.assertIn("Erreur communication générique", treadmill.describe_modbus_status(255))
        self.assertEqual(treadmill.describe_modbus_status(999), "Défaut communication (999)")
        self.assertEqual(treadmill.describe_modbus_status(None), "Non configuré")

    def test_transition_logging(self):
        """Verify IO transitions and stall warnings generate log entries."""
        hw = MockHardware()
        tm = treadmill.TreadmillController(hw)
        tm.start()
        
        # Simulate belt_stop transition
        hw.io_dict['belt_stop'].value = False
        tm.update()
        
        log_msgs = [e['msg'] for e in tm.diagnostic_log]
        self.assertTrue(any('belt_stop' in m for m in log_msgs))

    def test_modbus_status_transition_logging(self):
        """Verify Modbus Action status transitions (e.g. 110 <-> 17) are logged with descriptions."""
        hw = MockHardware()
        tm = treadmill.TreadmillController(hw)
        tm.start()
        tm.update()
        
        # Simulate transition 0 -> 110 (Timeout)
        hw.io_dict['Modbus_Action_Status_1'].value = 110
        tm.update()
        
        log_msgs = [e['msg'] for e in tm.diagnostic_log]
        self.assertTrue(any('0 -> 110' in m and 'Timeout' in m for m in log_msgs))
        
        # Simulate transition 110 -> 17 (Port busy)
        hw.io_dict['Modbus_Action_Status_1'].value = 17
        tm.update()
        log_msgs = [e['msg'] for e in tm.diagnostic_log]
        self.assertTrue(any('110 -> 17' in m and 'occupé' in m for m in log_msgs))

    def test_modbus_auto_recovery_watchdog(self):
        """Verify Auto-Recovery Watchdog triggers reset_modbus on errors 110/17 while running."""
        hw = MockHardware()
        tm = treadmill.TreadmillController(hw)
        tm.start()
        self.assertTrue(tm.running)
        self.assertTrue(tm.modbus_auto_recovery_enabled)
        self.assertEqual(tm.modbus_auto_reset_count, 0)
        
        # When Action 1 hits error 110
        hw.io_dict['Modbus_Action_Status_1'].value = 110
        tm.update()
        
        # Should have incremented reset count and triggered hardware reset
        self.assertEqual(tm.modbus_auto_reset_count, 1)
        self.assertEqual(hw.io_dict['Master_Status_Reset'].value, 1)
        
        # Clear reset flag on hardware
        hw.io_dict['Master_Status_Reset'].value = 0
        
        # Immediate subsequent update should be rate-limited (cooldown 1.5s)
        tm.update()
        self.assertEqual(tm.modbus_auto_reset_count, 1)
        self.assertEqual(hw.io_dict['Master_Status_Reset'].value, 0)
        
        # Simulate passage of time (> 1.5s)
        tm._last_modbus_auto_reset_time = 0.0
        hw.io_dict['Modbus_Action_Status_1'].value = 17
        tm.update()
        self.assertEqual(tm.modbus_auto_reset_count, 2)
        self.assertEqual(hw.io_dict['Master_Status_Reset'].value, 1)
        
        # When auto-recovery is disabled, it should not trigger
        tm.set_modbus_auto_recovery(False)
        self.assertFalse(tm.modbus_auto_recovery_enabled)
        tm._last_modbus_auto_reset_time = 0.0
        hw.io_dict['Master_Status_Reset'].value = 0
        tm.update()
        self.assertEqual(tm.modbus_auto_reset_count, 2)
        self.assertEqual(hw.io_dict['Master_Status_Reset'].value, 0)

    def test_system_info_widget_lifecycle(self):
        """Verify SystemInfoWidget updates, switches views, and formats Modbus statuses cleanly."""
        hw = MockHardware()
        hw.io_dict['Modbus_Action_Status_1'].value = 110
        hw.io_dict['Modbus_Action_Status_2'].value = 0
        hw.io_dict['Modbus_Action_Status_3'].value = 17
        
        tm = treadmill.TreadmillController(hw)
        widget = SystemInfoWidget()
        widget.set_treadmill(tm)
        widget.update_info()
        
        self.assertTrue(widget.connected)
        self.assertEqual(widget.connection_text, "REVPI EN LIGNE")
        self.assertIn("110", widget.modbus_act1_text)
        self.assertIn("Timeout", widget.modbus_act1_text)
        self.assertEqual(widget.modbus_act1_bg, [0.85, 0.45, 0.1, 1])
        self.assertEqual(widget.modbus_act2_text, "0 (OK)")
        self.assertIn("17", widget.modbus_act3_text)
        self.assertEqual(widget.freq_pv_text, "25.00 Hz")
        self.assertTrue(widget.modbus_auto_recovery_active)
        
        # Test toggling auto-recovery from widget
        widget.toggle_auto_recovery_clicked()
        self.assertFalse(tm.modbus_auto_recovery_enabled)
        widget.update_info()
        self.assertFalse(widget.modbus_auto_recovery_active)

        widget.switch_view('explorer')
        self.assertEqual(widget.view_mode, 'explorer')
        widget.set_explorer_type_filter('OUT')
        self.assertEqual(widget.explorer_filter_type, 'OUT')

if __name__ == '__main__':
    unittest.main()

