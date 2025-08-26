from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.properties import NumericProperty
from kivy.uix.slider import Slider
from kivy.graphics import Color, Rectangle, Ellipse


class CustomSlider(Slider):
    handle_radius = NumericProperty(15)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(value=self.update_canvas, pos=self.update_canvas, size=self.update_canvas)

    def update_canvas(self, *args):
        self.canvas.after.clear()
        with self.canvas.after:
            # --- Rail (toujours visible, au-dessus) ---
            Color(0.7, 0.7, 0.7)  # gris clair
            rail_height = 8
            Rectangle(
                pos=(self.x, self.center_y - rail_height / 2),
                size=(self.width, rail_height)
            )

            # --- Curseur (rond bleu) ---
            Color(0.1, 0.6, 0.9)  # bleu
            knob_x = self.x + (self.width - self.handle_radius * 2) * (
                (self.value - self.min) / (self.max - self.min)
            )
            Ellipse(
                pos=(knob_x, self.center_y - self.handle_radius),
                size=(self.handle_radius * 2, self.handle_radius * 2)
            )


class TestApp(App):
    def build(self):
        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)

        self.value_label = Label(text="Valeur : 50", font_size=24)

        self.slider = CustomSlider(min=0, max=100, value=50)
        self.slider.bind(value=self.on_value_change)

        layout.add_widget(self.slider)
        layout.add_widget(self.value_label)
        return layout

    def on_value_change(self, slider, value):
        self.value_label.text = f"Valeur : {int(value)}"


if __name__ == "__main__":
    TestApp().run()
