
from kivy.app import App
from treadmill_widget import TreadmillWidget
from treadmill_stack import TreadmillStackLayout

class TreadmillApp(App):
    def build(self):
        widget = TreadmillStackLayout()
        widget.security_top = False
        widget.security_bottom = False
        widget.security_left = False
        widget.security_right = False
        widget.emergency_stop = False
        widget.mode_belt = True
        widget.font_size = 20
        #widget.update_canvas()
        return widget


if __name__ == "__main__":
    TreadmillApp().run()