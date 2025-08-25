from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from precise_slider import PreciseSlider


class DemoApp(App):
    def build(self):
        root = BoxLayout(orientation="vertical", padding=10, spacing=10)

        # Exemple 1 : vitesse
        speed_widget = PreciseSlider(value=8.0, min_value=0, var_name="Vitesse",
                                     max_value=30, step=0.1, unit="km/h", precision=2)

        # Exemple 2 : inclinaison
        angle_widget = PreciseSlider(value=5.0, min_value=0, var_name="Inclinaison",
                                     max_value=90, step=0.1, unit="°", precision=1)

        # Exemple 3 : puissance
        power_widget = PreciseSlider(value=150.0, min_value=0, var_name="Puissance",
                                     max_value=400, step=1.0, unit="W", precision=0, height=200, size_hint_y=None)

        root.add_widget(speed_widget)
        root.add_widget(angle_widget)
        root.add_widget(power_widget)

        return root


if __name__ == "__main__":
    DemoApp().run()
