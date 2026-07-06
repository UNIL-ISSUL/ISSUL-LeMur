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
        print("Testing drift compensation...")
        class MockHardware:
            def __init__(self):
                self.speed = 12.5
            def get_lift_angle(self): return 10
            def get_belt_speed(self): return self.speed
            def get_safeties(self): return {"top": False, "bottom": False, "left": False, "right": False, "emergency": False}
            def get_belt_direction(self): return True
            def set_belt_speed(self, val): pass
            def stop_belt(self): pass
            def stop_all(self): pass

        mock_hw = MockHardware()
        self.treadmill.hardware = mock_hw
        # Set a speed and simulate a higher PV (so drift ratio is < 1.0)
        self.treadmill.set_belt_speed(10)
        for _ in range(250):
            self.treadmill.update()

        # After updates, drift should be calculated and clamped at 0.8
        self.assertAlmostEqual(self.treadmill.drift, 0.8, places=1)

        # The compensated speed should be lower
        self.assertLess(self.treadmill.compensated_belt_speed_SP, 10)
        self.assertAlmostEqual(self.treadmill.compensated_belt_speed_SP, 10 * 0.8, places=1)

        # Now, simulate a PV that is lower than SP (so drift ratio is > 1.0)
        mock_hw.speed = 8.3
        for _ in range(450):
            self.treadmill.update()

        # Drift should be calculated and clamped at 1.2
        self.assertAlmostEqual(self.treadmill.drift, 1.2, places=1)
        self.assertAlmostEqual(self.treadmill.compensated_belt_speed_SP, 10 * 1.2, places=1)
        print("OK")


if __name__ == '__main__':
    unittest.main()