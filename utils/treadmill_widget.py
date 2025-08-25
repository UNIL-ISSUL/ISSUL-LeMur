from kivy.app import App
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Ellipse


class TreadmillWidget(Widget):
    # Variables de configuration
    security_top = None     # True / False / None
    security_bottom = None
    security_left = None
    security_right = None
    emergency_stop = None   # True / False / None
    mode = "belt"           # "belt" ou "step"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self.update_canvas, pos=self.update_canvas)

    def get_color(self, status):
        """Retourne la couleur en fonction du statut"""
        if status is True:
            return (0, 1, 0)  # vert
        elif status is False:
            return (1, 0, 0)  # rouge
        else:
            return (0.5, 0.5, 0.5)  # gris

    def update_canvas(self, *args):
        self.canvas.clear()
        with self.canvas:
            w, h = self.width, self.height

            # Ratio tapis (2.5 : 1.25 → 2:1 visuel)
            treadmill_width = w * 1
            treadmill_height = h * 1

            x = self.center_x - treadmill_width / 2
            y = self.center_y - treadmill_height / 2

            # --- Surface du tapis (12 rectangles) ---
            step_height = treadmill_height / 12
            for i in range(12):
                if self.mode == "belt":
                    Color(0, 0, 0)  # noir
                else:  # step
                    if i % 2 == 0:
                        Color(0, 0, 0)  # noir
                    else:
                        Color(0.26, 0.52, 0.96)  # bleu (même que boutons Kivy)
                        #Color(0.5, 0.5, 0.5)  # bleu (même que boutons Kivy)
                Rectangle(pos=(x, y + i * step_height),
                          size=(treadmill_width, step_height))

            # Sécurités autour du tapis
            border_thickness = 15

            # Haut
            Color(*self.get_color(self.security_top))
            Rectangle(pos=(x, y + treadmill_height),
                      size=(treadmill_width, border_thickness))

            # Bas
            Color(*self.get_color(self.security_bottom))
            Rectangle(pos=(x, y - border_thickness),
                      size=(treadmill_width, border_thickness))

            # Gauche
            Color(*self.get_color(self.security_left))
            Rectangle(pos=(x - border_thickness, y),
                      size=(border_thickness, treadmill_height))

            # Droite
            Color(*self.get_color(self.security_right))
            Rectangle(pos=(x + treadmill_width, y),
                      size=(border_thickness, treadmill_height))

            # Bouton d'arrêt d'urgence à droite
            btn_width, btn_height = 60, 100
            btn_x = x + treadmill_width + 2 * border_thickness
            btn_y = y + treadmill_height / 2 - btn_height / 2

            # Rectangle du bouton
            Color(0.3, 0.3, 0.3)
            Rectangle(pos=(btn_x, btn_y), size=(btn_width, btn_height))

            # Champignon (cercle au centre)
            Color(*self.get_color(self.emergency_stop))
            radius = min(btn_width, btn_height) / 1.5
            Ellipse(pos=(btn_x + btn_width / 2 - radius / 2, btn_y + btn_height / 2 - radius / 2),
                    size=(radius, radius))