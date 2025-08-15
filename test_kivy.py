from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.slider import Slider
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, Rectangle


# Fonction pour ajouter un fond coloré aux widgets (debug visuel)
def debug_background(widget, color):
    with widget.canvas.before:
        Color(*color)  # RGBA, entre 0 et 1
        widget._bg = Rectangle(size=widget.size, pos=widget.pos)
    widget.bind(size=lambda w, val: setattr(w._bg, 'size', w.size))
    widget.bind(pos=lambda w, val: setattr(w._bg, 'pos', w.pos))


class SliderScrollTest(App):
    def build(self):
        root = BoxLayout(orientation='vertical', spacing=10, padding=10)
        #debug_background(root, (0.8, 0.8, 0.8, 1))  # gris clair

        # --- SLIDER ---
        slider_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        #debug_background(slider_layout, (1, 0, 0, 0.3))  # rouge transparent


        self.slider_value = Label(text="Valeur: 0", size_hint_x=None, width=100)
        #debug_background(self.slider_value, (0, 0, 1, 0.3))  # bleu transparent


        #slider = Slider(min=0, max=100, value=0, size_hint_y=None, height=150)
        #debug_background(slider, (0, 1, 0, 0.5))  # vert plus visible
        slider = Slider(min=0, max=100, value=0)
        #debug_background(slider, (0, 1, 0, 0.3))  # vert transparent
        slider.bind(value=self.on_slider_value_change)

        slider_layout.add_widget(self.slider_value)
        slider_layout.add_widget(slider)
        root.add_widget(slider_layout)

        # --- SCROLLVIEW ---
        scrollview = ScrollView(size_hint=(1, 1))
        #debug_background(scrollview, (1, 1, 0, 0.3))  # jaune transparent

        grid = GridLayout(cols=1, size_hint_y=None, spacing=5, padding=5)
        #debug_background(grid, (0.5, 0, 0.5, 0.3))  # violet transparent
        grid.bind(minimum_height=grid.setter('height'))

        # Ajout de nombreux labels pour tester le défilement
        for i in range(1, 51):
            lbl = Label(text=f"Ligne {i}", size_hint_y=None, height=30)
            #debug_background(lbl, (0, 1, 1, 0.3))  # cyan transparent
            grid.add_widget(lbl)

        scrollview.add_widget(grid)
        root.add_widget(scrollview)

        return root

    def on_slider_value_change(self, slider, value):
        self.slider_value.text = f"Valeur: {int(value)}"


if __name__ == '__main__':
    SliderScrollTest().run()
