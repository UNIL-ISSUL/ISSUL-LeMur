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

L = config['LONGERON_LENGTH_MM']    # 2630 mm (longeron length)
h = config['LONGERON_HEIGHT_MM']    # 185 mm (longeron height)
D_wheel = config['REAR_WHEEL_DIAMETER_MM'] # 125 mm (rear wheel diameter)
R = D_wheel / 2.0                   # 62.5 mm (rear wheel radius)

output_dir = 'kinematics'
os.makedirs(output_dir, exist_ok=True)

print(f"Geometry parameters loaded:")
print(f"  Longeron Length (L) = {L} mm")
print(f"  Longeron Height (h) = {h} mm")
print(f"  Rear Wheel Diameter = {D_wheel} mm (Radius R = {R} mm)")
print(f"All output files will be saved in the directory: {output_dir}")

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
    alpha_inv = inverse_kinematics_profile(H_p, t_ang)
    
    results[t_ang] = {
        'H': H_p,
        'x': x_p,
        'y_ground': y_g,
        'alpha_inv': alpha_inv
    }

# Create a DataFrame for transition angle = 80 degrees (full range 0 to 90)
df_full = pd.DataFrame({
    'Alpha_deg': alpha_vals,
    'H_flat_mm': H_flat_vals,
    'H_profile_80deg_mm': results[80.0]['H'],
    'X_profile_80deg_mm': results[80.0]['x'],
    'Y_ground_80deg_mm': results[80.0]['y_ground'],
    'Alpha_inverse_80deg': results[80.0]['alpha_inv']
})
df_full.to_csv(os.path.join(output_dir, 'lift_kinematics_data.csv'), index=False)
print("Saved data to kinematics/lift_kinematics_data.csv")

# 5. Generate local wedge profiles starting at their own 0 (where the ramp starts)
# and format them for Fusion 360 import (X, Y, Z headerless CSV)
for t_ang in transitions:
    # We only care about the region from t_ang to 90 degrees where the wedge is non-zero
    alpha_wedge_vals = np.linspace(t_ang, 90, 200)
    x_w, y_w = compute_profile(alpha_wedge_vals, t_ang)
    
    # Starting offset x_0
    x_0 = x_w[0]
    
    # Local coordinates: starts at 0
    x_local = x_w - x_0
    y_local = y_w
    z_local = np.zeros_like(x_local)
    
    # Save standard CSV with headers
    df_wedge = pd.DataFrame({
        'X_local_mm': x_local,
        'Y_height_mm': y_local,
        'Z_mm': z_local
    })
    csv_name = f'wedge_profile_{int(t_ang)}deg.csv'
    df_wedge.to_csv(os.path.join(output_dir, csv_name), index=False)
    
    # Save headerless CSV for Fusion 360 (Comma delimited X,Y,Z with no headers)
    fusion_csv_name = f'wedge_profile_{int(t_ang)}deg_fusion.csv'
    df_wedge.to_csv(os.path.join(output_dir, fusion_csv_name), header=False, index=False)
    print(f"Saved wedge profiles for transition at {t_ang}° to {output_dir}/")

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
plt.savefig(os.path.join(output_dir, 'direct_kinematics.png'), dpi=300)
plt.close()

# Plot 2: Inverse Kinematics alpha(H)
plt.figure(figsize=(10, 6))
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
plt.savefig(os.path.join(output_dir, 'inverse_kinematics.png'), dpi=300)
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
plt.savefig(os.path.join(output_dir, 'ground_profile.png'), dpi=300)
plt.close()

print("Generated plots in kinematics/:")
print("  - direct_kinematics.png")
print("  - inverse_kinematics.png")
print("  - ground_profile.png")

# Output regular coordinates for transition at 80 degrees
# Regenerate regular coordinates relative to local 0
alpha_wedge_80 = np.linspace(80.0, 90.0, 200)
x_w_80, y_w_80 = compute_profile(alpha_wedge_80, 80.0)
x_local_80 = x_w_80 - x_w_80[0]

x_regular = np.arange(0, np.max(x_local_80), 50)
if x_regular[-1] < np.max(x_local_80):
    x_regular = np.append(x_regular, np.max(x_local_80))
y_regular = np.interp(x_regular, x_local_80, y_w_80)

print("\nWedge profile shape coordinates starting at local 0 (Transition at 80°):")
print(f"{'x (mm)':<12} | {'y (mm)':<12}")
print("-" * 27)
for x_val, y_val in zip(x_regular, y_regular):
    print(f"{x_val:<12.1f} | {y_val:<12.2f}")
