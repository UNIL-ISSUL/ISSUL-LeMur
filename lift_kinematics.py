import os
import math
import numpy as np
import yaml
import pandas as pd
import matplotlib.pyplot as plt

# Load configuration
config_path = 'hardware.yaml'
if not os.path.exists(config_path):
    config_path = os.path.join(os.path.dirname(__file__), 'hardware.yaml')

with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

L = config['BELT_LENGTH_MM']  # 2620 mm
h = config['BELT_HEIGHT_MM']  # 185 mm
R = config['RADIUS_CYL_MM']    # 93 mm

print(f"Geometry parameters loaded:")
print(f"  L (Belt Length) = {L} mm")
print(f"  h (Belt Height / rear roller to wheel axis vertical distance) = {h} mm")
print(f"  R (Wheel Radius) = {R} mm")

# 1. Direct Kinematics: H(alpha)
# H(alpha) = L * sin(alpha) + h * cos(alpha) + R
def direct_kinematics(alpha_deg):
    alpha_rad = np.radians(alpha_deg)
    return L * np.sin(alpha_rad) + h * np.cos(alpha_rad) + R

# 2. Inverse Kinematics: alpha(H)
# alpha(H) = arcsin((H - R) / sqrt(L^2 + h^2)) - atan2(h, L)
def inverse_kinematics(H):
    denom = np.sqrt(L**2 + h**2)
    val = (H - R) / denom
    # Clip val to [-1, 1] to avoid math domain errors
    val = np.clip(val, -1.0, 1.0)
    alpha_rad = np.arcsin(val) - np.arctan2(h, L)
    return np.degrees(alpha_rad)

# 3. Ground profile for linearization
# We want the relationship between alpha and H to be linear:
# H_linear(alpha) = H_0 + k * alpha
# where H_0 = h + R
alpha_max_deg = 70.0
alpha_max_rad = np.radians(alpha_max_deg)
H_0 = h + R
H_max = direct_kinematics(alpha_max_deg)
k = (H_max - H_0) / alpha_max_rad

def ground_profile(alpha_deg):
    alpha_rad = np.radians(alpha_deg)
    # Required H_linear(alpha)
    H_linear = H_0 + k * alpha_rad
    # Real H without ground profile
    H_flat = L * np.sin(alpha_rad) + h * np.cos(alpha_rad) + R
    # y_ground is the difference between H_linear and H_flat
    y_ground = H_linear - H_flat
    # x coordinate of the wheel axis relative to its position at alpha=0
    # x_w(alpha) = -L * cos(alpha) + h * sin(alpha)
    # x_profile(alpha) = x_w(alpha) - x_w(0) = L*(1 - cos(alpha)) + h * sin(alpha)
    x_profile = L * (1.0 - np.cos(alpha_rad)) + h * np.sin(alpha_rad)
    return x_profile, y_ground

# Generate data points
alpha_vals = np.linspace(0, 70, 500)
H_vals = direct_kinematics(alpha_vals)

x_profile_vals = []
y_ground_vals = []
for a in alpha_vals:
    x_p, y_g = ground_profile(a)
    x_profile_vals.append(x_p)
    y_ground_vals.append(y_g)

x_profile_vals = np.array(x_profile_vals)
y_ground_vals = np.array(y_ground_vals)

# Create a DataFrame
df = pd.DataFrame({
    'Alpha_deg': alpha_vals,
    'H_direct_mm': H_vals,
    'X_profile_mm': x_profile_vals,
    'Y_ground_mm': y_ground_vals
})

df.to_csv('lift_kinematics_data.csv', index=False)
print("Saved data to lift_kinematics_data.csv")

# Plotting
# Plot 1: Direct Kinematics H(alpha)
plt.figure(figsize=(10, 6))
plt.plot(alpha_vals, H_vals, 'b-', linewidth=2, label='Actual $H(\\alpha)$ (Flat Ground)')
plt.plot(alpha_vals, H_0 + k * np.radians(alpha_vals), 'r--', linewidth=1.5, label='Linearized Target $H_{linear}(\\alpha)$')
plt.title('Direct Kinematics of Lift: Pivot Height vs Inclination Angle')
plt.xlabel('Inclination Angle $\\alpha$ (degrees)')
plt.ylabel('Pivot Height $H$ (mm)')
plt.grid(True)
plt.legend()
plt.savefig('direct_kinematics.png', dpi=300)
plt.close()

# Plot 2: Inverse Kinematics alpha(H)
plt.figure(figsize=(10, 6))
plt.plot(H_vals, alpha_vals, 'g-', linewidth=2, label='$\\alpha(H)$ (Flat Ground)')
plt.title('Inverse Kinematics of Lift: Inclination Angle vs Pivot Height')
plt.xlabel('Pivot Height $H$ (mm)')
plt.ylabel('Inclination Angle $\\alpha$ (degrees)')
plt.grid(True)
plt.legend()
plt.savefig('inverse_kinematics.png', dpi=300)
plt.close()

# Plot 3: Ground Profile
plt.figure(figsize=(10, 6))
plt.plot(x_profile_vals, y_ground_vals, 'm-', linewidth=2.5, label='Ground profile $y_{ground}(x)$')
plt.title('Required Ground Profile to Linearize Lift Kinematics')
plt.xlabel('Horizontal Profile Coordinate $x$ (mm) from initial contact')
plt.ylabel('Profile Height $y$ (mm)')
plt.grid(True)
plt.legend()
plt.savefig('ground_profile.png', dpi=300)
plt.close()

print("Generated plots:")
print("  - direct_kinematics.png")
print("  - inverse_kinematics.png")
print("  - ground_profile.png")

# Interpolate ground profile at regular horizontal steps
x_regular = np.arange(0, np.max(x_profile_vals), 100)
y_regular = np.interp(x_regular, x_profile_vals, y_ground_vals)

print("\nGround profile shape coordinates (every 100mm):")
print(f"{'x (mm)':<12} | {'y (mm)':<12}")
print("-" * 27)
for x_val, y_val in zip(x_regular, y_regular):
    print(f"{x_val:<12.1f} | {y_val:<12.2f}")
