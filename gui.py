import asyncio
import logging
import os
import shutil
import threading
from tkinter import filedialog

import customtkinter as ctk
import pandas as pd

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

SEED_DIR = "seed"


class LogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        msg = self.format(record)
        self.callback(msg)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto Servidores")
        self.geometry("1050x650")
        self.minsize(800, 500)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._running = False
        self._total_rows = 0
        self._processed_rows = 0

        os.makedirs(SEED_DIR, exist_ok=True)

        self._build_sidebar()
        self._build_main()
        self._setup_logging()
        self._refresh_seed_list()

    def _build_sidebar(self):
        side = ctk.CTkFrame(self, width=280, fg_color=("gray90", "gray20"))
        side.grid(row=0, column=0, sticky="nsew", padx=(15, 0), pady=15)
        side.grid_rowconfigure(3, weight=1)
        side.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(side, text="Seed Files", font=ctk.CTkFont(size=16, weight="bold"))
        title.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        fmt_frame = ctk.CTkFrame(side, fg_color=("gray80", "gray25"))
        fmt_frame.grid(row=1, column=0, padx=10, pady=4, sticky="ew")
        fmt_frame.grid_columnconfigure(0, weight=1)

        fmt_title = ctk.CTkLabel(fmt_frame, text="Excel Format", font=ctk.CTkFont(size=12, weight="bold"))
        fmt_title.grid(row=0, column=0, padx=8, pady=(8, 2), sticky="w")

        fmt_hint = ctk.CTkLabel(
            fmt_frame,
            text="Col A: Nombres (name)\nCol B: RFC\nNo header row needed.\nFirst row = first person.",
            font=ctk.CTkFont(size=11),
            text_color=("gray30", "gray70"),
            justify="left",
        )
        fmt_hint.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="w")

        sample_btn = ctk.CTkButton(
            fmt_frame, text="Download Sample", width=120, height=24,
            font=ctk.CTkFont(size=11),
            command=self._download_sample
        )
        sample_btn.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="w")

        btn_row = ctk.CTkFrame(side, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=10, pady=4, sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)
        btn_row.grid_columnconfigure(1, weight=1)

        self.btn_add = ctk.CTkButton(btn_row, text="Add File", height=28, command=self._add_file)
        self.btn_add.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.btn_remove = ctk.CTkButton(btn_row, text="Remove", height=28, fg_color="gray40", hover_color="gray30", command=self._remove_file)
        self.btn_remove.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self.seed_listbox = ctk.CTkScrollableFrame(side, fg_color="transparent")
        self.seed_listbox.grid(row=3, column=0, padx=10, pady=4, sticky="nsew")

        self.file_widgets = []

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(header, text="Auto Servidores", font=ctk.CTkFont(size=20, weight="bold"))
        title.grid(row=0, column=0, sticky="w")

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.grid(row=0, column=0, sticky="e")

        self.btn_clear_checkpoint = ctk.CTkButton(
            btn_frame, text="Clear Checkpoint", width=130,
            command=self._clear_checkpoint, fg_color="gray40", hover_color="gray30"
        )
        self.btn_clear_checkpoint.pack(side="left", padx=(0, 8))

        self.btn_start = ctk.CTkButton(
            btn_frame, text="Start", width=100,
            command=self._toggle_run
        )
        self.btn_start.pack(side="left")

        self.log_frame = ctk.CTkFrame(main)
        self.log_frame.grid(row=1, column=0, sticky="nsew")
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(self.log_frame, wrap="word", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.log_text.configure(state="disabled")

        status_frame = ctk.CTkFrame(main, fg_color="transparent")
        status_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        status_frame.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(status_frame)
        self.progress.set(0)
        self.progress.grid(row=0, column=0, sticky="ew")

        self.status_label = ctk.CTkLabel(status_frame, text="Ready", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

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
                self.seed_listbox, text="No seed files yet.\nAdd .xlsx files to get started.",
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

            icon = ctk.CTkLabel(row_frame, text="📄", font=ctk.CTkFont(size=14))
            icon.pack(side="left", padx=(8, 4))

            info = ctk.CTkLabel(
                row_frame, text=f"{fname}",
                font=ctk.CTkFont(size=12), justify="left"
            )
            info.pack(side="left", fill="x", expand=True, padx=4)

            count = ctk.CTkLabel(
                row_frame, text=f"{rows} rows",
                font=ctk.CTkFont(size=11), text_color=("gray40", "gray60")
            )
            count.pack(side="right", padx=(4, 8))

            self.file_widgets.extend([row_frame, icon, info, count])

    def _add_file(self):
        paths = filedialog.askopenfilenames(
            title="Select Excel files",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
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
        self._append_log(f"Added {copied} file(s) to seed folder.")

    def _remove_file(self):
        files = sorted(f for f in os.listdir(SEED_DIR) if f.endswith(".xlsx"))
        if not files:
            return

        picker = ctk.CTkToplevel(self)
        picker.title("Remove File")
        picker.geometry("320x200")
        picker.transient(self)
        picker.grab_set()
        picker.resizable(False, False)

        picker.grid_columnconfigure(0, weight=1)
        picker.grid_rowconfigure(0, weight=1)

        label = ctk.CTkLabel(picker, text="Select file to remove:", font=ctk.CTkFont(size=13))
        label.pack(pady=(12, 4))

        var = ctk.StringVar(value=files[0])
        for f in files:
            rb = ctk.CTkRadioButton(picker, text=f, variable=var, value=f)
            rb.pack(anchor="w", padx=20, pady=2)

        def do_remove():
            target = var.get()
            path = os.path.join(SEED_DIR, target)
            if os.path.exists(path):
                os.remove(path)
                self._refresh_seed_list()
                self._append_log(f"Removed {target}.")
            picker.destroy()

        ctk.CTkButton(picker, text="Remove", command=do_remove, width=100).pack(pady=10)

    def _download_sample(self):
        dest = filedialog.asksaveasfilename(
            title="Save sample Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfilename="sample_seed.xlsx"
        )
        if not dest:
            return

        df = pd.DataFrame({
            "A": ["Juan Pérez García", "María López Hernández", "Carlos Ramírez Díaz"],
            "B": ["PEPJ850101HDF", "LOHM900202MDF", "RADC780303HDF"]
        })
        df.to_excel(dest, index=False, header=False)
        self._append_log(f"Sample saved to {dest}")

    def _clear_checkpoint(self):
        path = ".checkpoint/state.json"
        if os.path.exists(path):
            os.remove(path)
            self._append_log("Checkpoint cleared.")
        else:
            self._append_log("No checkpoint to clear.")

    def _toggle_run(self):
        if self._running:
            return
        self._start_processing()

    def _start_processing(self):
        files = [f for f in os.listdir(SEED_DIR) if f.endswith(".xlsx")]
        if not files:
            self._append_log("No seed files found. Add files first.")
            return

        self._running = True
        self._processed_rows = 0
        self._total_rows = 0
        self.btn_start.configure(text="Running...", state="disabled")
        self.btn_add.configure(state="disabled")
        self.btn_remove.configure(state="disabled")
        self.progress.set(0)
        self.status_label.configure(text="Starting...")

        from orchestrator import Orchestrator
        orchestrator = Orchestrator()

        for f in orchestrator.seed_index.get_files():
            self._total_rows += f["row_count"]

        thread = threading.Thread(target=self._run_async, args=(orchestrator,), daemon=True)
        thread.start()

    def _run_async(self, orchestrator):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_with_progress(orchestrator))
        finally:
            loop.close()
            self.after(0, self._on_complete)

    async def _run_with_progress(self, orchestrator):
        from session import create_session
        from worker import process_person

        session = await create_session(limit=orchestrator.config["processing"]["max_workers"])

        try:
            for file_info in orchestrator.seed_index.get_files():
                orchestrator.checkpoint.set_current_file(file_info["filename"])
                self._update_status(f"Processing: {file_info['filename']}")

                batch_size = orchestrator.config["processing"]["batch_size"]
                processed_count = 0

                for start in range(0, file_info["row_count"], batch_size):
                    batch = orchestrator.seed_index.load_batch(
                        file_info["filepath"], start=start, size=batch_size
                    )
                    tasks = []
                    for name, rfc in batch:
                        if orchestrator.checkpoint.is_processed(rfc):
                            self._processed_rows += 1
                            continue
                        tasks.append(
                            process_person(name, rfc, orchestrator.config, orchestrator.cache, session)
                        )

                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, Exception):
                            continue
                        orchestrator.checkpoint.mark_processed(result["RFC"], result)
                        processed_count += 1
                        self._processed_rows += 1

                    orchestrator.checkpoint.save()
                    orchestrator.cache.flush()
                    self._update_progress()

                found, not_found = orchestrator.checkpoint.get_results()
                summary = orchestrator.compactor.compact(found, not_found, file_info["basename"])
                logging.info(
                    f"Completed {file_info['filename']}: "
                    f"{summary['found_count']} found, {summary['not_found_count']} not found"
                )
        finally:
            await session.close()
            orchestrator.cache.close()

    def _update_progress(self):
        def _do():
            if self._total_rows > 0:
                self.progress.set(self._processed_rows / self._total_rows)
            self.status_label.configure(text=f"Processed {self._processed_rows} / {self._total_rows}")
        self.after(0, _do)

    def _update_status(self, text):
        self.after(0, lambda: self.status_label.configure(text=text))

    def _on_complete(self):
        self._running = False
        self.btn_start.configure(text="Start", state="normal")
        self.btn_add.configure(state="normal")
        self.btn_remove.configure(state="normal")
        self.progress.set(1)
        self.status_label.configure(text="Done")
        logging.info("All processing completed.")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
