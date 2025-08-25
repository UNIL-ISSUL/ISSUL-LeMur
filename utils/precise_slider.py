from kivy.uix.boxlayout import BoxLayout
from kivy.properties import NumericProperty, StringProperty, ListProperty
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, Rectangle


class PreciseSlider(BoxLayout):
    value = NumericProperty(0.0)       # current value
    unit = StringProperty("unit")      # unit (e.g. km/h, °, %)
    var_name = StringProperty("Variable")  # name of the variable
    min_value = NumericProperty(0.0)
    max_value = NumericProperty(10.0)
    step = NumericProperty(0.1)
    precision = NumericProperty(1)
    font_size = NumericProperty(25)     # font size for labels
    bg_color = ListProperty([0.2, 0.2, 0.2, 0.8])  # RGBA background (default grey 20%)

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=5, padding=10, **kwargs)

        # === Background with transparency ===
        with self.canvas.before:
            Color(*self.bg_color)
            self.bg = Rectangle()
        self.bind(pos=self._update_bg, size=self._update_bg, bg_color=self._update_bg_color)

        # === Title label (variable name + value + unit) ===
        self.title_label = Label(
            text=f"{self.var_name}: {self.value:.{self.precision}f} {self.unit}",
            size_hint_y=0.4,
            font_size=self.font_size
        )
        self.add_widget(self.title_label)

        # === Horizontal layout for controls ===
        controls = BoxLayout(orientation="horizontal", spacing=5)

        # bouton -step
        self.btn_minus = Button(text=f"-{self.step}", size_hint_x=0.2)
        self.btn_minus.bind(on_press=lambda x: self.update_value(-self.step))

        # slider
        self.slider = Slider(min=self.min_value, max=self.max_value,
                             step=self.step, value=self.value)
        self.slider.bind(value=self.on_slider_change)

        # bouton +step
        self.btn_plus = Button(text=f"+{self.step}", size_hint_x=0.2)
        self.btn_plus.bind(on_press=lambda x: self.update_value(self.step))

        controls.add_widget(self.btn_minus)
        controls.add_widget(self.slider)
        controls.add_widget(self.btn_plus)

        self.add_widget(controls)

    # === Update background rectangle ===
    def _update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size
    
    def _update_bg_color(self, *args):
        # redraw background with new color
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            self.bg = Rectangle(pos=self.pos, size=self.size)

    # === Value update logic ===
    def update_value(self, delta):
        new_val = min(max(self.slider.value + delta, self.min_value), self.max_value)
        self.slider.value = round(new_val, self.precision)

    def on_slider_change(self, instance, val):
        self.value = round(val, self.precision)
        self.title_label.text = f"{self.var_name}: {self.value:.{self.precision}f} {self.unit}"
