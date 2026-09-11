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
            'Master_Status_Reset': MockIO(0),
            'Action_Status_Reset_1': MockIO(0),
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
        self.io_dict['Master_Status_Reset'].value = 1
        self.io_dict['Action_Status_Reset_1'].value = 1
        return 2

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
        self.assertEqual(count, 2)
        self.assertEqual(hw.io_dict['Master_Status_Reset'].value, 1)

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

    def test_system_info_widget_lifecycle(self):
        """Verify SystemInfoWidget updates and switches views cleanly."""
        hw = MockHardware()
        tm = treadmill.TreadmillController(hw)
        widget = SystemInfoWidget()
        widget.set_treadmill(tm)
        widget.update_info()
        self.assertTrue(widget.connected)
        self.assertEqual(widget.connection_text, "REVPI EN LIGNE")
        self.assertTrue(widget.belt_stop_val)

        widget.switch_view('explorer')
        self.assertEqual(widget.view_mode, 'explorer')
        widget.set_explorer_type_filter('OUT')
        self.assertEqual(widget.explorer_filter_type, 'OUT')

if __name__ == '__main__':
    unittest.main()
