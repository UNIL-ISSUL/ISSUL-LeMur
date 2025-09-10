
from kivy.app import App
from treadmill_layout import TreadmillLayout

class TreadmillApp(App):
    def build(self):
        widget = TreadmillLayout()
        widget.safeties = {
            'top': False,
            'bottom': False,
            'left': False,
            'right': False,
            'emergency': False
        }
        widget.mode_belt = True
        widget.font_size = 20
        #widget.update_canvas()
        return widget


if __name__ == "__main__":
    TreadmillApp().run()