import asyncio
import logging
import os
import platform
import shutil
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pandas as pd
import psutil
import yaml

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

SEED_DIR = "seed"
CONFIG_PATH = "config.yaml"


class LogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        msg = self.format(record)
        self.callback(msg)


class ConfigManager:
    @staticmethod
    def load():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def save(config):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config, f, sort_keys=False)


class SystemInfo:
    @staticmethod
    def get_specs():
        return {
            "cpu_cores": psutil.cpu_count(logical=True),
            "cpu_physical": psutil.cpu_count(logical=False),
            "ram_gb": round(psutil.virtual_memory().total / (1024 ** 3), 1),
            "os": f"{platform.system()} {platform.release()}",
        }

    @staticmethod
    def recommend_settings(specs):
        cores = specs["cpu_cores"]
        ram = specs["ram_gb"]

        max_workers = min(cores, 10)
        if ram < 4:
            batch_size = 10
        elif ram < 8:
            batch_size = 15
        elif ram < 16:
            batch_size = 25
        else:
            batch_size = 25

        return {"batch_size": batch_size, "max_workers": max_workers}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto Servidores")
        self.geometry("1150x750")
        self.minsize(950, 650)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._running = False
        os.makedirs(SEED_DIR, exist_ok=True)

        self.specs = SystemInfo.get_specs()

        self._build_sidebar()
        self._build_main()
        self._setup_logging()
        self._refresh_seed_list()
        self._load_config_to_sliders()
        self._apply_recommended_settings()

    def _build_sidebar(self):
        side = ctk.CTkFrame(self, width=300, fg_color=("gray90", "gray20"))
        side.grid(row=0, column=0, sticky="nsew", padx=(15, 0), pady=15)
        side.grid_rowconfigure(4, weight=1)
        side.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(side, text="Archivos de Origen", font=ctk.CTkFont(size=16, weight="bold"))
        title.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        # System Info Card
        sys_frame = ctk.CTkFrame(side, fg_color=("gray80", "gray25"))
        sys_frame.grid(row=1, column=0, padx=10, pady=4, sticky="ew")
        sys_frame.grid_columnconfigure(0, weight=1)

        sys_title = ctk.CTkLabel(sys_frame, text="Info del Sistema", font=ctk.CTkFont(size=12, weight="bold"))
        sys_title.grid(row=0, column=0, padx=8, pady=(8, 2), sticky="w")

        self.lbl_cpu = ctk.CTkLabel(sys_frame, text=f"CPU: {self.specs['cpu_cores']} núcleos", font=ctk.CTkFont(size=11))
        self.lbl_cpu.grid(row=1, column=0, padx=8, sticky="w")

        self.lbl_ram = ctk.CTkLabel(sys_frame, text=f"RAM: {self.specs['ram_gb']} GB", font=ctk.CTkFont(size=11))
        self.lbl_ram.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="w")

        # Excel Format Hint
        fmt_frame = ctk.CTkFrame(side, fg_color=("gray80", "gray25"))
        fmt_frame.grid(row=2, column=0, padx=10, pady=4, sticky="ew")
        fmt_frame.grid_columnconfigure(0, weight=1)

        fmt_title = ctk.CTkLabel(fmt_frame, text="Formato Excel", font=ctk.CTkFont(size=12, weight="bold"))
        fmt_title.grid(row=0, column=0, padx=8, pady=(8, 2), sticky="w")

        # Mini spreadsheet visual
        tbl = ctk.CTkFrame(fmt_frame, fg_color=("gray70", "gray35"))
        tbl.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="w")
        tbl.grid_columnconfigure((0, 1), weight=1)

        hdr_a = ctk.CTkLabel(tbl, text=" A ", font=ctk.CTkFont(size=10, weight="bold"), fg_color=("gray60", "gray45"), text_color="white", width=110)
        hdr_a.grid(row=0, column=0, padx=(1, 0), pady=(1, 0), sticky="w")
        hdr_b = ctk.CTkLabel(tbl, text=" B ", font=ctk.CTkFont(size=10, weight="bold"), fg_color=("gray60", "gray45"), text_color="white", width=90)
        hdr_b.grid(row=0, column=1, padx=(0, 1), pady=(1, 0), sticky="w")

        ctk.CTkLabel(tbl, text="JUAN PEREZ GARCIA", font=ctk.CTkFont(size=10), fg_color=("gray90", "gray25"), width=110).grid(row=1, column=0, padx=(1, 0), pady=(0, 1), sticky="w")
        ctk.CTkLabel(tbl, text="BEGX123456X01", font=ctk.CTkFont(size=10), fg_color=("gray90", "gray25"), width=90).grid(row=1, column=1, padx=(0, 1), pady=(0, 1), sticky="w")
        ctk.CTkLabel(tbl, text="MARIA LOPEZ HDEZ", font=ctk.CTkFont(size=10), fg_color=("white", "gray20"), width=110).grid(row=2, column=0, padx=(1, 0), pady=(0, 1), sticky="w")
        ctk.CTkLabel(tbl, text="BEGX654321X02", font=ctk.CTkFont(size=10), fg_color=("white", "gray20"), width=90).grid(row=2, column=1, padx=(0, 1), pady=(0, 1), sticky="w")

        hint = ctk.CTkLabel(fmt_frame, text="Sin fila de encabezado. Primera fila = primera persona.", font=ctk.CTkFont(size=10), text_color=("gray30", "gray70"))
        hint.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="w")

        self.btn_add = ctk.CTkButton(side, text="Agregar Archivo", height=32, command=self._add_file)
        self.btn_add.grid(row=3, column=0, padx=10, pady=10, sticky="ew")

        self.seed_listbox = ctk.CTkScrollableFrame(side, fg_color="transparent")
        self.seed_listbox.grid(row=4, column=0, padx=10, pady=4, sticky="nsew")

        self.file_widgets = []

    def _build_main(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.tabview.grid_columnconfigure(0, weight=1)
        self.tabview.grid_rowconfigure(0, weight=1)

        self.tab_proc = self.tabview.add("Procesamiento")
        self.tab_settings = self.tabview.add("Configuración Avanzada")

        self._build_processing_tab()
        self._build_settings_tab()

    def _build_processing_tab(self):
        self.tab_proc.grid_columnconfigure(0, weight=1)
        self.tab_proc.grid_rowconfigure(3, weight=1)

        # --- Top Control Panel ---
        ctrl_frame = ctk.CTkFrame(self.tab_proc, fg_color=("gray90", "gray20"))
        ctrl_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctrl_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Batch Size Slider
        batch_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        batch_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(batch_frame, text="Tamaño de Lote", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.lbl_batch_val = ctk.CTkLabel(batch_frame, text="50", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_batch_val.pack(anchor="w")
        self.slider_batch = ctk.CTkSlider(batch_frame, from_=5, to=100, number_of_steps=19, command=self._on_batch_change)
        self.slider_batch.pack(fill="x", pady=(5, 0))
        self.slider_batch.set(25)

        # Max Workers Slider
        worker_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        worker_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(worker_frame, text="Trabajadores Máx.", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.lbl_worker_val = ctk.CTkLabel(worker_frame, text="100", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_worker_val.pack(anchor="w")
        self.slider_worker = ctk.CTkSlider(worker_frame, from_=1, to=20, number_of_steps=19, command=self._on_worker_change)
        self.slider_worker.pack(fill="x", pady=(5, 0))
        self.slider_worker.set(10)

        # Auto-config + Action Buttons
        action_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        action_frame.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")

        self.btn_auto = ctk.CTkButton(
            action_frame, text="Auto-Configurar", height=28,
            command=self._apply_recommended_settings,
            fg_color="gray40", hover_color="gray30"
        )
        self.btn_auto.pack(fill="x", pady=(0, 5))

        self.btn_start = ctk.CTkButton(
            action_frame, text="Iniciar Procesamiento", height=40,
            command=self._toggle_run, font=ctk.CTkFont(weight="bold")
        )
        self.btn_start.pack(fill="x")

        # --- Log Panel ---
        self.log_frame = ctk.CTkFrame(self.tab_proc)
        self.log_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(self.log_frame, wrap="word", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.log_text.configure(state="disabled")

        # --- Progress ---
        status_frame = ctk.CTkFrame(self.tab_proc, fg_color="transparent")
        status_frame.grid(row=2, column=0, sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(status_frame)
        self.progress.set(0)
        self.progress.grid(row=0, column=0, sticky="ew")

        self.status_label = ctk.CTkLabel(status_frame, text="Listo", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

    def _build_settings_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        config = ConfigManager.load()

        # API Section
        api_frame = ctk.CTkFrame(container)
        api_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(api_frame, text="Configuración API", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=5, anchor="w")

        self.ent_base_url = self._create_setting_row(api_frame, "URL Base:", config["api"]["base_url"])
        self.ent_coll_name = self._create_setting_row(api_frame, "ID de Colección:", str(config["api"]["default_coll_name"]))

        # Filters Section
        filt_frame = ctk.CTkFrame(container)
        filt_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(filt_frame, text="Configuración de Filtros", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=5, anchor="w")

        years_str = ",".join(map(str, config["filters"]["years_to_check"]))
        self.ent_years = self._create_setting_row(filt_frame, "Años (separados por coma):", years_str)

        # Rate Limit Section
        rl = config.get("rate_limit", {})
        rl_frame = ctk.CTkFrame(container)
        rl_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(rl_frame, text="Control de Rate Limit", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=5, anchor="w")

        # Max Concurrent
        self.lbl_rl_concurrent = ctk.CTkLabel(rl_frame, text="")
        self._build_slider_row(rl_frame, "Conexiones Máximas:", 1, 20, 19,
                               rl.get("max_concurrent", 10), self.lbl_rl_concurrent,
                               "_on_rl_concurrent_change")

        # Min Interval
        self.lbl_rl_interval = ctk.CTkLabel(rl_frame, text="")
        self._build_float_slider_row(rl_frame, "Intervalo Mínimo (seg):", 0.05, 1.0, 19,
                                     rl.get("min_interval", 0.15), self.lbl_rl_interval,
                                     "_on_rl_interval_change")

        # Cooldown Base
        self.lbl_rl_cooldown = ctk.CTkLabel(rl_frame, text="")
        self._build_float_slider_row(rl_frame, "Cooldown al obtener 429 (seg):", 1.0, 30.0, 29,
                                     rl.get("cooldown_base", 5.0), self.lbl_rl_cooldown,
                                     "_on_rl_cooldown_change")

        # Cooldown Max
        self.lbl_rl_cooldown_max = ctk.CTkLabel(rl_frame, text="")
        self._build_float_slider_row(rl_frame, "Cooldown Máximo (seg):", 5.0, 120.0, 23,
                                     rl.get("cooldown_max", 60.0), self.lbl_rl_cooldown_max,
                                     "_on_rl_cooldown_max_change")

        # Inter-batch Delay
        self.lbl_rl_batch_delay = ctk.CTkLabel(rl_frame, text="")
        self._build_float_slider_row(rl_frame, "Pausa Entre Lotes (seg):", 0.0, 10.0, 20,
                                     rl.get("inter_batch_delay", 1.5), self.lbl_rl_batch_delay,
                                     "_on_rl_batch_delay_change")

        # Retry Base Delay
        self.lbl_retry_delay = ctk.CTkLabel(rl_frame, text="")
        max_retries = config["api"].get("max_retries", 5)
        api_retry_base = config.get("api", {}).get("retry_base_delay", 2.0)
        self._build_float_slider_row(rl_frame, "Base de Espera al Reintentar (seg):", 0.5, 10.0, 19,
                                     api_retry_base, self.lbl_retry_delay,
                                     "_on_retry_delay_change")

        # Max Retries
        self.lbl_max_retries = ctk.CTkLabel(rl_frame, text="")
        self._build_slider_row(rl_frame, "Reintentos Máximos:", 1, 10, 9,
                               max_retries, self.lbl_max_retries,
                               "_on_max_retries_change")

        # Save Button
        self.btn_save_config = ctk.CTkButton(container, text="Guardar Configuración", command=self._save_config, fg_color="green", hover_color="darkgreen")
        self.btn_save_config.pack(pady=20)

    def _build_slider_row(self, parent, label, from_, to, steps, initial, val_label, callback_name):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row, text=label, anchor="w").pack(side="left")
        val_label.configure(text=str(int(initial)))
        val_label.pack(side="right", padx=(5, 0))
        slider = ctk.CTkSlider(row, from_=from_, to=to, number_of_steps=steps, command=lambda v, cb=callback_name: getattr(self, cb)(v))
        slider.pack(fill="x", padx=(0, 5))
        slider.set(int(initial))
        setattr(self, callback_name.replace("_on_", "slider_").replace("_change", ""), slider)

    def _build_float_slider_row(self, parent, label, from_, to, steps, initial, val_label, callback_name):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row, text=label, anchor="w").pack(side="left")
        val_label.configure(text=f"{initial:.2f}")
        val_label.pack(side="right", padx=(5, 0))
        slider = ctk.CTkSlider(row, from_=from_, to=to, number_of_steps=steps, command=lambda v, cb=callback_name: getattr(self, cb)(v))
        slider.pack(fill="x", padx=(0, 5))
        slider.set(initial)
        setattr(self, callback_name.replace("_on_", "slider_").replace("_change", ""), slider)

    def _on_rl_concurrent_change(self, value):
        self.lbl_rl_concurrent.configure(text=str(int(value)))

    def _on_rl_interval_change(self, value):
        self.lbl_rl_interval.configure(text=f"{value:.2f}")

    def _on_rl_cooldown_change(self, value):
        self.lbl_rl_cooldown.configure(text=f"{value:.1f}")

    def _on_rl_cooldown_max_change(self, value):
        self.lbl_rl_cooldown_max.configure(text=f"{value:.1f}")

    def _on_rl_batch_delay_change(self, value):
        self.lbl_rl_batch_delay.configure(text=f"{value:.1f}")

    def _on_retry_delay_change(self, value):
        self.lbl_retry_delay.configure(text=f"{value:.1f}")

    def _on_max_retries_change(self, value):
        self.lbl_max_retries.configure(text=str(int(value)))

    def _create_setting_row(self, parent, label, value):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row, text=label, width=150, anchor="w").pack(side="left")
        ent = ctk.CTkEntry(row)
        ent.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ent.insert(0, value)
        return ent

    def _on_batch_change(self, value):
        val = int(value)
        self.lbl_batch_val.configure(text=str(val))

    def _on_worker_change(self, value):
        val = int(value)
        self.lbl_worker_val.configure(text=str(val))

    def _apply_recommended_settings(self):
        rec = SystemInfo.recommend_settings(self.specs)
        batch = rec["batch_size"]
        workers = rec["max_workers"]

        self.slider_batch.set(batch)
        self.slider_worker.set(workers)
        self.lbl_batch_val.configure(text=str(batch))
        self.lbl_worker_val.configure(text=str(workers))

        self._append_log(f"Auto-configurado: batch_size={batch}, max_workers={workers} (basado en {self.specs['cpu_cores']} núcleos, {self.specs['ram_gb']} GB RAM) — Limitado por rate-limit del API")

    def _load_config_to_sliders(self):
        try:
            config = ConfigManager.load()
            batch = config["processing"]["batch_size"]
            workers = config["processing"]["max_workers"]
            self.slider_batch.set(batch)
            self.slider_worker.set(workers)
            self.lbl_batch_val.configure(text=str(batch))
            self.lbl_worker_val.configure(text=str(workers))

            rl = config.get("rate_limit", {})
            if hasattr(self, 'slider_rl_concurrent'):
                self.slider_rl_concurrent.set(rl.get("max_concurrent", 10))
                self.lbl_rl_concurrent.configure(text=str(rl.get("max_concurrent", 10)))
            if hasattr(self, 'slider_rl_interval'):
                self.slider_rl_interval.set(rl.get("min_interval", 0.15))
                self.lbl_rl_interval.configure(text=f"{rl.get('min_interval', 0.15):.2f}")
            if hasattr(self, 'slider_rl_cooldown'):
                self.slider_rl_cooldown.set(rl.get("cooldown_base", 5.0))
                self.lbl_rl_cooldown.configure(text=f"{rl.get('cooldown_base', 5.0):.1f}")
            if hasattr(self, 'slider_rl_cooldown_max'):
                self.slider_rl_cooldown_max.set(rl.get("cooldown_max", 60.0))
                self.lbl_rl_cooldown_max.configure(text=f"{rl.get('cooldown_max', 60.0):.0f}")
            if hasattr(self, 'slider_rl_batch_delay'):
                self.slider_rl_batch_delay.set(rl.get("inter_batch_delay", 1.5))
                self.lbl_rl_batch_delay.configure(text=f"{rl.get('inter_batch_delay', 1.5):.1f}")
            if hasattr(self, 'slider_retry_delay'):
                retry_base = config.get("api", {}).get("retry_base_delay", 2.0)
                self.slider_retry_delay.set(retry_base)
                self.lbl_retry_delay.configure(text=f"{retry_base:.1f}")
            if hasattr(self, 'slider_max_retries'):
                max_retries = config.get("api", {}).get("max_retries", 5)
                self.slider_max_retries.set(max_retries)
                self.lbl_max_retries.configure(text=str(max_retries))
        except Exception:
            pass

    def _save_config(self):
        try:
            config = ConfigManager.load()
            config["api"]["base_url"] = self.ent_base_url.get()
            config["api"]["default_coll_name"] = int(self.ent_coll_name.get())
            config["filters"]["years_to_check"] = [int(x.strip()) for x in self.ent_years.get().split(",") if x.strip()]

            config["processing"]["batch_size"] = int(self.slider_batch.get())
            config["processing"]["max_workers"] = int(self.slider_worker.get())

            config["api"]["max_retries"] = int(self.slider_max_retries.get())
            config["api"]["retry_base_delay"] = round(self.slider_retry_delay.get(), 1)

            rl = config.get("rate_limit", {})
            rl["max_concurrent"] = int(self.slider_rl_concurrent.get())
            rl["min_interval"] = round(self.slider_rl_interval.get(), 2)
            rl["cooldown_base"] = round(self.slider_rl_cooldown.get(), 1)
            rl["cooldown_max"] = round(self.slider_rl_cooldown_max.get(), 1)
            rl["inter_batch_delay"] = round(self.slider_rl_batch_delay.get(), 1)
            config["rate_limit"] = rl

            ConfigManager.save(config)
            messagebox.showinfo("Éxito", "¡Configuración guardada exitosamente!")
        except ValueError as e:
            messagebox.showerror("Error", f"Entrada inválida: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar configuración: {e}")

    def _setup_logging(self):
        handler = LogHandler(self._log_callback)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logging.root.addHandler(handler)
        logging.root.setLevel(logging.INFO)

    def _log_callback(self, msg):
        self.after(0, lambda: self._append_log(msg))

    def _append_log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _refresh_seed_list(self):
        for w in self.file_widgets:
            w.destroy()
        self.file_widgets = []

        files = sorted(f for f in os.listdir(SEED_DIR) if f.endswith(".xlsx"))

        if not files:
            empty = ctk.CTkLabel(
                self.seed_listbox, text="Aún no hay archivos de origen.\nAgrega archivos .xlsx para comenzar.",
                text_color=("gray40", "gray60"), font=ctk.CTkFont(size=12),
                justify="center"
            )
            empty.pack(pady=30)
            self.file_widgets.append(empty)
            return

        for fname in files:
            fpath = os.path.join(SEED_DIR, fname)
            try:
                df = pd.read_excel(fpath)
                rows = len(df)
            except Exception:
                rows = "?"

            row_frame = ctk.CTkFrame(self.seed_listbox, fg_color=("gray85", "gray25"))
            row_frame.pack(fill="x", padx=2, pady=2)
            row_frame.grid_columnconfigure(1, weight=1)

            icon = ctk.CTkLabel(row_frame, text="📄", font=ctk.CTkFont(size=14))
            icon.grid(row=0, column=0, padx=(8, 4), pady=4)

            display_name = fname if len(fname) <= 24 else fname[:21] + "..."
            info = ctk.CTkLabel(
                row_frame, text=display_name,
                font=ctk.CTkFont(size=12), justify="left", anchor="w"
            )
            info.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

            count = ctk.CTkLabel(
                row_frame, text=f"{rows} filas",
                font=ctk.CTkFont(size=11), text_color=("gray40", "gray60")
            )
            count.grid(row=0, column=2, padx=(4, 4), pady=4)

            btn_del = ctk.CTkButton(
                row_frame, text="X", width=28, height=24,
                fg_color="transparent", hover_color=("gray70", "gray30"),
                text_color=("gray40", "gray60"),
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda f=fname: self._remove_file(f)
            )
            btn_del.grid(row=0, column=3, padx=(0, 8), pady=4)

            self.file_widgets.extend([row_frame, icon, info, count, btn_del])

    def _add_file(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar archivos Excel",
            filetypes=[("Archivos Excel", "*.xlsx"), ("Todos los archivos", "*.*")]
        )
        if not paths:
            return

        copied = 0
        for p in paths:
            dest = os.path.join(SEED_DIR, os.path.basename(p))
            if os.path.exists(dest):
                base, ext = os.path.splitext(os.path.basename(p))
                i = 1
                while os.path.exists(dest):
                    dest = os.path.join(SEED_DIR, f"{base}_{i}{ext}")
                    i += 1
            shutil.copy2(p, dest)
            copied += 1

        self._refresh_seed_list()
        self._append_log(f"Agregado(s) {copied} archivo(s) a la carpeta de origen.")

    def _remove_file(self, filename):
        path = os.path.join(SEED_DIR, filename)
        if os.path.exists(path):
            os.remove(path)
            self._refresh_seed_list()
            self._append_log(f"Eliminado {filename}.")

    def _toggle_run(self):
        if self._running:
            return
        self._start_processing()

    def _start_processing(self):
        files = [f for f in os.listdir(SEED_DIR) if f.endswith(".xlsx")]
        if not files:
            messagebox.showwarning("Sin Archivos", "Por favor agrega algunos archivos .xlsx de origen antes de iniciar.")
            return

        # Sync slider values to config before running
        try:
            config = ConfigManager.load()
            config["processing"]["batch_size"] = int(self.slider_batch.get())
            config["processing"]["max_workers"] = int(self.slider_worker.get())
            config["api"]["max_retries"] = int(self.slider_max_retries.get())
            config["api"]["retry_base_delay"] = round(self.slider_retry_delay.get(), 1)
            rl = config.get("rate_limit", {})
            rl["max_concurrent"] = int(self.slider_rl_concurrent.get())
            rl["min_interval"] = round(self.slider_rl_interval.get(), 2)
            rl["cooldown_base"] = round(self.slider_rl_cooldown.get(), 1)
            rl["cooldown_max"] = round(self.slider_rl_cooldown_max.get(), 1)
            rl["inter_batch_delay"] = round(self.slider_rl_batch_delay.get(), 1)
            config["rate_limit"] = rl
            ConfigManager.save(config)
        except Exception as e:
            messagebox.showerror("Error", f"Error al sincronizar configuración: {e}")
            return

        self._running = True
        self.btn_start.configure(text="Ejecutando...", state="disabled")
        self.btn_auto.configure(state="disabled")
        self.slider_batch.configure(state="disabled")
        self.slider_worker.configure(state="disabled")
        self.btn_add.configure(state="disabled")
        self.progress.set(0)
        self.status_label.configure(text="Iniciando...")

        from orchestrator import Orchestrator
        try:
            orchestrator = Orchestrator()
            thread = threading.Thread(
                target=self._run_async,
                args=(orchestrator,),
                daemon=True
            )
            thread.start()
        except Exception as e:
            messagebox.showerror("Error Crítico", f"Error al inicializar el orquestador: {e}")
            self._on_complete()

    def _run_async(self, orchestrator):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                orchestrator.run(
                    on_progress=self._update_progress,
                    on_log=self._log_callback
                )
            )
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error Crítico", f"El procesamiento falló: {e}"))
        finally:
            loop.close()
            self.after(0, self._on_complete)

    def _update_progress(self, processed, total):
        def _do():
            if total > 0:
                self.progress.set(processed / total)
            self.status_label.configure(text=f"Procesados {processed} / {total}")
        self.after(0, _do)

    def _on_complete(self):
        self._running = False
        self.btn_start.configure(text="Iniciar Procesamiento", state="normal")
        self.btn_auto.configure(state="normal")
        self.slider_batch.configure(state="normal")
        self.slider_worker.configure(state="normal")
        self.btn_add.configure(state="normal")
        self.progress.set(1)
        self.status_label.configure(text="Listo")
        logging.info("Procesamiento completado.")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
