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

L = config['LONGERON_LENGTH_MM']    # 2630 mm (updated longeron length)
h = config['LONGERON_HEIGHT_MM']    # 185 mm (longeron height)
D_wheel = config['REAR_WHEEL_DIAMETER_MM'] # 125 mm (rear wheel diameter)
R = D_wheel / 2.0                   # 62.5 mm (rear wheel radius)

print(f"Geometry parameters loaded:")
print(f"  Longeron Length (L) = {L} mm")
print(f"  Longeron Height (h) = {h} mm")
print(f"  Rear Wheel Diameter = {D_wheel} mm (Radius R = {R} mm)")

# 1. Direct Kinematics on flat ground: H_flat(alpha)
# H_flat(alpha) = L * sin(alpha) + h * cos(alpha) + R
def direct_kinematics_flat(alpha_deg):
    alpha_rad = np.radians(alpha_deg)
    return L * np.sin(alpha_rad) + h * np.cos(alpha_rad) + R

# 2. Inverse Kinematics on flat ground: alpha_flat(H)
# alpha(H) = arcsin((H - R) / sqrt(L^2 + h^2)) - atan2(h, L)
def inverse_kinematics_flat(H):
    denom = np.sqrt(L**2 + h**2)
    val = (H - R) / denom
    val = np.clip(val, -1.0, 1.0)
    alpha_rad = np.arcsin(val) - np.arctan2(h, L)
    return np.degrees(alpha_rad)

# 3. Direct Kinematics with ground profile to prevent height decrease
# For alpha <= alpha_0: H(alpha) = H_flat(alpha)
# For alpha > alpha_0: H(alpha) = H_flat(alpha_0) + H_flat'(alpha_0) * (alpha - alpha_0)
def direct_kinematics_profile(alpha_deg, alpha_0_deg=80.0):
    alpha_rad = np.radians(alpha_deg)
    alpha_0_rad = np.radians(alpha_0_deg)
    
    H_flat = L * np.sin(alpha_rad) + h * np.cos(alpha_rad) + R
    
    # Calculate flat properties at transition angle
    H_0_flat = L * np.sin(alpha_0_rad) + h * np.cos(alpha_0_rad) + R
    slope_0 = L * np.cos(alpha_0_rad) - h * np.sin(alpha_0_rad)
    
    if isinstance(alpha_deg, np.ndarray):
        H = np.where(alpha_deg <= alpha_0_deg, 
                     H_flat, 
                     H_0_flat + slope_0 * (alpha_rad - alpha_0_rad))
    else:
        H = H_flat if alpha_deg <= alpha_0_deg else H_0_flat + slope_0 * (alpha_rad - alpha_0_rad)
        
    return H

# 4. Inverse Kinematics with ground profile
# Inverts the direct kinematics with the positive ground profile
def inverse_kinematics_profile(H, alpha_0_deg=80.0):
    alpha_0_rad = np.radians(alpha_0_deg)
    H_0_flat = L * np.sin(alpha_0_rad) + h * np.cos(alpha_0_rad) + R
    slope_0 = L * np.cos(alpha_0_rad) - h * np.sin(alpha_0_rad)
    
    # Case H <= H_0_flat (uses flat kinematics)
    denom = np.sqrt(L**2 + h**2)
    val = (H - R) / denom
    val = np.clip(val, -1.0, 1.0)
    alpha_flat_rad = np.arcsin(val) - np.arctan2(h, L)
    alpha_flat_deg = np.degrees(alpha_flat_rad)
    
    # Case H > H_0_flat (uses linear inverse kinematics)
    alpha_above_rad = alpha_0_rad + (H - H_0_flat) / slope_0
    alpha_above_deg = np.degrees(alpha_above_rad)
    
    if isinstance(H, np.ndarray):
        alpha_deg = np.where(H <= H_0_flat, alpha_flat_deg, alpha_above_deg)
    else:
        alpha_deg = alpha_flat_deg if H <= H_0_flat else alpha_above_deg
        
    return alpha_deg

# Calculate ground profile height y_ground and coordinate x
# y_ground = H_target - H_flat
# x_profile = L * (1 - cos(alpha)) + h * sin(alpha)
def compute_profile(alpha_deg, alpha_0_deg=80.0):
    alpha_rad = np.radians(alpha_deg)
    H_target = direct_kinematics_profile(alpha_deg, alpha_0_deg)
    H_flat = L * np.sin(alpha_rad) + h * np.cos(alpha_rad) + R
    y_ground = H_target - H_flat
    x_profile = L * (1.0 - np.cos(alpha_rad)) + h * np.sin(alpha_rad)
    return x_profile, y_ground

