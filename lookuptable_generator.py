#generate lookup table for belt speed calibration
import numpy as np
from scipy.interpolate import griddata
import time
import math

#motor control value is frequency in Hz
#input variable are angle [°], speed [km/h] and weight [kg]
#points_marches = np.array([[18,2.83,50],[18,2.83,80],[30,1.79,50],[30,1.81,80],[38,1.48,50],[38,1.49,80],[18,2.11,50],[18,2.12,80],[30,1.34,50],[30,1.37,80],[38,1.12,50],[38,1.16,80],[30,2.26,80]])
#values_marches = np.array([6.48,6.48,4,4,3.25,3.25,4.85,4.85,3,3,2.44,2.44,5])

points_etude = np.array([[18,2.59],[22,2.14],[26,1.82],[30,1.60],[34,1.43],[38,1.3]])

points_marches = np.loadtxt('speed_calib_steps.txt', delimiter='\t',skiprows=2,usecols=(1,2,3),comments='#')
values_marches = np.loadtxt('speed_calib_steps.txt', delimiter='\t',skiprows=2,usecols=(0),comments='#')

grid_x, grid_y, grid_z = np.mgrid[18:38:200j, 1:3.5:250j, 50:80:30j]

import matplotlib.pyplot as plt
freq_marches_nearest = griddata(points_marches, values_marches, (grid_x, grid_y, grid_z), method='nearest')
freq_marches_linear = griddata(points_marches, values_marches, (grid_x, grid_y, grid_z), method='linear')

plt.figure("Marches @ 80kg")
plt.imshow(freq_marches_nearest[:,:,30-1].T, extent=(18,38,1,3.5), origin='lower',aspect='auto')
plt.imshow(freq_marches_linear[:,:,30-1].T, extent=(18,38,1,3.5), origin='lower',aspect='auto')
plt.axis([16,40,1,3.5])
args=np.argwhere(points_marches[:,2]==80)[:,0]
plt.plot(points_marches[args,0], points_marches[args,1], 'k.', ms=6)
plt.plot(points_etude[:,0], points_etude[:,1], 'r.', ms=6)

plt.figure("Marches @ 50kg")
plt.imshow(freq_marches_nearest[:,:,10-1].T, extent=(18,38,1,3.5), origin='lower',aspect='auto')
plt.imshow(freq_marches_linear[:,:,10-1].T, extent=(18,38,1,3.5), origin='lower',aspect='auto')
plt.axis([16,40,1,3.5])
args=np.argwhere(points_marches[:,2]==50)[:,0]
plt.plot(points_marches[args,0], points_marches[args,1], 'k.', ms=6)
plt.plot(points_etude[:,0], points_etude[:,1], 'r.', ms=6)

#points_bandes = np.array([[18,2.61,50],[18,2.62,80],[30,1.65,50],[30,1.68,80],[38,1.36,50],[38,1.4,80]])
#values_bandes = np.array([6.48,6.48,4,4,3.25,3.25])
points_bandes = np.loadtxt('speed_calib_belt.txt', delimiter='\t',skiprows=2,usecols=(1,2,3)) 
values_bandes = np.loadtxt('speed_calib_belt.txt', delimiter='\t',skiprows=2,usecols=(0))

freq_bandes_nearest = griddata(points_bandes, values_bandes, (grid_x, grid_y, grid_z), method='nearest')
freq_bandes_linear = griddata(points_bandes, values_bandes, (grid_x, grid_y, grid_z), method='linear')
plt.figure("Bandes @80kg")
plt.imshow(freq_bandes_nearest[:,:,30-1].T, extent=(18,38,1,3.5), origin='lower',aspect='auto')
plt.imshow(freq_bandes_linear[:,:,30-1].T, extent=(18,38,1,3.5), origin='lower',aspect='auto')
plt.axis([16,40,1,3.5])
args=np.argwhere(points_bandes[:,2]==80)[:,0]
plt.plot(points_bandes[args,0], points_bandes[args,1], 'k.', ms=6)
plt.plot(points_etude[:,0], points_etude[:,1], 'r.', ms=6)

plt.figure("Bandes @50kg")
plt.imshow(freq_bandes_nearest[:,:,10-1].T, extent=(18,38,1,3.5), origin='lower',aspect='auto')
plt.imshow(freq_bandes_linear[:,:,10-1].T, extent=(18,38,1,3.5), origin='lower',aspect='auto')
#increase vertical axis length
plt.axis([16,40,1,3.5])
args=np.argwhere(points_bandes[:,2]==50)[:,0]
plt.plot(points_bandes[args,0], points_bandes[args,1], 'k.', ms=6)
plt.plot(points_etude[:,0], points_etude[:,1], 'r.', ms=6)

for mode in ["belt ","steps"] :
    for weight in [72] :
        for point in points_etude :
            if mode == "belt " :
                print('On',mode,"@",weight,"kg","angle:",point[0],"speed:",point[1],"frequency:",format(griddata(points_bandes, values_bandes, (point[0], point[1], weight), method='linear'),'.2f'))
            else :
                print('On',mode,"@",weight,"kg","angle:",point[0],"speed:",point[1],"frequency:",format(griddata(points_marches, values_marches, (point[0], point[1], weight), method='linear'),'.2f'))

plt.show()