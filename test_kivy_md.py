from kivymd.app import MDApp
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.slider import MDSlider
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.tab import MDTabs, MDTabsBase
from kivy.metrics import dp


class Tab(MDBoxLayout, MDTabsBase):
    """Un onglet qui peut contenir n'importe quel layout."""
    pass


class TestMDTabsApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"

        root = MDTabs()

        # --- Onglet Slider ---
        tab_slider = Tab(orientation="vertical", padding=dp(10), spacing=dp(10))
        tab_slider.title = "Slider"

        self.slider_value = MDLabel(text="Valeur: 0", halign="center")
        slider = MDSlider(min=0, max=100, value=0)
        slider.bind(value=self.on_slider_value_change)

        tab_slider.add_widget(self.slider_value)
        tab_slider.add_widget(slider)
        root.add_widget(tab_slider)

        # --- Onglet ScrollView ---
        tab_scroll = Tab(orientation="vertical")
        tab_scroll.title = "Scroll"

        scroll = MDScrollView()
        grid = MDGridLayout(cols=1, spacing=dp(5), padding=dp(5), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        for i in range(1, 51):
            grid.add_widget(MDLabel(text=f"Ligne {i}", size_hint_y=None, height=dp(30)))

        scroll.add_widget(grid)
        tab_scroll.add_widget(scroll)
        root.add_widget(tab_scroll)

        return root

    def on_slider_value_change(self, slider, value):
        self.slider_value.text = f"Valeur: {int(value)}"


if __name__ == '__main__':
    TestMDTabsApp().run()
