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
H_target_90 = config['TARGET_PIVOT_HEIGHT_AT_90_MM'] # 2750 mm (target pivot height at 90°)

output_dir = 'kinematics'
os.makedirs(output_dir, exist_ok=True)

print(f"Geometry parameters loaded:")
print(f"  Longeron Length (L) = {L} mm")
print(f"  Longeron Height (h) = {h} mm")
print(f"  Rear Wheel Diameter = {D_wheel} mm (Radius R = {R} mm)")
print(f"  Target Pivot Height at 90° = {H_target_90} mm")

# 1. Solve for the transition angle alpha_0 numerically
def get_final_height(a0_deg):
    a0_rad = np.radians(a0_deg)
    H0_flat = L * np.sin(a0_rad) + h * np.cos(a0_rad) + R
    slope_0 = L * np.cos(a0_rad) - h * np.sin(a0_rad)
    H_90 = H0_flat + slope_0 * (np.radians(90.0) - a0_rad)
    return H_90

# We use Bisection method to find alpha_0_deg such that get_final_height(alpha_0_deg) = H_target_90
low, high = 60.0, 89.9
for _ in range(100):
    mid = (low + high) / 2.0
    H_90_val = get_final_height(mid)
    if H_90_val > H_target_90:
        low = mid
    else:
        high = mid

alpha_0_opt = (low + high) / 2.0
print(f"Optimized Transition Angle (alpha_0) = {alpha_0_opt:.4f}°")

# 2. Direct Kinematics on flat ground: H_flat(alpha)
def direct_kinematics_flat(alpha_deg):
    alpha_rad = np.radians(alpha_deg)
    return L * np.sin(alpha_rad) + h * np.cos(alpha_rad) + R

# 3. Direct Kinematics with optimized ground profile
def direct_kinematics_profile(alpha_deg, alpha_0_deg):
    alpha_rad = np.radians(alpha_deg)
    alpha_0_rad = np.radians(alpha_0_deg)
    
    H_flat = L * np.sin(alpha_rad) + h * np.cos(alpha_rad) + R
    
    H_0_flat = L * np.sin(alpha_0_rad) + h * np.cos(alpha_0_rad) + R
    slope_0 = L * np.cos(alpha_0_rad) - h * np.sin(alpha_0_rad)
    
    if isinstance(alpha_deg, np.ndarray):
        H = np.where(alpha_deg <= alpha_0_deg, 
                     H_flat, 
                     H_0_flat + slope_0 * (alpha_rad - alpha_0_rad))
    else:
        H = H_flat if alpha_deg <= alpha_0_deg else H_0_flat + slope_0 * (alpha_rad - alpha_0_rad)
        
    return H

# 4. Inverse Kinematics with optimized ground profile
def inverse_kinematics_profile(H, alpha_0_deg):
    alpha_0_rad = np.radians(alpha_0_deg)
    H_0_flat = L * np.sin(alpha_0_rad) + h * np.cos(alpha_0_rad) + R
    slope_0 = L * np.cos(alpha_0_rad) - h * np.sin(alpha_0_rad)
    
    denom = np.sqrt(L**2 + h**2)
    val = (H - R) / denom
    val = np.clip(val, -1.0, 1.0)
    alpha_flat_rad = np.arcsin(val) - np.arctan2(h, L)
    alpha_flat_deg = np.degrees(alpha_flat_rad)
    
    alpha_above_rad = alpha_0_rad + (H - H_0_flat) / slope_0
    alpha_above_deg = np.degrees(alpha_above_rad)
    
    if isinstance(H, np.ndarray):
        alpha_deg = np.where(H <= H_0_flat, alpha_flat_deg, alpha_above_deg)
    else:
        alpha_deg = alpha_flat_deg if H <= H_0_flat else alpha_above_deg
        
    return alpha_deg

# Calculate ground profile height y_ground and coordinate x
def compute_profile(alpha_deg, alpha_0_deg):
    alpha_rad = np.radians(alpha_deg)
    H_target = direct_kinematics_profile(alpha_deg, alpha_0_deg)
    H_flat = L * np.sin(alpha_rad) + h * np.cos(alpha_rad) + R
    y_ground = H_target - H_flat
    x_profile = L * (1.0 - np.cos(alpha_rad)) + h * np.sin(alpha_rad)
    return x_profile, y_ground

