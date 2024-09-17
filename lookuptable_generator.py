#generate lookup table for belt speed calibration
import numpy as np
from scipy.interpolate import griddata
import time

#motor control value is frequency in Hz
#input variable are angle [°], speed [km/h] and weight [kg]
#points_marches = np.array([[18,2.83,50],[18,2.83,80],[30,1.79,50],[30,1.81,80],[38,1.48,50],[38,1.49,80],[18,2.11,50],[18,2.12,80],[30,1.34,50],[30,1.37,80],[38,1.12,50],[38,1.16,80],[30,2.26,80]])
#values_marches = np.array([6.48,6.48,4,4,3.25,3.25,4.85,4.85,3,3,2.44,2.44,5])

points_marches = np.loadtxt('speed_calib_steps.txt', delimiter='\t',skiprows=2,usecols=(1,2,3))
values_marches = np.loadtxt('speed_calib_steps.txt', delimiter='\t',skiprows=2,usecols=(0))

grid_x, grid_y, grid_z = np.mgrid[18:38:200j, 1:3:200j, 50:80:30j]

time_0 = time.time()
print("frequency 18 @80kg:",griddata(points_marches, values_marches, (18, 2.59, 80), method='linear'))
print("frequency 22 @80kg:",griddata(points_marches, values_marches, (22, 2.14, 80), method='linear'))
print("frequency 26 @80kg:",griddata(points_marches, values_marches, (26, 1.82, 80), method='linear'))
print("frequency 30 @80kg:",griddata(points_marches, values_marches, (30, 1.60, 80), method='linear'))
print("frequency 38 @80kg:",griddata(points_marches, values_marches, (30, 1.3, 80), method='linear'))

print("frequency 18 @50kg:",griddata(points_marches, values_marches, (18, 2.59, 70), method='linear'))
print("frequency 22 @50kg:",griddata(points_marches, values_marches, (22, 2.14, 65), method='linear'))
print("frequency 26 @50kg:",griddata(points_marches, values_marches, (26, 1.82, 65), method='linear'))
print("frequency 30 @50kg:",griddata(points_marches, values_marches, (30, 1.60, 65), method='linear'))
print("frequency 38 @50kg:",griddata(points_marches, values_marches, (30, 1.3, 65), method='linear'))

print("time :",(time.time()-time_0)/1000,' ms')

import matplotlib.pyplot as plt
freq_marches = griddata(points_marches, values_marches, (grid_x, grid_y, grid_z), method='linear')

plt.figure("Marches @ 80kg")
plt.imshow(freq_marches[:,:,30-1].T, extent=(15,40,1,3), origin='lower')
args=np.argwhere(points_marches[:,2]==80)[:,0]
plt.plot(points_marches[args,0], points_marches[args,1], 'k.', ms=1)

plt.figure("Marches @ 30°")
plt.imshow(freq_marches[120,:,:].T, extent=(0,5,40,100), origin='lower')
args=np.argwhere(points_marches[:,0]==30)[:,0]
plt.plot(points_marches[args,1], points_marches[args,2], 'k.', ms=1)

#points_bandes = np.array([[18,2.61,50],[18,2.62,80],[30,1.65,50],[30,1.68,80],[38,1.36,50],[38,1.4,80]])
#values_bandes = np.array([6.48,6.48,4,4,3.25,3.25])
points_bandes = np.loadtxt('speed_calib_belt.txt', delimiter='\t',skiprows=2,usecols=(1,2,3)) 
values_bandes = np.loadtxt('speed_calib_belt.txt', delimiter='\t',skiprows=2,usecols=(0))

print("frequency 18 @80kg:",griddata(points_bandes, values_bandes, (18, 2.59, 80), method='linear'))
print("frequency 22 @80kg:",griddata(points_bandes, values_bandes, (22, 2.14, 80), method='linear'))
print("frequency 26 @80kg:",griddata(points_bandes, values_bandes, (26, 1.82, 80), method='linear'))
print("frequency 30 @80kg:",griddata(points_bandes, values_bandes, (30, 1.60, 80), method='linear'))
print("frequency 38 @80kg:",griddata(points_bandes, values_bandes, (30, 1.3, 80), method='linear'))

print("frequency 18 @50kg:",griddata(points_bandes, values_bandes, (18, 2.59, 50), method='linear'))
print("frequency 22 @50kg:",griddata(points_bandes, values_bandes, (22, 2.14, 50), method='linear'))
print("frequency 26 @50kg:",griddata(points_bandes, values_bandes, (26, 1.82, 50), method='linear'))
print("frequency 30 @50kg:",griddata(points_bandes, values_bandes, (30, 1.60, 50), method='linear'))
print("frequency 38 @50kg:",griddata(points_bandes, values_bandes, (30, 1.3, 50), method='linear'))

#freq_bandes = griddata(points_bandes, values_bandes, (grid_x, grid_y, grid_z), method='linear')
#plt.figure("Bandes")
#plt.imshow(freq_bandes[:,:,30-1].T, extent=(15,40,1,3), origin='lower')
#args=np.argwhere(points_bandes[:,2]==80)[:,0]
#plt.plot(points_bandes[args,0], points_bandes[args,1], 'k.', ms=1)

plt.show()