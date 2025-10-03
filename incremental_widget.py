from kivy_garden.graph import Graph, MeshLinePlot, ScatterPlot
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.utils import platform
from kivy.core.window import Window
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.properties import NumericProperty, ListProperty
from kivy.clock import Clock
from kivy.lang import Builder
from math import radians, sin, degrees, asin, floor, ceil, log10
import numpy as np
import time, csv, os
from datetime import datetime
from treadmill import compute_tilt, compute_belt_speed, compute_vertical_speed_mh


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
    
def compute_axis_range(values, padding_ratio=0.05, max_minor=5):
    """
    Calcule xmin, xmax, tick_major et tick_minor pour un axe de graphique.

    :param values: Liste de nombres ou nombre unique
    :param padding_ratio: Espace vide ajouté de chaque côté (% de l'intervalle)
    :param max_minor: Nombre maximum de ticks mineurs par tick majeur
    :return: (xmin, xmax, tick_major, tick_minor)
    """
    # Si une seule valeur donnée → liste
    if not hasattr(values, '__iter__'):
        values = [values]

    vmin = min(values)
    vmax = max(values)

    # Cas particulier : toutes les valeurs identiques
    if vmin == vmax:
        vmin -= 1
        vmax += 1

    # Calcul de l'intervalle avec marge
    span = vmax - vmin
    padding = span * padding_ratio
    vmin -= padding
    vmax += padding

    # Ordre de grandeur du pas
    magnitude = 10 ** floor(log10(span))
    tick_major = magnitude

    # Ajustement du pas pour avoir 5 à 10 ticks max
    if span / tick_major < 5:
        tick_major /= 2
    elif span / tick_major > 10:
        tick_major *= 2

    # Arrondi des bornes au multiple du pas
    xmin = floor(vmin / tick_major) * tick_major
    xmax = ceil(vmax / tick_major) * tick_major

    # Tick mineur : diviser le tick majeur en parts égales
    for div in [5, 4, 3, 2, 1]:
        if div <= max_minor:
            #stop if tick_major modulo div == 0
            if tick_major % div == 0:
                tick_minor = tick_major / div
            else:
                tick_minor = 0
            break

    return xmin, xmax, tick_major, tick_minor