# Generate data points up to 90 degrees
alpha_vals = np.linspace(0, 90, 500)
H_flat_vals = direct_kinematics_flat(alpha_vals)
H_opt_vals = direct_kinematics_profile(alpha_vals, alpha_0_opt)
x_opt_vals, y_opt_ground = compute_profile(alpha_vals, alpha_0_opt)
alpha_opt_inv = inverse_kinematics_profile(H_opt_vals, alpha_0_opt)

# Create a DataFrame for optimized profile (full range 0 to 90)
df_full = pd.DataFrame({
    'Alpha_deg': alpha_vals,
    'H_flat_mm': H_flat_vals,
    'H_profile_opt_mm': H_opt_vals,
    'X_profile_opt_mm': x_opt_vals,
    'Y_ground_opt_mm': y_opt_ground,
    'Alpha_inverse_opt': alpha_opt_inv
})
df_full.to_csv(os.path.join(output_dir, 'lift_kinematics_data.csv'), index=False)
print("Saved data to kinematics/lift_kinematics_data.csv")

# 5. Generate local wedge profile starting at its own 0 (where the ramp starts)
# and format it for Fusion 360 import (X, Y, Z headerless CSV)
alpha_wedge_vals = np.linspace(alpha_0_opt, 90.0, 200)
x_w, y_w = compute_profile(alpha_wedge_vals, alpha_0_opt)
x_0 = x_w[0]

x_local = x_w - x_0
y_local = y_w
z_local = np.zeros_like(x_local)

# Save standard CSV with headers
df_wedge = pd.DataFrame({
    'X_local_mm': x_local,
    'Y_height_mm': y_local,
    'Z_mm': z_local
})
df_wedge.to_csv(os.path.join(output_dir, 'wedge_profile_optimized.csv'), index=False)

# Save headerless CSV for Fusion 360
df_wedge.to_csv(os.path.join(output_dir, 'wedge_profile_optimized_fusion.csv'), header=False, index=False)
print("Saved optimized wedge profiles to kinematics/wedge_profile_optimized.csv and wedge_profile_optimized_fusion.csv")

# Plotting
# Plot 1: Direct Kinematics H(alpha)
plt.figure(figsize=(10, 6))
plt.plot(alpha_vals, H_flat_vals, 'k--', linewidth=1.5, label='Flat Ground (height decreases at end)')
plt.plot(alpha_vals, H_opt_vals, 'r-', linewidth=2, label=f'Optimized Profile (Transition at {alpha_0_opt:.2f}°)')
plt.axhline(y=H_target_90, color='g', linestyle=':', label=f'Target Height at 90° ({H_target_90} mm)')
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
plt.plot(H_opt_vals, alpha_opt_inv, 'r-', linewidth=2, label=f'Optimized Profile (Transition at {alpha_0_opt:.2f}°)')
plt.title('Inverse Kinematics of Lift: Inclination Angle vs Pivot Height')
plt.xlabel('Pivot Height $H$ (mm)')
plt.ylabel('Inclination Angle $\\alpha$ (degrees)')
plt.grid(True)
plt.legend()
plt.savefig(os.path.join(output_dir, 'inverse_kinematics.png'), dpi=300)
plt.close()

# Plot 3: Ground Profile y_ground(x)
plt.figure(figsize=(10, 6))
plt.plot(x_opt_vals, y_opt_ground, 'r-', linewidth=2.5, label=f'Ground profile $y_{{ground}}(x)$ (Transition at {alpha_0_opt:.2f}°)')
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

# Output regular coordinates for the optimized transition angle
x_regular = np.arange(0, np.max(x_local), 50)
if x_regular[-1] < np.max(x_local):
    x_regular = np.append(x_regular, np.max(x_local))
y_regular = np.interp(x_regular, x_local, y_local)

print(f"\nWedge profile shape coordinates starting at local 0 (Transition at {alpha_0_opt:.2f}°):")
print(f"{'x (mm)':<12} | {'y (mm)':<12}")
print("-" * 27)
for x_val, y_val in zip(x_regular, y_regular):
    print(f"{x_val:<12.1f} | {y_val:<12.2f}")
