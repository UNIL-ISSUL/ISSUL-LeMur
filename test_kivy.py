from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.slider import Slider
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout


class SliderScrollTest(App):
    def build(self):
        root = BoxLayout(orientation='vertical', spacing=10, padding=10)

        # --- SLIDER ---
        slider_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        self.slider_value = Label(text="Valeur: 0", size_hint_x=None, width=100)

        slider = Slider(min=0, max=100, value=0)
        slider.bind(value=self.on_slider_value_change)

        slider_layout.add_widget(self.slider_value)
        slider_layout.add_widget(slider)
        root.add_widget(slider_layout)

        # --- SCROLLVIEW ---
        scrollview = ScrollView(size_hint=(1, 1))
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5, padding=5)
        grid.bind(minimum_height=grid.setter('height'))

        # Ajout de nombreux labels pour tester le défilement
        for i in range(1, 51):
            grid.add_widget(Label(text=f"Ligne {i}", size_hint_y=None, height=30))

        scrollview.add_widget(grid)
        root.add_widget(scrollview)

        return root

    def on_slider_value_change(self, slider, value):
        self.slider_value.text = f"Valeur: {int(value)}"


if __name__ == '__main__':
    SliderScrollTest().run()
