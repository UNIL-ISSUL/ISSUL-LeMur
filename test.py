import revpimodio2
import struct
rpi = revpimodio2.RevPiModIO(autorefresh=True)
rpi.io.Master_Status_Reset.value=1
rpi.io.Action_Status_Reset_1.value=1
rpi.io.Action_Status_Reset_2.value=1
rpi.io.Action_Status_Reset_3.value=1
rpi.io.belt_frequency.byteorder='big'
rpi.io.belt_frequency.value = 1000
rpi.io.belt_start.value = 0
rpi.io.belt_stop.value = 0
print('set F ',rpi.io.belt_frequency.length)
print('read F ',rpi.io.belt_out_frequency.value)
print('Master status ',rpi.io.Modbus_Master_Status.value)
print('Action 1 status',rpi.io.Modbus_Action_Status_1.value)
print('action 2 status ',rpi.io.Modbus_Action_Status_2.value) 
print('action 3 status ',rpi.io.Modbus_Action_Status_3.value) 