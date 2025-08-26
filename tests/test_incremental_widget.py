from kivy.app import App
from incremental_widget import IncrementalWidget

class TestApp(App):
    def build(self):
        return IncrementalWidget()

if __name__ == '__main__':
    TestApp().run()
