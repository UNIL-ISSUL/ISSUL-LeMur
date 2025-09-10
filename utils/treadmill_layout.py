from kivy.graphics import Rectangle
from kivy.uix.stacklayout import StackLayout
from kivy.uix.togglebutton import ToggleButton
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty

def make_vertical_text(text):
    """Ajoute des \n entre chaque caractère pour un affichage vertical"""
    if not text:
        return ""
    return '\n'.join(text)

def bool2state(value):
    """Convertit un booléen en état de bouton ('down' ou 'normal')"""
    return 'down' if value else 'normal'

class TreadmillLayout(StackLayout):
     # Variables de configuration
    safeties = ObjectProperty({})
    mode_belt = BooleanProperty(False)  # True pour "belt", False pour "step"
    font_size = NumericProperty(5)
    
    def __init__(self, **kwargs):
        #init and add bind function
        super().__init__(orientation="lr-tb", **kwargs)
        self.bind(
            safeties=self._update,
            mode_belt=self._update,
            font_size=self._update_font_size
        )
        #define widgets
        self.emergency_stop_widget = []
        for i  in range(4) :
            self.emergency_stop_widget.append(SecurityToggleButton(size_hint=(0.15,0.15),
                                                           text=make_vertical_text('STOP'),
                                                           font_size=self.font_size,
                                                           state='down',
                                                           on_press=self._update))
        self.top_widget = SecurityToggleButton(size_hint=(0.7,0.15),
                                       text= 'SÉCURITÉ AVANT',
                                       font_size=self.font_size,
                                       state='down',
                                       on_press=self._update)
        self.left_widget = SecurityToggleButton(size_hint=(0.15,0.7),
                                        text = make_vertical_text('SÉCURITÉ GAUCHE'),
                                        font_size=self.font_size,
                                        halign='center',
                                        state='down',
                                        on_press=self._update)
        self.center_widget = ToggleButton(size_hint=(0.7,0.7),
                                          text='ESCALIER' if self.mode_belt else 'BANDE',
                                          font_size=self.font_size,
                                          state='down',
                                          on_press=self._update)
        self.right_widget = SecurityToggleButton(size_hint=(0.15,0.7),
                                         text=make_vertical_text('SÉCURITÉ DROITE'),
                                         font_size=self.font_size,
                                         halign='center',
                                         state='down',
                                         on_press=self._update)
        self.bottom_widget = SecurityToggleButton(size_hint=(0.7,0.15),
                                          text='SÉCURITÉ ARRIÈRE',
                                          font_size=self.font_size,
                                          state='down',
                                          on_press=self._update)
        #add widgets
        self.add_widget(self.emergency_stop_widget[0])
        self.add_widget(self.top_widget)
        self.add_widget(self.emergency_stop_widget[1])
        self.add_widget(self.left_widget)
        self.add_widget(self.center_widget)
        self.add_widget(self.right_widget)
        self.add_widget(self.emergency_stop_widget[2])
        self.add_widget(self.bottom_widget)
        self.add_widget(self.emergency_stop_widget[3])

    def _update(self, *args):
        for i in range(4):
            self.emergency_stop_widget[i].state = bool2state(self.safeties.get('emergency', True))
        self.top_widget.state = bool2state(self.safeties.get('top', True))
        self.left_widget.state = bool2state(self.safeties.get('left', True))
        self.center_widget.state = bool2state(self.mode_belt)
        self.center_widget.text = 'ESCALIER' if self.mode_belt else 'BANDE'
        self.right_widget.state = bool2state(self.safeties.get('right', True))
        self.bottom_widget.state = bool2state(self.safeties.get('bottom', True))

    def _update_font_size(self, *args):
        for widget in self.children:
            widget.font_size = self.font_size
            if widget == self.center_widget:
                widget.font_size = self.font_size * 1.5
        # for widget in self.emergency_stop_widget:
        #     widget.font_size = self.font_size
        # self.top_widget.font_size = self.font_size
        # self.left_widget.font_size = self.font_size
        # self.center_widget.font_size = self.font_size * 1.5  # Center widget larger font
        # self.right_widget.font_size = self.font_size
        # self.bottom_widget.font_size = self.font_size

class SecurityToggleButton(ToggleButton):
    """ToggleButton personnalisé pour les sécurités"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(state=self._update_appearance)
    
    def _update_appearance(self, *args):
        """Met à jour l'apparence selon l'état"""
        if self.state == 'down':
            #self.background_down = ''
            self.background_color = [10, 0, 0, 1]  # Rouge pour actif
            self.color = [1, 1, 0, 1]  # Texte jaune
        else:
            self.background_color = [1,1,1,1]
            self.color = [1, 1, 1, 1]  # Texte blanc