# Generate data points up to 90 degrees
alpha_vals = np.linspace(0, 90, 500)
H_flat_vals = direct_kinematics_flat(alpha_vals)

# Compute for transition angles: 75, 80, 85 degrees
transitions = [75.0, 80.0, 85.0]
results = {}

for t_ang in transitions:
    H_p = direct_kinematics_profile(alpha_vals, t_ang)
    x_p, y_g = compute_profile(alpha_vals, t_ang)
    
    # Verify inverse kinematics for the modified profile
    alpha_inv = inverse_kinematics_profile(H_p, t_ang)
    
    results[t_ang] = {
        'H': H_p,
        'x': x_p,
        'y_ground': y_g,
        'alpha_inv': alpha_inv
    }

# Create a DataFrame for transition angle = 80 degrees
df = pd.DataFrame({
    'Alpha_deg': alpha_vals,
    'H_flat_mm': H_flat_vals,
    'H_profile_80deg_mm': results[80.0]['H'],
    'X_profile_80deg_mm': results[80.0]['x'],
    'Y_ground_80deg_mm': results[80.0]['y_ground'],
    'Alpha_inverse_80deg': results[80.0]['alpha_inv']
})
df.to_csv('lift_kinematics_data.csv', index=False)
print("Saved data to lift_kinematics_data.csv")

# Plotting
# Plot 1: Direct Kinematics H(alpha)
plt.figure(figsize=(10, 6))
plt.plot(alpha_vals, H_flat_vals, 'k--', linewidth=1.5, label='Flat Ground (height decreases at end)')
for t_ang, col in zip(transitions, ['b', 'r', 'g']):
    plt.plot(alpha_vals, results[t_ang]['H'], color=col, linewidth=2, 
             label=f'Modified (Transition at {t_ang}°)')
plt.title('Direct Kinematics of Lift: Pivot Height vs Inclination Angle (0° to 90°)')
plt.xlabel('Inclination Angle $\\alpha$ (degrees)')
plt.ylabel('Pivot Height $H$ (mm)')
plt.grid(True)
plt.legend()
plt.savefig('direct_kinematics.png', dpi=300)
plt.close()

# Plot 2: Inverse Kinematics alpha(H)
plt.figure(figsize=(10, 6))
# Flat ground inverse is only valid up to the peak (85.96 deg)
peak_idx = np.argmax(H_flat_vals)
plt.plot(H_flat_vals[:peak_idx], alpha_vals[:peak_idx], 'k--', linewidth=1.5, label='Flat Ground (only valid up to peak)')
for t_ang, col in zip(transitions, ['b', 'r', 'g']):
    plt.plot(results[t_ang]['H'], results[t_ang]['alpha_inv'], color=col, linewidth=2, 
             label=f'Modified (Transition at {t_ang}°)')
plt.title('Inverse Kinematics of Lift: Inclination Angle vs Pivot Height')
plt.xlabel('Pivot Height $H$ (mm)')
plt.ylabel('Inclination Angle $\\alpha$ (degrees)')
plt.grid(True)
plt.legend()
plt.savefig('inverse_kinematics.png', dpi=300)
plt.close()

# Plot 3: Ground Profiles y_ground(x)
plt.figure(figsize=(10, 6))
for t_ang, col in zip(transitions, ['b', 'r', 'g']):
    plt.plot(results[t_ang]['x'], results[t_ang]['y_ground'], color=col, linewidth=2.5, 
             label=f'Ground profile $y_{{ground}}(x)$ (Transition at {t_ang}°)')
plt.title('Required Ground Profile to Prevent Pivot Height Decrease')
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

# Output regular coordinates for transition at 80 degrees
x_profile_80 = results[80.0]['x']
y_ground_80 = results[80.0]['y_ground']
x_regular = np.arange(0, np.max(x_profile_80), 100)
# Add maximum x point to list
if x_regular[-1] < np.max(x_profile_80):
    x_regular = np.append(x_regular, np.max(x_profile_80))
y_regular = np.interp(x_regular, x_profile_80, y_ground_80)

print("\nGround profile shape coordinates (Transition at 80°, every 100mm):")
print(f"{'x (mm)':<12} | {'y (mm)':<12}")
print("-" * 27)
for x_val, y_val in zip(x_regular, y_regular):
    print(f"{x_val:<12.1f} | {y_val:<12.2f}")
