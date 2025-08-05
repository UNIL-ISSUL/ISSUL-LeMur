from kivy_garden.graph import Graph, MeshLinePlot, LinePlot
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.utils import platform
from kivy.core.window import Window
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.lang import Builder
from math import radians, sin, degrees, asin, floor, ceil
import numpy as np
import time, csv, os
from datetime import datetime


def parse(text_widget):
    try:
        return float(text_widget.text.strip().lower().replace(',', '.'))
    except:
        return None

class TabNavigableInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.parent_widget = None

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        if keycode[1] == 'tab' and self.parent_widget:
            Clock.schedule_once(lambda dt: self.parent_widget.handle_tab(self), 0.05)
            return True
        return super().keyboard_on_key_down(window, keycode, text, modifiers)


class IncrementalWidget(BoxLayout):

    def __init__(self, **kwargs):
        Builder.load_file("incremental_widget.kv")
        super().__init__(**kwargs)
        Clock.schedule_once(self._delayed_init)
        Clock.schedule_once(self._post_init)
        self.test_running = False
        self.test_start_time = None
        self.elapsed_time = 0
        self.time_update_event = None
        self.current_dot = None  # pour afficher le rond d'avancement
        self.controller = None

    ### table section ***************************
    def _delayed_init(self, *args):
        self.points = []
        self.test_points = []
        self.add_point()

    def handle_tab(self, instance):
        for row_index, row in enumerate(self.points):
            inputs = [row['time'], row['incl'], row['speed'], row['asc']]
            if instance in inputs:
                current_index = inputs.index(instance)
                if current_index < len(inputs) - 1:
                    inputs[current_index + 1].focus = True
                else:
                    if row_index + 1 < len(self.points):
                        self.points[row_index + 1]['time'].focus = True
                    else:
                        self.add_point()
                        Clock.schedule_once(lambda dt: setattr(self.points[-1]['time'], 'focus', True), 0.05)
                break

    def add_point(self):
        if "points_grid" in self.ids :
            grid = self.ids.points_grid

            ti_time = TabNavigableInput(hint_text='s', multiline=False, input_filter='float')
            ti_incl = TabNavigableInput(hint_text='°', multiline=False, input_filter='float')
            ti_speed = TabNavigableInput(hint_text='km/h', multiline=False, input_filter='float')
            ti_asc = TabNavigableInput(hint_text='m/h', multiline=False, input_filter='float')

            for ti in [ti_time, ti_incl, ti_speed, ti_asc]:
                ti.parent_widget = self

            btn = Button(text="Supprimer", size_hint_x=None, width=100)

            row = {'time': ti_time, 'incl': ti_incl, 'speed': ti_speed, 'asc': ti_asc, 'btn': btn}
            self.points.append(row)

            def remove_row(instance):
                for widget in [ti_time, ti_incl, ti_speed, ti_asc, btn]:
                    grid.remove_widget(widget)
                self.points.remove(row)

            def on_change(instance, value):
                # Update the row with the new value
                self.recalculate(row)
                # Recalculate the graph after any change
                self.update_graph()

            for widget in [ti_time, ti_incl, ti_speed, ti_asc]:
                widget.bind(text=on_change)

            btn.bind(on_press=remove_row)

            for widget in [ti_time, ti_incl, ti_speed, ti_asc, btn]:
                grid.add_widget(widget)
    
    def recalculate(self, row):
        # Récupération des valeurs des champs
        v = parse(row['speed'])
        i = parse(row['incl'])
        a = parse(row['asc'])

        # Si tous les champs sont None on ne fait rien
        if a is None or v is None or i is None:
            return
        
        #Si un champ est déjà calculé on remplace le texte par -
        for field in ['speed', 'incl', 'asc']:
            if row[field].readonly and parse(row[field]) >= 0:
                row[field].readonly = False
                row[field].text = '-1'

        # Si champ marqué 'nc', alors le calculer, verrouiller et griser
        if a < 0 and v is not None and i is not None:
            a_calc = v * sin(radians(i)) * 1000 # Convert km/h to m/h 
            row['asc'].text = f"{a_calc:.2f}"
            row['asc'].readonly = True
            row['asc'].background_color = (0.7, 0.7, 0.7, 1)

        elif v < 0 and a is not None and i is not None and sin(radians(i)) != 0:
            v_calc = (a/1000) / sin(radians(i)) # Convert m/h to km/h
            row['speed'].text = f"{v_calc:.2f}"
            row['speed'].readonly = True
            row['speed'].background_color = (0.7, 0.7, 0.7, 1)

        elif i < 0 and a is not None and v is not None and v != 0:
            try:
                i_calc = degrees(asin((a/1000) / v))
                row['incl'].text = f"{i_calc:.2f}"
                row['incl'].readonly = True
                row['incl'].background_color = (0.7, 0.7, 0.7, 1)
            except:
                pass
        
        # Generate array of points for the graph
        self.test_points = []
        for row in self.points:
            try:
                t = parse(row["time"])
                incl = parse(row["incl"])
                speed = parse(row["speed"])
                asc = parse(row["asc"])
            except ValueError:
                continue
            #add the point to the test_points list if there is no -1 in the values
            if t is not None and incl is not None and speed is not None and asc is not None:
                if -1 not in [t, incl, speed, asc]:
                    # Append the point to the test_points list
                    self.test_points.append({
                        'time': t,
                        'incl': incl,
                        'speed': speed,
                        'asc': asc
                    })
        #Sort the test_points by time
        self.test_points.sort(key=lambda x: x['time'])
        

    ### graph section ***************************
    def _post_init(self, *args):
        # Initialize the graph and its properties
        self.events = []    # List to store events for the graph {"time": ..., "speed": ..., "angle": ..., "comment": ""}
        self.graph_variable = 'inclinaison'
        self.plot = MeshLinePlot(color=[0, 1, 0, 1])
        self.graph = Graph(xlabel='Temps (s)', ylabel='Inclinaison (°)',
                           x_ticks_minor=5, x_ticks_major=10,
                           y_ticks_minor=5, y_ticks_major=10,
                           y_grid_label=True, x_grid_label=True,
                           padding=5, x_grid=True, y_grid=True,
                           xmin=0, xmax=60, ymin=0, ymax=30)
        self.graph.add_plot(self.plot)
        self.ids.graph_view.clear_widgets()
        self.ids.graph_view.add_widget(self.graph)
        self.set_graph_variable('incl')
        self.update_graph()

    def set_graph_variable(self, var_name):
        self.graph_variable = var_name
        if self.graph:
            unit = {
                'incl': 'Inclinaison (°)',
                'speed': 'Vitesse (km/h)',
                'asc': 'Vitesse Asc. (m/h)'
            }.get(var_name, '')
            self.graph.ylabel = unit
        self.update_graph()

    def update_graph(self):
        if not self.test_points:
            return
        # Ajustement dynamique des axes  
        x_vals = [p['time'] for p in self.test_points]
        y_vals = [p[self.graph_variable] for p in self.test_points]
        x_range = max(x_vals) - min(x_vals)
        y_range = max(y_vals) - min(y_vals)
        #avoid division by zero on axes calculation
        if x_range == 0 :
            x_vals = [min(x_vals), max(x_vals) + 1]
            x_range = 1
        if y_range == 0:
            y_vals = [min(y_vals)-1, max(y_vals) + 1]
            y_range = 1
        # Set the graph limits to be multiples of thick major
        self.graph.xmin = floor(min(x_vals) / 10) * 10
        self.graph.xmax = ceil(max(x_vals) / 10) * 10 
        self.graph.ymin = floor(min(y_vals) / 10) * 10
        self.graph.ymax = ceil(max(y_vals) / 10) * 10
        #Set the graphs ticks
        self.graph.x_ticks_major = (self.graph.xmax-self.graph.xmin) / 10
        self.graph.y_ticks_major = (self.graph.ymax-self.graph.ymin) / 5
        self.graph.x_ticks_minor = self.graph.x_ticks_major / 2
        self.graph.y_ticks_minor =self.graph.y_ticks_major / 2
        #add the points to the plot
        self.plot.points = [(p['time'], p[self.graph_variable]) for p in self.test_points]

    ### Events section ***************************
    def refresh_events(self):
        grid = self.ids.events_grid
        grid.clear_widgets()
        for event in self.events:
            grid.add_widget(Label(text="{:.2f}".format(event["time"])))
            grid.add_widget(Label(text="{:.2f}".format(event["speed"])))
            grid.add_widget(Label(text="{:.2f}".format(event["angle"])))
            grid.add_widget(Label(text="{:.2f}".format(event["asc"])))
            grid.add_widget(Button(text="Supprimer", on_release=lambda btn, ev=event: self.delete_event(ev)))
    
    def add_event(self):
        #add event only if the test is running
        if not self.test_running:
            return
        #add a new event at the current time
        current_time = self.elapsed_time  # ou variable que tu utilises
        speed = self.get_speed(current_time)
        angle = self.get_angle(current_time)
        asc = self.get_speed_asc(current_time)

        new_event = {"time": current_time, "speed": speed, "angle": angle, "asc": asc}
        self.events.append(new_event)
        self.draw_event_line(current_time)
        self.refresh_events()

    def draw_event_line(self, time_s):
        line = MeshLinePlot(color=[1, 0, 0, 1])
        line.points = [(time_s, 0), (time_s, 1e9)]
        self.graph.add_plot(line)
    
    def delete_event(self, event):
        #if event is None call recusrsively the funtion for each event
        if event is None:
            for ev in self.events[:]:
                self.delete_event(ev)
            return
        self.events.remove(event)
        self.refresh_events()
        # Remove the event line from the graph
        for plot in self.graph.plots:
            if isinstance(plot, MeshLinePlot) and len(plot.points) == 2 :
                if plot.points[0][0] == event["time"] and plot.points[1][0] == event["time"]:
                    self.graph.remove_plot(plot)
                    break
        self.update_graph()
    
    ### Start/Stop Test section ***************************
    def start_test(self):
        if not self.test_running:
            #clear events
            self.delete_event(None)
            #init running state
            self.test_running = True
            self.test_start_time = time.time()
            #schedule update
            self.time_update_event = Clock.schedule_interval(self.update_test_time, 0.1)
            #move treadmill and start band if connected
            if self.controller :
                #update treamill speed and angle
                self.update_test_time(0.1)
                #start_belt
                self.controller.start_belt()

    def stop_test(self):
        if self.test_running:
            self.test_running = False
            if self.controller :
                #stop_belt
                self.controller.stop_belt()
            if self.time_update_event:
                self.time_update_event.cancel()
                self.time_update_event = None

    def update_test_time(self, dt):
        if not self.test_running:
            return

        self.elapsed_time = time.time() - self.test_start_time
        t = self.elapsed_time

        #stop test is the elapsed time is greater than maximum time
        if t > max([p['time'] for p in self.test_points]):
            self.stop_test()
            self.ids.stop_button.state = 'down'
            self.ids.start_button.state = 'normal'
            return

        #update treadmill speed and angle
        if self.controller :
            speed = self.get_speed(t)
            angle = self.get_angle(t)
            self.controller.set_belt_speed(speed)
            self.controller.set_lift_angle(angle)

        # Mettre à jour l'affichage du temps et des valeurs actuelles
        #self.ids.time_display.text = f"{int(t)} s"
        #self.ids.speed_display.text = f"{speed:.2f} km/h"
        #self.ids.angle_display.text = f"{angle:.2f} °"
        #self.ids.asc_display.text = f"{self.get_speed_asc(t):.2f} m/h"

        # Positionner le point sur le graphique
        self.update_graph_dot(t, self._interpolate(t,self.graph_variable))
    
    def update_graph_dot(self, time_value, y_value):
        if not self.current_dot:
            self.current_dot = MeshLinePlot(color=[1, 1, 0, 1])
            self.graph.add_plot(self.current_dot)
        self.current_dot.points =  [(time_value, 0), (time_value, 1e9)]
    
    def get_speed(self, t):
        return self._interpolate(t,"speed")

    def get_angle(self, t):
        return self._interpolate(t,"incl")

    def get_speed_asc(self, t):
        return self._interpolate(t,"asc")
    
    def _interpolate(self, t, key):
        if not self.test_points:
            return 0

        times = np.array([p["time"] for p in self.test_points])
        values = np.array([p[key] for p in self.test_points])

        if t <= times[0]:
            return values[0]
        elif t >= times[-1]:
            return values[-1]
        else:
            return float(np.interp(t, times, values))

    #### Save/Load Profile section ***************************
    def open_file_dialog(self, action, callback):
        #define file chooser widget et text input
        chooser = FileChooserListView(path="profiles", filters=["*.csv"], dirselect=(action == "save"))
        chooser.bind(on_submit=lambda chooser, selection, touch: submit_from_double_click(selection))
        file_input = TextInput(text="", hint_text="Nom du fichier (ex: test.csv)", size_hint_y=None, height="40dp")
        #add widgets tzo layout
        layout = BoxLayout(orientation="vertical", spacing=10)
        layout.add_widget(chooser)
        if action == "save":
            layout.add_widget(file_input)
        #manage callbacks
        def on_select(instance):
            selected = chooser.selection
            path = chooser.path
            filename = file_input.text.strip()
            # Priorité : fichier sélectionné OU saisie manuelle
            if action == "save":
                if filename:
                    full_path = os.path.join(path, filename)
                elif selected:
                    full_path = selected[0]
                else:
                    return
            else:
                if selected:
                    full_path = selected[0]
                else:
                    return

            popup.dismiss()
            callback(full_path)
        # If the user double-clicks a file, submit it directly
        def submit_from_double_click(selection):
            if action == "load" and selection:
                popup.dismiss()
                callback(selection[0])

        btn = Button(text="Valider", size_hint_y=None, height="40dp")
        btn.bind(on_press=on_select)
        layout.add_widget(btn)

        popup = Popup(title="Sélectionner un fichier", content=layout, size_hint=(0.9, 0.9))
        popup.open()
    
    def save_profile(self):
        def do_save(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["time", "incl", "speed", "asc"])
                for row in self.points:
                    def val(textinput):
                        text = textinput.text.strip()
                        #if textinput is readonly and not empty, return -1
                        if textinput.readonly and textinput.text.strip():
                            text = "-1"
                        return text if text else "-1"

                    writer.writerow([
                        val(row["time"]),
                        val(row["incl"]),
                        val(row["speed"]),
                        val(row["asc"]),
                    ])
        self.open_file_dialog("save", do_save)
    
    def load_profile(self):
        def do_load(filepath):
            if not os.path.exists(filepath):
                return
            with open(filepath, newline="") as f:
                reader = csv.DictReader(f)
                self.points = []
                self.ids.points_grid.clear_widgets()
                for line in reader:
                    self.add_point()
                    row = self.points[-1]
                    for k in ["time", "incl", "speed", "asc"]:
                        value = line[k]
                        row[k].text = value
                    self.recalculate(row)

        self.open_file_dialog("load", do_load)


    ### EXPORT evnts section ***************************
    def export_events_as_csv(self):
        #if test is running, do nothing
        if self.test_running:
            return
        layout = BoxLayout(orientation="vertical", spacing=10, padding=10)
        input_name = TextInput(hint_text="Nom du test", multiline=False, size_hint_y=None, height="40dp")
        layout.add_widget(input_name)

        def save_csv(_):
            name = input_name.text.strip().replace(" ", "_")
            if not name:
                return
            date = date = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            filename = f"{date}-{name}.csv"
            filepath = os.path.join("events", filename)
            self.write_events_to_csv(self.events, filepath)
            popup.dismiss()

        btn = Button(text="Exporter", size_hint_y=None, height="40dp")
        btn.bind(on_press=save_csv)
        layout.add_widget(btn)

        popup = Popup(title="Exporter les événements en CSV", content=layout, size_hint=(0.8, 0.4))
        popup.open()
    
    def write_events_to_csv(self,events, filepath):
        with open(filepath, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Temps (s)", "Vitesse (km/h)", "Inclinaison (°)", "Vitesse verticale (m*/h)"])
            for ev in events:
                writer.writerow([
                    ev.get("time", ""),
                    ev.get("speed", ""),
                    ev.get("angle", ""),
                    ev.get("asc", ""),
                ])
    
    #connect with revpi controller
    def set_controller(self, controller):
        self.controller = controller