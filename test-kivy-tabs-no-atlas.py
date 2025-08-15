# test_kivy_tabs_no_atlas.py
from kivy.app import App
from kivy.lang import Builder
from kivy.metrics import dp

KV = f"""
#:import dp kivy.metrics.dp

<TabHeader@TabbedPanelHeader>:
    # Neutralise les images d'arrière-plan (atlas) et force une couleur
    background_normal: ''
    background_down: ''
    background_color: (0.24, 0.24, 0.24, 1) if self.state=='normal' else (0.36, 0.36, 0.36, 1)
    color: 1, 1, 1, 1
    # Optionnel : padding interne du texte
    padding: dp(12), dp(8)

<TabStrip@TabbedPanelStrip>:
    # Bande des onglets : pas d'image, fond uni
    canvas.before:
        Color: 
            rgba :0.16, 0.16, 0.16, 1
        Rectangle: 
            size: self.size
            pos: self.pos

BoxLayout:
    orientation: 'vertical'
    padding: dp(10); spacing: dp(10)
    canvas.before:
        Color: 
            rgba:0.10, 0.10, 0.10, 1  # fond global
        Rectangle: 
            size: self.size
            pos: self.pos

    TabbedPanel:
        do_default_tab: False
        tab_height: dp(40)
        # Neutralise le fond par défaut du contenu (atlas)
        background_image: ''
        background_color: 0.12, 0.12, 0.12, 1
        # Associe notre strip custom sans atlas
        strip_image: ''     # pas d'image
        strip_border: 0, 0, 0, 0
        # IMPORTANT: forcer le type de strip via classe custom
        _strip_cls: 'TabStrip'

        TabbedPanelItem:
            text: 'Contrôles'
            # Applique notre header custom
            default_tab_cls: 'TabHeader'
            BoxLayout:
                orientation: 'vertical'
                spacing: dp(10); padding: dp(10)
                size_hint_y: 1

                BoxLayout:
                    size_hint_y: None
                    height: dp(48)
                    Label:
                        text: 'Valeur: ' + str(int(slider.value))
                        size_hint_x: None
                        width: dp(120)
                    Slider:
                        id: slider
                        min: 0; max: 100; value: 50

                # ScrollView avec contenu
                ScrollView:
                    size_hint: 1, 1
                    bar_width: dp(6)
                    scroll_type: ['bars', 'content']
                    effect_cls: 'ScrollEffect'
                    # Un fond uni pour bien voir les limites
                    canvas.before:
                        Color: 
                            rgba: 0.18, 0.18, 0.18, 1
                        Rectangle: 
                            size: self.size
                            pos: self.pos

                    GridLayout:
                        id: gl
                        cols: 1
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(6); padding: dp(6), dp(6)
                        # Chaque entrée
                        Label:
                            text: '\\n'.join([f"Ligne {{i}}" for i in range(1, 101)])
                            size_hint_y: None
                            height: self.texture_size[1]
                            text_size: self.width, None

        TabbedPanelItem:
            text: 'Autre'
            default_tab_cls: 'TabHeader'
            BoxLayout:
                Label:
                    text: 'Deuxième onglet'
"""

class Demo(App):
    def build(self):
        return Builder.load_string(KV)

if __name__ == "__main__":
    Demo().run()
