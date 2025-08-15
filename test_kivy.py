from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.slider import Slider
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.graphics import Color, Rectangle


# Fonction pour ajouter un fond coloré aux widgets (debug visuel)
def debug_background(widget, color):
    with widget.canvas.before:
        Color(*color)  # RGBA, entre 0 et 1
        widget._bg = Rectangle(size=widget.size, pos=widget.pos)
    widget.bind(size=lambda w, val: setattr(w._bg, 'size', w.size))
    widget.bind(pos=lambda w, val: setattr(w._bg, 'pos', w.pos))


class SliderScrollTab(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', spacing=10, padding=10, **kwargs)

        # --- SLIDER ---
        slider_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        self.slider_value = Label(text="Valeur: 0", size_hint_x=None, width=100)
        slider = Slider(min=0, max=100, value=0)
        slider.bind(value=self.on_slider_value_change)
        slider_layout.add_widget(self.slider_value)
        slider_layout.add_widget(slider)
        self.add_widget(slider_layout)

        # --- SCROLLVIEW ---
        scrollview = ScrollView(size_hint=(1, 1))
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5, padding=5)
        grid.bind(minimum_height=grid.setter('height'))

        # Ajout de nombreux labels pour tester le défilement
        for i in range(1, 51):
            lbl = Label(text=f"Ligne {i}", size_hint_y=None, height=30)
            grid.add_widget(lbl)

        scrollview.add_widget(grid)
        self.add_widget(scrollview)

    def on_slider_value_change(self, slider, value):
        self.slider_value.text = f"Valeur: {int(value)}"


class TabbedExampleApp(App):
    def build(self):
        panel = TabbedPanel(do_default_tab=False)

        # Onglet 1 avec slider + scrollview
        tab1 = TabbedPanelItem(text='Onglet 1')
        tab1.add_widget(SliderScrollTab())
        panel.add_widget(tab1)

        # Onglet 2 simple
        tab2 = TabbedPanelItem(text='Onglet 2')
        tab2.add_widget(Label(text='Autre contenu'))
        panel.add_widget(tab2)

        return panel


if __name__ == '__main__':
    TabbedExampleApp().run()
