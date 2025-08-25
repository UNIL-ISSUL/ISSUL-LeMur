import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

fig = plt.figure(figsize=(8,6))
ax = fig.add_subplot(111, projection='3d')

# Paramètres du tapis
L = 2.0   # longueur
W = 0.6   # largeur
R = 0.1   # rayon des rouleaux
theta = 20 * np.pi/180  # inclinaison en radians

# Position des rouleaux
x0, y0, z0 = 0, 0, 0
x1 = L*np.cos(theta)
z1 = L*np.sin(theta)

# Rouleaux (cylindres)
phi = np.linspace(0, 2*np.pi, 50)
y = np.linspace(-W/2, W/2, 2)
Y, PHI = np.meshgrid(y, phi)
Xc = R*np.cos(PHI)
Zc = R*np.sin(PHI)

# Rouleau bas
Xb = Xc + x0
Yb = Y
Zb = Zc + z0
ax.plot_surface(Xb, Yb, Zb, color="green", alpha=0.7)

# Rouleau haut
Xt = Xc + x1
Yt = Y
Zt = Zc + z1
ax.plot_surface(Xt, Yt, Zt, color="green", alpha=0.7)

# Bande du tapis (rectangle rouge)
X = np.array([[x0, x1],[x0, x1]])
Y = np.array([[-W/2, -W/2],[W/2, W/2]])
Z = np.array([[z0, z1],[z0, z1]])
ax.plot_surface(X, Y, Z, color="red", alpha=0.5)

# Axes
ax.quiver(0,0,0, 0.5,0,0, color="k", arrow_length_ratio=0.1)  # X
ax.quiver(0,0,0, 0,0.5,0, color="k", arrow_length_ratio=0.1)  # Y
ax.quiver(0,0,0, 0,0,0.5, color="k", arrow_length_ratio=0.1)  # Z

# Réglages
ax.set_xlabel("X")
ax.set_ylabel("Y")
ax.set_zlabel("Z")
ax.set_box_aspect([2,1,1])
plt.show()
