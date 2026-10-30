import sys
import os
import re
import json
import time
import shutil
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import pystray
from PIL import Image, ImageDraw

DEFAULT_CONFIG = {
    "source_dir": "~/Downloads",
    "destination_dir": "~/Downloads",
    "organize_by_episode": False,
    "video_extensions": [".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"],
    "rules": [
        {
            "folder_name": "Altı Üstü İstanbul",
            "keywords": ["alti ustu istanbul", "aui"]
        },
        {
            "folder_name": "Taşacak Bu Deniz",
            "keywords": ["tasacak bu deniz", "tbd"]
        }
    ]
}


class SceneOrganizer:
    def __init__(self, config_path="config.json", log_callback=None):
        # Eğer program .exe olarak çalışıyorsa, config.json'u .exe'nin yanına kaydet
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent
            
        self.config_path = base_dir / config_path
        self.log_callback = log_callback
        self.load_config()
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        print(formatted)
        if self.log_callback:
            self.log_callback(formatted)

    def load_config(self):
        if not self.config_path.exists():
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=4)

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.source_dir = Path(os.path.expanduser(self.config.get("source_dir", "~/Downloads")))
        self.dest_dir = Path(os.path.expanduser(self.config.get("destination_dir", "~/Downloads")))
        self.extensions = tuple(ext.lower() for ext in self.config.get("video_extensions", [".mp4"]))
        self.organize_by_episode = self.config.get("organize_by_episode", False)
        self.rules = self.config.get("rules", [])

    def save_config(self):
        self.config["organize_by_episode"] = self.organize_by_episode
        self.config["rules"] = self.rules
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    @staticmethod
    def normalize_text(text: str) -> str:
        tr_map = str.maketrans("çğıöşüÇĞİIÖŞÜ_-.", "cgiosucgiiosu   ")
        cleaned = text.translate(tr_map).lower()
        return " ".join(cleaned.split())

    @staticmethod
    def extract_episode(filename: str):
        norm = SceneOrganizer.normalize_text(filename)
        patterns = [
            r"s\d+\s*e(\d+)",
            r"(\d+)\s*bolum",
            r"bolum\s*(\d+)",
            r"ep\s*(\d+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, norm)
            if match:
                return f"Bölüm {int(match.group(1))}"
        return None

    @staticmethod
    def is_file_ready(file_path: Path, wait_time: float = 1.0) -> bool:
        try:
            initial_size = file_path.stat().st_size
            if initial_size == 0:
                return False
            time.sleep(wait_time)
            return file_path.stat().st_size == initial_size
        except OSError:
            return False

    @staticmethod
    def get_unique_path(target_dir: Path, filename: str) -> Path:
        target_path = target_dir / filename
        if not target_path.exists():
            return target_path

        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1
        while True:
            new_path = target_dir / f"{stem} ({counter}){suffix}"
            if not new_path.exists():
                return new_path
            counter += 1

    def process_file(self, file_path: Path):
        if not file_path.exists() or not file_path.is_file():
            return
        if not file_path.name.lower().endswith(self.extensions):
            return

        normalized_name = self.normalize_text(file_path.stem)

        for rule in self.rules:
            folder_name = rule["folder_name"]
            for keyword in rule["keywords"]:
                norm_keyword = self.normalize_text(keyword)
                if norm_keyword and norm_keyword in normalized_name:
                    if not self.is_file_ready(file_path):
                        return

                    target_folder = self.dest_dir / folder_name
                    if self.organize_by_episode:
                        ep_folder = self.extract_episode(file_path.stem)
                        if ep_folder:
                            target_folder = target_folder / ep_folder

                    target_folder.mkdir(parents=True, exist_ok=True)
                    final_path = self.get_unique_path(target_folder, file_path.name)

                    try:
                        shutil.move(str(file_path), str(final_path))
                        self.log(f"TAŞINDI: {file_path.name} -> {folder_name}/")
                    except PermissionError:
                        self.log(f"BEKLİYOR (Kullanımda): {file_path.name}")
                    except Exception as e:
                        self.log(f"HATA: {file_path.name} ({e})")
                    return

    def scan_existing(self):
        self.log("İndirilenler klasörü taranıyor...")
        if self.source_dir.exists():
            for item in self.source_dir.iterdir():
                self.process_file(item)
        self.log("Tarama tamamlandı.")


class DownloadEventHandler(FileSystemEventHandler):
    def __init__(self, organizer: SceneOrganizer):
        self.organizer = organizer

    def on_created(self, event):
        if not event.is_directory:
            threading.Thread(target=self.organizer.process_file, args=(Path(event.src_path),), daemon=True).start()

    def on_moved(self, event):
        if not event.is_directory:
            threading.Thread(target=self.organizer.process_file, args=(Path(event.dest_path),), daemon=True).start()


class OrganizerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Scene Organizer - Dizi & Sahne Düzenleyici")
        self.root.geometry("680x520")
        self.root.minsize(620, 480)

        self.organizer = SceneOrganizer(log_callback=self.append_log)
        self.tray_icon = None

        self.setup_ui()
        self.refresh_rules_table()

        # Pencere kapatıldığında (X tuşu) tamamen kapatmak yerine sağ alt köşeye küçült
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        # Watchdog başlat
        self.observer = Observer()
        event_handler = DownloadEventHandler(self.organizer)
        self.observer.schedule(event_handler, str(self.organizer.source_dir), recursive=False)
        self.observer.start()

        # Sistem tepsisi ikonunu başlat
        self.start_tray_icon()

        # İlk açılışta mevcut dosyaları tara
        threading.Thread(target=self.organizer.scan_existing, daemon=True).start()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Üst Kısım: Yeni Dizi Ekleme
        add_frame = ttk.LabelFrame(main_frame, text=" Yeni Dizi Kuralı Ekle ", padding=10)
        add_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(add_frame, text="Klasör Adı (Örn: Eşref Rüya):").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        self.folder_entry = ttk.Entry(add_frame, width=25)
        self.folder_entry.grid(row=0, column=1, sticky=tk.EW, padx=4, pady=4)

        ttk.Label(add_frame, text="Aranacak Kelimeler (Virgülle ayır: esref ruya, er):").grid(row=1, column=0, sticky=tk.W, padx=4, pady=4)
        self.keywords_entry = ttk.Entry(add_frame, width=25)
        self.keywords_entry.grid(row=1, column=1, sticky=tk.EW, padx=4, pady=4)

        add_btn = ttk.Button(add_frame, text="Kaydet / Ekle", command=self.add_rule_ui)
        add_btn.grid(row=0, column=2, rowspan=2, padx=8, pady=4, sticky=tk.NS)
        add_frame.columnconfigure(1, weight=1)

        # Orta Kısım: Kayıtlı Diziler Tablosu
        list_frame = ttk.LabelFrame(main_frame, text=" Aktif Dizi Kuralları ", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ("folder", "keywords")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=6)
        self.tree.heading("folder", text="Açılacak Klasör Adı")
        self.tree.heading("keywords", text="Dosya Adında Aranan Kelimeler")
        self.tree.column("folder", width=200)
        self.tree.column("keywords", width=380)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Kontrol Butonları
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))

        self.ep_var = tk.BooleanVar(value=self.organizer.organize_by_episode)
        ep_check = ttk.Checkbutton(
            ctrl_frame,
            text="Bölüm numarasına göre alt klasör aç (Bölüm 1, Bölüm 2 vb.)",
            variable=self.ep_var,
            command=self.toggle_episode_option
        )
        ep_check.pack(side=tk.LEFT)

        del_btn = ttk.Button(ctrl_frame, text="Seçili Kuralı Sil", command=self.delete_selected_rule)
        del_btn.pack(side=tk.RIGHT, padx=4)

        scan_btn = ttk.Button(ctrl_frame, text="Şimdi Tara", command=lambda: threading.Thread(target=self.organizer.scan_existing, daemon=True).start())
        scan_btn.pack(side=tk.RIGHT, padx=4)

        open_btn = ttk.Button(ctrl_frame, text="İndirilenleri Aç", command=lambda: os.startfile(self.organizer.source_dir))
        open_btn.pack(side=tk.RIGHT, padx=4)

        # Alt Kısım: Canlı Log Ekranı
        log_frame = ttk.LabelFrame(main_frame, text=" Canlı Hareket Dökümü ", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=6, state=tk.DISABLED, bg="#1e1e1e", fg="#00ff88", font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def append_log(self, text: str):
        def _update():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, text + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.root.after(0, _update)

    def refresh_rules_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for rule in self.organizer.rules:
            self.tree.insert("", tk.END, values=(rule["folder_name"], ", ".join(rule["keywords"])))

    def add_rule_ui(self):
        folder = self.folder_entry.get().strip()
        raw_keywords = self.keywords_entry.get().strip()
        if not folder or not raw_keywords:
            messagebox.showwarning("Eksik Bilgi", "Lütfen hem klasör adını hem de aranacak kelimeleri girin.")
            return

        keywords = [k.strip().lower() for k in raw_keywords.split(",") if k.strip()]
        for rule in self.organizer.rules:
            if rule["folder_name"].lower() == folder.lower():
                for k in keywords:
                    if k not in rule["keywords"]:
                        rule["keywords"].append(k)
                break
        else:
            self.organizer.rules.append({"folder_name": folder, "keywords": keywords})

        self.organizer.save_config()
        self.refresh_rules_table()
        self.folder_entry.delete(0, tk.END)
        self.keywords_entry.delete(0, tk.END)
        self.organizer.log(f"Kural güncellendi: {folder}")
        threading.Thread(target=self.organizer.scan_existing, daemon=True).start()

    def delete_selected_rule(self):
        selected = self.tree.selection()
        if not selected:
            return
        folder_name = self.tree.item(selected[0])["values"][0]
        self.organizer.rules = [r for r in self.organizer.rules if r["folder_name"] != folder_name]
        self.organizer.save_config()
        self.refresh_rules_table()
        self.organizer.log(f"Kural silindi: {folder_name}")

    def toggle_episode_option(self):
        self.organizer.organize_by_episode = self.ep_var.get()
        self.organizer.save_config()

    @staticmethod
    def create_tray_image():
        img = Image.new("RGB", (64, 64), color=(30, 30, 46))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([8, 8, 56, 56], radius=12, fill=(0, 180, 120))
        draw.polygon([(24, 18), (24, 46), (46, 32)], fill=(255, 255, 255))
        return img

    def start_tray_icon(self):
        menu = pystray.Menu(
            pystray.MenuItem("Arayüzü Aç", self.show_window, default=True),
            pystray.MenuItem("Şimdi Tara", lambda: threading.Thread(target=self.organizer.scan_existing, daemon=True).start()),
            pystray.MenuItem("Çıkış", self.quit_app)
        )
        self.tray_icon = pystray.Icon("scene_organizer", self.create_tray_image(), "Scene Organizer (Aktif)", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_to_tray(self):
        self.root.withdraw()
        self.organizer.log("Arka planda çalışmaya devam ediyor (Sağ alt köşedeki ikondan açabilirsin).")

    def show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)

    def quit_app(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        self.observer.stop()
        self.root.after(0, self.root.destroy)


if __name__ == "__main__":
    root = tk.Tk()
    app = OrganizerApp(root)
    root.mainloop()