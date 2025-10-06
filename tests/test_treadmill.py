import unittest
import sys
import os
from time import sleep

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from treadmill import TreadmillController

class TestTreadmillController(unittest.TestCase):

    def setUp(self):
        # Mock hardware, so we can test logic without real hardware
        self.treadmill = TreadmillController(hardware=None)
        # Start the treadmill for testing
        self.treadmill.start()
        # Set non-zero speed and angle for calculations
        self.treadmill.set_belt_speed(10) # 10 km/h
        self.treadmill.set_lift_angle(10) # 10 degrees

    def tearDown(self):
        self.treadmill.stop()

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
        # Set a speed and simulate a lower PV for a while
        self.treadmill.set_belt_speed(10)
        for _ in range(10):
            # Simulate a PV that is 15% lower than SP
            self.treadmill.belt_speed_PV = 8.5
            self.treadmill.update()
            sleep(0.1)

        # After 10 updates, drift should be calculated and clamped at 0.9
        self.assertAlmostEqual(self.treadmill.drift, 0.9, places=2)

        # The compensated speed should be lower
        self.assertLess(self.treadmill.compensated_belt_speed_SP, 10)
        self.assertAlmostEqual(self.treadmill.compensated_belt_speed_SP, 10 * 0.9, places=2)

        # Now, simulate a PV that is higher than SP
        for _ in range(10):
            self.treadmill.belt_speed_PV = 12
            self.treadmill.update()
            sleep(0.1)

        # Drift should be calculated and clamped at 1.1
        self.assertAlmostEqual(self.treadmill.drift, 1.1, places=2)
        self.assertAlmostEqual(self.treadmill.compensated_belt_speed_SP, 10 * 1.1, places=2)
        print("OK")


if __name__ == '__main__':
    unittest.main()
