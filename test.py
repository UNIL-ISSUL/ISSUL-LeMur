import os
os.environ['KIVY_WINDOW'] = 'egl_rpi'
#os.environ['KIVY_WINDOW'] = 'sdl2'
os.environ['KIVY_GL_BACKEND'] = 'gl'
#os.environ['KIVY_GL_BACKEND'] ='sdl2/gl'
#os.environ['KIVY_BCM_DISPMANX_ID'] = '2'
#os.environ['DISPLAY'] = 'localhost:0.0'
print("KIVY_ENVIRON : ", os.environ['KIVY_WINDOW'])
print("KIVY_GL_BACKEND : ", os.environ['KIVY_GL_BACKEND'])
#print("KIVY_BCM_DISPMANX_ID : ", os.environ['KIVY_BCM_DISPMANX_ID'])

from kivy.core.window import Window