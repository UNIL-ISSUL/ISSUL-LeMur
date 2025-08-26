from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout


class TabsExample(App):
    def build(self):
        root = BoxLayout(orientation="vertical")

        # --- Barre d'onglets ---
        tab_bar = BoxLayout(size_hint_y=None, height=40)

        btn_slider = ToggleButton(text="Slider", group="tabs", state="down")
        btn_scroll = ToggleButton(text="Scroll", group="tabs")

        tab_bar.add_widget(btn_slider)
        tab_bar.add_widget(btn_scroll)

        root.add_widget(tab_bar)

        # --- Gestionnaire d'écrans ---
        sm = ScreenManager()

        # Écran Slider
        slider_screen = Screen(name="slider_tab")
        slider_layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        self.slider_value = Label(text="Valeur: 0")
        slider = Slider(min=0, max=100, value=0)
        slider.bind(value=self.on_slider_value_change)
        slider_layout.add_widget(self.slider_value)
        slider_layout.add_widget(slider)
        slider_screen.add_widget(slider_layout)
        sm.add_widget(slider_screen)

        # Écran ScrollView
        scroll_screen = Screen(name="scroll_tab")
        scroll = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5, padding=5)
        grid.bind(minimum_height=grid.setter('height'))
        for i in range(1, 51):
            grid.add_widget(Label(text=f"Ligne {i}", size_hint_y=None, height=30))
        scroll.add_widget(grid)
        scroll_screen.add_widget(scroll)
        sm.add_widget(scroll_screen)

        root.add_widget(sm)

        # --- Actions pour changer d'onglet ---
        btn_slider.bind(on_press=lambda x: setattr(sm, 'current', 'slider_tab'))
        btn_scroll.bind(on_press=lambda x: setattr(sm, 'current', 'scroll_tab'))

        return root

    def on_slider_value_change(self, slider, value):
        self.slider_value.text = f"Valeur: {int(value)}"


if __name__ == '__main__':
    TabsExample().run()