class IncrementalWidget(BoxLayout):

    zoom = NumericProperty(1)
    test_points = ListProperty([])

    def __init__(self, **kwargs):
        Builder.load_file("incremental_widget.kv")
        super().__init__(**kwargs)
        Clock.schedule_once(self._delayed_init)
        Clock.schedule_once(self._post_init)
        self.test_running = False
        self.current_dot = None  # pour afficher le rond d'avancement
        self.actual_plot = None  # pour afficher les valeurs actuels
        self.treadmill = None
        self.current_profile_path = None

    ### table section ***************************
    def _delayed_init(self, *args):
        self.points = []
        #self.test_points = []
        self.elapsed_time = 0
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

            ti_time = TabNavigableInput(hint_text='s', multiline=False)#, input_filter='float')
            ti_incl = TabNavigableInput(hint_text='°', multiline=False)#, input_filter='float')
            ti_speed = TabNavigableInput(hint_text='km/h', multiline=False)#, input_filter='float')
            ti_asc = TabNavigableInput(hint_text='m/h', multiline=False)#, input_filter='float')

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
                #Clock.schedule_once(lambda dt:self.update_graph(),0.2)

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
        #self.plot = MeshLinePlot(color=[0, 1, 0, 1])
        self.plot = ScatterPlot(color=[0, 1, 0, 1],point_size=5)
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
        self.update_graph_dot(self.treadmill.get_treadmill_points() if self.treadmill else [])

    def update_graph(self):
        if not self.test_points:
            return
        # Ajustement dynamique des axes  
        x_vals = [p['time'] for p in self.test_points]
        y_vals = [p[self.graph_variable] for p in self.test_points]
        #concatenate with treadmill points if any
        if self.treadmill:
            treadmill_points = self.treadmill.get_treadmill_points()
            if treadmill_points:
                y_vals += [p[self.graph_variable] for p in treadmill_points]
        #adjust graph to data
        xmin, xmax, xmajor, xminor = compute_axis_range(x_vals,0)
        ymin, ymax, ymajor, yminor = compute_axis_range(y_vals,0.1) 

        # Set the graph limits
        self.graph.xmin = xmin
        self.graph.xmax = xmax
        self.graph.ymin = ymin
        self.graph.ymax = ymax
        #Set the graphs ticks
        self.graph.x_ticks_major = xmajor
        self.graph.y_ticks_major = ymajor
        self.graph.x_ticks_minor = xminor
        self.graph.y_ticks_minor = yminor
        #apply zoom
        self.update_graph_zoom(self.zoom)
        
        #add the points to the plot
        self.plot.points = [(p['time'], p[self.graph_variable]) for p in self.test_points]
    
    def update_graph_zoom(self, value):
        self.zoom = value
        #only zoom on x axis the graph
        t = self.elapsed_time
        if not self.test_points:
            return
        xmin, xmax, xmajor, xminor = compute_axis_range([p['time'] for p in self.test_points],0)
        #zoom range
        new_range = (xmax - xmin) / value
        if value > 1 :
            #new x range centered on t
            self.graph.xmin = floor(t)
            self.graph.xmax = ceil(t + new_range)
            self.graph.x_ticks_major = max(1, floor((self.graph.xmax - self.graph.xmin) / 10))
        else: #reset to full range
            self.graph.xmin = xmin
            self.graph.xmax = xmax
            self.graph.x_ticks_major = xmajor
        self.graph.x_ticks_minor = xminor

    ### Events section ***************************
    def refresh_events(self):
        grid = self.ids.events_grid
        grid.clear_widgets()
        for event in self.events:
            grid.add_widget(Label(text="{:.2f}".format(event["time"])))
            grid.add_widget(Label(text="{:.2f}".format(event["speed_sp"])))
            grid.add_widget(Label(text="{:.2f}".format(event["speed_pv"])))
            grid.add_widget(Label(text="{:.2f}".format(event["angle_sp"])))
            grid.add_widget(Label(text="{:.2f}".format(event["angle_pv"])))
            grid.add_widget(Label(text="{:.2f}".format(event["asc_sp"])))
            grid.add_widget(Label(text="{:.2f}".format(event["asc_pv"])))
            #grid.add_widget(Button(text="Supprimer", on_release=lambda btn, ev=event: self.delete_event(ev)))
    
    def add_event(self):
        self.treadmill.record_event("user event")
        #add a new event at the current time
        current_time = self.elapsed_time

        #get setpoints
        speed_sp = self.get_speed(current_time)
        angle_sp = self.get_angle(current_time)
        asc_sp = self.get_speed_asc(current_time)
        #get process values
        speed_pv = self.treadmill.get_belt_speed() if self.treadmill else 0
        angle_pv = self.treadmill.get_lift_angle() if self.treadmill else 0
        asc_pv = self.treadmill.get_vertical_speed() if self.treadmill else 0

        new_event = {
            "time": current_time,
            "speed_sp": speed_sp, "speed_pv": speed_pv,
            "angle_sp": angle_sp, "angle_pv": angle_pv,
            "asc_sp": asc_sp, "asc_pv": asc_pv
        }
        self.events.append(new_event)
        self.draw_event_line(current_time)
        self.refresh_events()

    def draw_event_line(self, time_s):
        line = MeshLinePlot(color=[1, 0, 0, 1])
        line.points = [(time_s, -1e9), (time_s, 1e9)]
        self.graph.add_plot(line)
    
    def delete_event(self, event=None):
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
    
    #update incremental tests
    def update_test(self, delta_t):
        #update graph dot position
        self.update_graph_dot(self.treadmill.get_treadmill_points())
        #get current time
        current_time = self.treadmill.get_elapsed_time()
        self.elapsed_time = current_time
        #udate zoom if is greater than graph xmax
        if self.zoom > 1 and current_time >= self.graph.xmax :
            self.update_graph_zoom(self.zoom)
        #get setpoints for current time
        angle = self.get_angle(current_time+delta_t)
        speed = self.get_speed(current_time+delta_t)
        #set treadmill setpoints
        self.treadmill.set_lift_angle(angle)
        self.treadmill.set_belt_speed(speed)
        #check if current >= last point time
        test_finished = self.test_points and current_time >= self.test_points[-1]['time']
        return test_finished
    
    def update_graph_dot(self, treadmill_points):
        #show a vertical line at the current time on the graph
        if not self.current_dot:
            self.current_dot = MeshLinePlot(color=[1, 1, 0, 1])
            self.graph.add_plot(self.current_dot)
        #get last time value from treadmill points if any
        time_value = 0
        if treadmill_points:
            time_value = treadmill_points[-1]['time']
        self.current_dot.points =  [(time_value, -1e9), (time_value, 1e9)]

        # #Add a new trace with actual values
        if not self.actual_plot :
            self.actual_plot = MeshLinePlot(color=[0, 1, 1, 1])
            self.graph.add_plot(self.actual_plot)
        #update points
        self.actual_plot.points = [(p['time'], p[self.graph_variable]) for p in treadmill_points]
        

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
        
        #check for boundaries
        if t <= times[0]:
            return values[0]
        elif t >= times[-1]:
            return values[-1]
        
        #find the last index of time where time < t
        arg_t = np.searchsorted(times, t) - 1 #get the indice before
        #determine if value at argt is a driven point
        if self.points[arg_t][key].readonly :
            #if driven point, interpolate values use for computation 
            if key == "incl":
                speed = self.get_speed(t)
                asc = self.get_speed_asc(t)
                return compute_tilt(speed, asc)
            elif key == "speed":
                angle = self.get_angle(t)
                asc = self.get_speed_asc(t)
                return compute_belt_speed(angle, asc)
            elif key == "asc":
                angle = self.get_angle(t)
                speed = self.get_speed(t)
                return compute_vertical_speed_mh(angle, speed)
        #interpolate data
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
            self.current_profile_path = filepath
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


    
    #connect with treadmill
    def set_treadmill(self, treadmill):
        self.treadmill = treadmill

    def get_current_test_name(self):
        if self.current_profile_path:
            return os.path.splitext(os.path.basename(self.current_profile_path))[0]
        return "incremental_test"