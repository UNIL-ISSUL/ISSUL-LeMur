import ast
if not hasattr(ast, 'Str'):
    class AstStrShim: pass
    ast.Str = AstStrShim
# System Info Widget for LeMur RevPi telemetry
import os
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import (
    BooleanProperty,
    NumericProperty,
    StringProperty,
    ObjectProperty,
    ColorProperty,
)
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock

class SystemInfoWidget(BoxLayout):
    treadmill = ObjectProperty(None)

    # Global Hardware & PLC Status
    connected = BooleanProperty(False)
    connection_text = StringProperty("MODE SIMULATION (PC)")
    connection_bg = ColorProperty([0.85, 0.55, 0.1, 1])
    cycletime_text = StringProperty("100 ms")
    ioerrors_text = StringProperty("0")
    ioerrors_bg = ColorProperty([0.2, 0.5, 0.2, 1])
    modbus_master_text = StringProperty("OK (0)")
    modbus_master_bg = ColorProperty([0.2, 0.5, 0.2, 1])
    stall_warning = BooleanProperty(False)

    # Digital Outputs
    belt_start_val = BooleanProperty(False)
    belt_stop_val = BooleanProperty(False)
    belt_dir_val = BooleanProperty(True)
    use_steps_val = BooleanProperty(False)

    # Digital Inputs (Safeties)
    secu_front_val = BooleanProperty(False)
    secu_back_val = BooleanProperty(False)
    secu_left_val = BooleanProperty(False)
    secu_right_val = BooleanProperty(False)
    secu_emergency_val = BooleanProperty(False)
    secu_front_back_val = BooleanProperty(False)

    # Modbus & Speed Registers
    belt_speed_sp_text = StringProperty("0.00 km/h")
    belt_speed_cmd_text = StringProperty("0.00 km/h")
    freq_sent_text = StringProperty("0.00 Hz")
    sp_0_text = StringProperty("0")
    sp_1_text = StringProperty("0")
    speed_pv_text = StringProperty("0.00 km/h")
    encoder_raw_text = StringProperty("0 mm/s")
    freq_pv_text = StringProperty("-- Hz")
    modbus_act1_text = StringProperty("0 (OK)")
    modbus_act1_bg = ColorProperty([0.2, 0.5, 0.2, 1])
    modbus_act2_text = StringProperty("0 (OK)")
    lift_sp_text = StringProperty("0.0°")
    lift_pv_text = StringProperty("0.0°")
    pid_enable_text = StringProperty("0")
    drift_pct_text = StringProperty("0.0 %")

    # Active view mode: 'summary' or 'explorer'
    view_mode = StringProperty('summary')
    explorer_filter_type = StringProperty('ALL')
    explorer_filter_search = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._last_log_count = 0
        self._last_log_top_time = ""
        self._all_ios_cache = []

    def set_treadmill(self, treadmill):
        self.treadmill = treadmill

    def switch_view(self, mode):
        self.view_mode = mode
        if mode == 'explorer':
            Clock.schedule_once(lambda dt: self.refresh_explorer(), 0.05)

    def reset_modbus_clicked(self):
        if self.treadmill and hasattr(self.treadmill, 'reset_modbus'):
            self.treadmill.reset_modbus()

    def pulse_start_clicked(self):
        if self.treadmill and hasattr(self.treadmill, 'pulse_start'):
            self.treadmill.pulse_start()

    def clear_log_clicked(self):
        if self.treadmill and hasattr(self.treadmill, 'clear_diagnostic_log'):
            self.treadmill.clear_diagnostic_log()
            self._update_log_display([])

    def set_explorer_type_filter(self, filter_type):
        self.explorer_filter_type = filter_type
        self.refresh_explorer()

    def on_search_text_changed(self, text):
        self.explorer_filter_search = text.strip().lower()
        self.refresh_explorer()

    def update_info(self):
        if not self.treadmill:
            return

        info = self.treadmill.get_system_info()
        if not info:
            return

        # 1. Global status
        self.connected = info.get("connected", False)
        if self.connected:
            self.connection_text = "REVPI EN LIGNE"
            self.connection_bg = [0.15, 0.65, 0.25, 1]
        else:
            self.connection_text = "MODE SIMULATION (PC)"
            self.connection_bg = [0.85, 0.55, 0.1, 1]

        cyc = info.get("cycletime_ms", 100)
        self.cycletime_text = f"{cyc} ms"

        errs = info.get("ioerrors", 0)
        self.ioerrors_text = str(errs)
        self.ioerrors_bg = [0.8, 0.2, 0.2, 1] if errs > 0 else [0.2, 0.5, 0.2, 1]

        # 2. Digital Outputs
        outputs = info.get("outputs", {})
        self.belt_start_val = bool(outputs.get("belt_start", False))
        self.belt_stop_val = bool(outputs.get("belt_stop", False))
        self.belt_dir_val = bool(outputs.get("belt_dir", True))
        self.use_steps_val = bool(outputs.get("use_steps", False))

        # 3. Digital Inputs
        inputs = info.get("inputs", {})
        self.secu_front_val = bool(inputs.get("secu_front", False))
        self.secu_back_val = bool(inputs.get("secu_back", False))
        self.secu_left_val = bool(inputs.get("secu_left", False))
        self.secu_right_val = bool(inputs.get("secu_right", False))
        self.secu_emergency_val = bool(inputs.get("secu_emergency", False))
        self.secu_front_back_val = bool(inputs.get("secu_front_back", False))

        # 4. Modbus registers
        modbus = info.get("modbus", {})
        controller = info.get("controller", {})

        sp = controller.get("belt_speed_SP", 0.0)
        cmd = controller.get("belt_speed_CMD", 0.0)
        pv = controller.get("belt_speed_PV", 0.0)
        drift = controller.get("drift_pct", 0.0)
        self.stall_warning = controller.get("stall_warning", False)

        self.belt_speed_sp_text = f"{sp:.2f} km/h"
        self.belt_speed_cmd_text = f"{cmd:.2f} km/h"
        self.speed_pv_text = f"{pv:.2f} km/h"
        self.drift_pct_text = f"{drift:.1f} %"

        freq_sent = modbus.get("frequency_sent_hz", 0.0)
        self.freq_sent_text = f"{freq_sent:.2f} Hz"

        self.sp_0_text = str(modbus.get("belt_speed_SP_0", 0))
        self.sp_1_text = str(modbus.get("belt_speed_SP_1", 0))

        enc_mms = modbus.get("encoder_feedback_speed_mms", 0)
        self.encoder_raw_text = f"{enc_mms} mm/s"

        cur_freq = modbus.get("belt_current_frequency")
        self.freq_pv_text = f"{cur_freq:.2f} Hz" if cur_freq is not None else "-- Hz"

        m_master = modbus.get("Modbus_Master_Status", 0)
        if m_master == 0:
            self.modbus_master_text = "OK (0)"
            self.modbus_master_bg = [0.2, 0.5, 0.2, 1]
        else:
            self.modbus_master_text = f"ERREUR ({m_master})"
            self.modbus_master_bg = [0.8, 0.2, 0.2, 1]

        m_act1 = modbus.get("Modbus_Action_Status_1", 0)
        if m_act1 == 0:
            self.modbus_act1_text = "OK (0)"
            self.modbus_act1_bg = [0.2, 0.5, 0.2, 1]
        else:
            self.modbus_act1_text = f"CODE {m_act1}"
            self.modbus_act1_bg = [0.8, 0.2, 0.2, 1]

        m_act2 = modbus.get("Modbus_Action_Status_2", 0)
        self.modbus_act2_text = f"Code {m_act2}" if m_act2 is not None else "--"

        l_sp = modbus.get("lift_angle_SP", 0)
        self.lift_sp_text = f"{(l_sp / 100.0):.1f}° (reg: {l_sp})"

        l_cur = modbus.get("lift_angle_current", 0)
        self.lift_pv_text = f"{(l_cur / 100.0):.1f}° (reg: {l_cur})"

        pid_en = modbus.get("pid_enable", 0)
        self.pid_enable_text = f"{bin(pid_en)} ({pid_en})"

        # 5. Log updates
        diag_log = info.get("diagnostic_log", [])
        top_time = diag_log[0]["time"] if diag_log else ""
        if len(diag_log) != self._last_log_count or top_time != self._last_log_top_time:
            self._last_log_count = len(diag_log)
            self._last_log_top_time = top_time
            self._update_log_display(diag_log)

        # 6. Explorer updates
        all_ios = info.get("all_ios", [])
        self._all_ios_cache = all_ios

    def _update_log_display(self, log_entries):
        if not hasattr(self.ids, 'log_container'):
            return
        container = self.ids.log_container
        container.clear_widgets()
        for entry in log_entries:
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(28), spacing=dp(6))
            time_lbl = Label(
                text=entry.get("time", ""),
                size_hint_x=None,
                width=dp(95),
                font_size='13sp',
                color=[0.65, 0.75, 0.85, 1],
                halign='left',
                valign='middle'
            )
            time_lbl.bind(size=time_lbl.setter('text_size'))

            lvl = entry.get("level", "info")
            if lvl == "warning":
                badge_bg = [0.85, 0.55, 0.1, 1]
                badge_txt = "ALERTE"
                msg_color = [1.0, 0.85, 0.3, 1]
            elif lvl == "error":
                badge_bg = [0.85, 0.2, 0.2, 1]
                badge_txt = "ERREUR"
                msg_color = [1.0, 0.4, 0.4, 1]
            else:
                badge_bg = [0.2, 0.45, 0.7, 1]
                badge_txt = "INFO"
                msg_color = [0.9, 0.9, 0.9, 1]

            badge_btn = Button(
                text=badge_txt,
                size_hint_x=None,
                width=dp(65),
                font_size='11sp',
                background_color=badge_bg,
                background_normal=''
            )

            msg_lbl = Label(
                text=entry.get("msg", ""),
                font_size='13sp',
                color=msg_color,
                halign='left',
                valign='middle'
            )
            msg_lbl.bind(size=msg_lbl.setter('text_size'))

            row.add_widget(time_lbl)
            row.add_widget(badge_btn)
            row.add_widget(msg_lbl)
            container.add_widget(row)

    def refresh_explorer(self):
        if not hasattr(self.ids, 'explorer_container'):
            return
        container = self.ids.explorer_container
        container.clear_widgets()

        search = self.explorer_filter_search
        ftype = self.explorer_filter_type

        filtered = []
        for io in self._all_ios_cache:
            io_name = io.get("name", "").lower()
            io_dev = io.get("device", "").lower()
            io_type = io.get("type", "MEM").upper()

            if ftype != 'ALL' and io_type != ftype:
                continue
            if search and search not in io_name and search not in io_dev:
                continue
            filtered.append(io)

        for io in filtered:
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30), spacing=dp(6))
            dev_lbl = Label(text=str(io.get("device", "")), size_hint_x=0.25, font_size='14sp', halign='left', valign='middle')
            dev_lbl.bind(size=dev_lbl.setter('text_size'))

            name_lbl = Label(text=str(io.get("name", "")), size_hint_x=0.35, font_size='14sp', halign='left', valign='middle', color=[0.3, 0.8, 1, 1])
            name_lbl.bind(size=name_lbl.setter('text_size'))

            t = io.get("type", "MEM")
            type_bg = [0.2, 0.4, 0.6, 1] if t == "INP" else ([0.6, 0.4, 0.1, 1] if t == "OUT" else [0.3, 0.3, 0.3, 1])
            type_btn = Button(text=t, size_hint_x=None, width=dp(60), font_size='12sp', background_color=type_bg, background_normal='')

            val = str(io.get("value", ""))
            val_color = [0.3, 1, 0.3, 1] if val in ("1", "True") else ([0.7, 0.7, 0.7, 1] if val in ("0", "False") else [1, 1, 0.3, 1])
            val_lbl = Label(text=val, size_hint_x=0.25, font_size='15sp', halign='right', valign='middle', color=val_color)
            val_lbl.bind(size=val_lbl.setter('text_size'))

            row.add_widget(dev_lbl)
            row.add_widget(name_lbl)
            row.add_widget(type_btn)
            row.add_widget(val_lbl)
            container.add_widget(row)

# Load KV file
kv_file = os.path.join(os.path.dirname(__file__), 'system_info_widget.kv')
if os.path.exists(kv_file):
    Builder.load_file(kv_file)
