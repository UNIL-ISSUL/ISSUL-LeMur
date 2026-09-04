import unittest
import sys
import os
from time import sleep
import yaml

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from treadmill import TreadmillController

class TestTreadmillController(unittest.TestCase):

    def setUp(self):
        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'treadmill.yaml'))
        self.backup_path = self.config_path + '.bak'
        if os.path.exists(self.config_path):
            import shutil
            shutil.copy2(self.config_path, self.backup_path)

        # Create a temporary yaml file for testing
        with open(self.config_path, 'w') as f:
            yaml.dump({'max_drift_pct': 20}, f)

        # Mock hardware, so we can test logic without real hardware
        self.treadmill = TreadmillController(hardware=None)
        # Start the treadmill for testing
        self.treadmill.start()
        # Set non-zero speed and angle for calculations
        self.treadmill.set_belt_speed(10) # 10 km/h
        self.treadmill.set_lift_angle(10) # 10 degrees

    def tearDown(self):
        try:
            self.treadmill.stop()
        finally:
            # Remove or restore the yaml file
            if os.path.exists(self.backup_path):
                import shutil
                if os.path.exists(self.config_path):
                    os.remove(self.config_path)
                shutil.move(self.backup_path, self.config_path)
            elif os.path.exists(self.config_path):
                os.remove(self.config_path)

    def test_elevation_forward_uphill(self):
        print("Testing forward uphill...")
        self.treadmill.reverse_belt(True) # Forward
        self.treadmill.set_lift_angle(10) # Uphill
        initial_pos_elevation = self.treadmill.get_elevation_pos()
        self.treadmill.update()
        sleep(0.1) # Simulate time passing
        self.treadmill.update()
        self.assertGreater(self.treadmill.get_elevation_pos(), initial_pos_elevation)
        print("OK")

    def test_elevation_forward_downhill(self):
        print("Testing forward downhill...")
        self.treadmill.reverse_belt(True) # Forward
        self.treadmill.set_lift_angle(-10) # Downhill
        initial_neg_elevation = self.treadmill.get_elevation_neg()
        self.treadmill.update()
        sleep(0.1) # Simulate time passing
        self.treadmill.update()
        self.assertLess(self.treadmill.get_elevation_neg(), initial_neg_elevation)
        print("OK")

    def test_elevation_backward_uphill(self):
        print("Testing backward uphill...")
        self.treadmill.reverse_belt(False) # Backward
        self.treadmill.set_lift_angle(10) # Uphill
        initial_neg_elevation = self.treadmill.get_elevation_neg()
        self.treadmill.update()
        sleep(0.1) # Simulate time passing
        self.treadmill.update()
        self.assertLess(self.treadmill.get_elevation_neg(), initial_neg_elevation)
        print("OK")

    def test_elevation_backward_downhill(self):
        print("Testing backward downhill...")
        self.treadmill.reverse_belt(False) # Backward
        self.treadmill.set_lift_angle(-10) # Downhill
        initial_pos_elevation = self.treadmill.get_elevation_pos()
        self.treadmill.update()
        sleep(0.1) # Simulate time passing
        self.treadmill.update()
        self.assertGreater(self.treadmill.get_elevation_pos(), initial_pos_elevation)
        print("OK")

    def test_reset_variables(self):
        print("Testing reset variables...")
        self.treadmill.reverse_belt(True)
        self.treadmill.set_lift_angle(10)
        self.treadmill.update()
        sleep(0.1)
        self.treadmill.update()
        self.assertNotEqual(0, self.treadmill.get_elevation_pos())
        self.treadmill.reset_variables()
        self.assertEqual(0, self.treadmill.get_elevation_pos())
        self.assertEqual(0, self.treadmill.get_elevation_neg())
        print("OK")


    def test_drift_compensation(self):
        print("Testing feedforward + slow integral drift compensation...")
        class MockHardware:
            def __init__(self):
                self.speed = 10.0
                self.last_commanded_speed = None
            def get_lift_angle(self): return 10
            def get_belt_speed(self): return self.speed
            def get_safeties(self): return {"top": False, "bottom": False, "left": False, "right": False, "emergency": False}
            def get_belt_direction(self): return True
            def set_belt_speed(self, val):
                self.last_commanded_speed = val
            def stop_belt(self): pass
            def stop_all(self): pass

        mock_hw = MockHardware()
        self.treadmill.hardware = mock_hw
        self.treadmill.belt_acc = 100.0  # Fast acceleration for test
        self.treadmill.set_belt_speed(10)
        
        # Advance update loop so ramp completes
        self.treadmill.update()
        sleep(0.15)
        self.treadmill.update()
        self.assertEqual(self.treadmill.current_speed_command, 10.0)

        # Simulate small slip: PV is 9.5 km/h
        mock_hw.speed = 9.5
        sleep(0.1)
        status = self.treadmill.update()

        # Integrator should have accumulated positive error
        self.assertGreater(self.treadmill.integrale_drift, 0.0)

        # With kp=0, commanded speed should be feedforward (10.0) + integral
        expected_speed = 10.0 + self.treadmill.integrale_drift
        self.assertAlmostEqual(mock_hw.last_commanded_speed, expected_speed, places=2)

        # Drift pct should be computed and available in status
        expected_drift_pct = (self.treadmill.integrale_drift / 10.0) * 100.0
        self.assertAlmostEqual(self.treadmill.drift_pct, expected_drift_pct, places=2)
        self.assertIn('drift_pct', status)
        self.assertAlmostEqual(status['drift_pct'], expected_drift_pct, places=2)

        # Test that large error (> 1.0 km/h) DOES NOT freeze the integrator
        integral_before_large_error = self.treadmill.integrale_drift
        mock_hw.speed = 8.0  # Error = 2.0 km/h > 1.0 km/h
        sleep(0.1)
        self.treadmill.update()
        self.assertGreater(self.treadmill.integrale_drift, integral_before_large_error)

        # Test Dynamic Clamping: If integral exceeds max_correction, it should clamp to max_drift_pct (20% of 10 km/h = 2.0)
        self.treadmill.integrale_drift = 5.0  # Artificially exceed clamping
        sleep(0.05)
        self.treadmill.update()
        max_clamped = 10.0 * (self.treadmill.max_drift_pct / 100.0)
        self.assertAlmostEqual(self.treadmill.integrale_drift, max_clamped, places=2)

        # Test negative clamping
        self.treadmill.integrale_drift = -5.0
        sleep(0.05)
        self.treadmill.update()
        self.assertAlmostEqual(self.treadmill.integrale_drift, -max_clamped, places=2)

        # Anti-Windup during ramping: Ramping actively freezes integrator
        integral_before_ramp = self.treadmill.integrale_drift
        self.treadmill.belt_acc = 1.0  # Slow acceleration
        self.treadmill.set_belt_speed(20.0)  # Trigger ramp
        mock_hw.speed = 9.5
        sleep(0.1)
        self.treadmill.update()
        self.assertEqual(self.treadmill.integrale_drift, integral_before_ramp)

        # Reset variables should clear integrator and drift_pct
        self.treadmill.reset_variables()
        self.assertEqual(self.treadmill.integrale_drift, 0.0)
        self.assertEqual(self.treadmill.drift_pct, 0.0)
        self.assertIsNone(self.treadmill.belt_speed_PV_filtered)
        print("OK")

    def test_speed_measurement_filter(self):
        print("Testing low-pass filter on belt speed...")
        class MockHardware:
            def __init__(self):
                self.speed = 10.0
            def get_lift_angle(self): return 0
            def get_belt_speed(self): return self.speed
            def get_safeties(self): return {"top": False, "bottom": False, "left": False, "right": False, "emergency": False}
            def get_belt_direction(self): return True
            def set_belt_speed(self, val): pass
            def stop_belt(self): pass
            def stop_all(self): pass

        mock_hw = MockHardware()
        self.treadmill.hardware = mock_hw
        self.treadmill.belt_acc = 100.0
        self.treadmill.set_belt_speed(10.0)
        self.treadmill.drift_filter_tau = 3.0

        # Initial update establishes filter baseline
        self.treadmill.update()
        self.assertEqual(self.treadmill.belt_speed_PV_filtered, 10.0)

        # Simulate foot contact oscillations (dip to 8.0 km/h for a brief 0.05s)
        mock_hw.speed = 8.0
        sleep(0.05)
        self.treadmill.update()

        # The filtered speed should reject the sharp dip (stay very close to 10.0 km/h, well above 9.5 km/h)
        self.assertGreater(self.treadmill.belt_speed_PV_filtered, 9.5)
        self.assertLess(self.treadmill.belt_speed_PV_filtered, 10.0)
        print("OK")


if __name__ == '__main__':
    unittest.main()