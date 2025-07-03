import os
import json
import wave
import subprocess
import threading
import tempfile
import shutil
import zipfile
from urllib.request import urlopen
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Canvas, scrolledtext
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from vosk import Model, KaldiRecognizer
from pydub import AudioSegment
import soundfile as sf
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import re
import time
import warnings
import unicodedata
import logging
from datetime import timedelta
from difflib import SequenceMatcher
from collections import defaultdict

# Configurar logging para Vosk
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("vosk")
logger.setLevel(logging.WARNING)

# ===================================================
# SOLUCIÓN PARA FFMPEG
# ===================================================
ffmpeg_path = r"C:\ffmpeg\bin\ffmpeg.exe"
if os.path.exists(ffmpeg_path):
    os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)
    AudioSegment.converter = ffmpeg_path
    AudioSegment.ffmpeg = ffmpeg_path
else:
    warnings.warn("FFmpeg no encontrado en la ruta especificada", RuntimeWarning)

# ===================================================
# CONFIGURACIÓN
# ===================================================
VOSK_MODELS = {
    "Español": {
        "small": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip",
            "name": "vosk-model-small-es-0.42"
        },
        "medium": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-es-0.42.zip",
            "name": "vosk-model-es-0.42"
        }
    },
    "Inglés (EEUU)": {
        "small": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
            "name": "vosk-model-small-en-us-0.15"
        },
        "medium": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip",
            "name": "vosk-model-en-us-0.22"
        },
        "large": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22-lgraph.zip",
            "name": "vosk-model-en-us-0.22-lgraph"
        }
    },
    "Francés": {
        "small": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip",
            "name": "vosk-model-small-fr-0.22"
        },
        "medium": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-fr-0.22.zip",
            "name": "vosk-model-fr-0.22"
        }
    },
    "Alemán": {
        "small": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip",
            "name": "vosk-model-small-de-0.15"
        },
        "medium": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-de-0.21.zip",
            "name": "vosk-model-de-0.21"
        }
    },
    "Italiano": {
        "small": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip",
            "name": "vosk-model-small-it-0.22"
        },
        "medium": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-it-0.22.zip",
            "name": "vosk-model-it-0.22"
        }
    },
    "Portugués": {
        "small": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip",
            "name": "vosk-model-small-pt-0.3"
        }
    },
    "Chino": {
        "small": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip",
            "name": "vosk-model-small-cn-0.22"
        }
    },
    "Ruso": {
        "small": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
            "name": "vosk-model-small-ru-0.22"
        },
        "medium": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-ru-0.22.zip",
            "name": "vosk-model-ru-0.22"
        }
    }
}

TEMP_AUDIO = "temp_audio.wav"
SUBTITLE_OUTPUT = "subtitulos.srt"
MODELS_DIR = "vosk_models"

def clean_text(text):
    """Normalizar texto y mantener caracteres especiales del español"""
    if not text:
        return ""
    
    text = unicodedata.normalize('NFC', text)
    
    # Reemplazar caracteres problemáticos específicos pero mantener letras especiales
    replacements = {
        'ÔÇ£': '"', 'ÔÇØ': '"', 'ÔÇÖ': "'", 'ÔÇª': '...', 
        'ÔÇô': '-', 'ÔÇó': '-', 'ÔÇò': "'", 'ÔÇ£': '"',
        'ÔÇó': '•', 'ÔÇ¬': '', 'ÔÇ¡': '!', 'ÔÇ¿': '?',
        '“': '"', '”': '"', '‘': "'", '’': "'", '…': '...',
        '–': '-', '—': '-', '«': '"', '»': '"'
    }
    
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    return text.strip()

def format_time(seconds):
    """Formatear segundos a tiempo SRT (HH:MM:SS,mmm)"""
    if seconds < 0:
        seconds = 0
    
    td = timedelta(seconds=seconds)
    total_seconds = td.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"

def parse_time(time_str):
    """Convertir tiempo SRT a segundos"""
    if not time_str:
        return 0.0
    
    parts = time_str.replace(',', ':').split(':')
    if len(parts) != 4:
        return 0.0
    
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        milliseconds = int(parts[3])
        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
    except:
        return 0.0

class SubtitleGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Generador Avanzado de Subtítulos con IA Local")
        self.root.geometry("1200x900")
        self.style = ttk.Style(theme="morph")
        
        self.audio_path = ""
        self.text_path = ""
        self.model = None
        self.processing = False
        self.cancel_requested = False
        self.subtitles = []
        self.audio_data = None
        self.sample_rate = None
        self.current_srt_file = ""
        self.audio_duration = 0
        
        self.setup_ui()
        self.check_models()
    
    def setup_ui(self):
        # Panel principal con pestañas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestaña 1: Procesamiento
        self.process_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.process_tab, text="Procesamiento")
        self.setup_process_tab()
        
        # Pestaña 2: Edición de Subtítulos
        self.edit_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.edit_tab, text="Edición")
        self.setup_edit_tab()
        
        # Pestaña 3: Previsualización
        self.preview_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.preview_tab, text="Previsualización")
        self.setup_preview_tab()
    
    def setup_process_tab(self):
        main_frame = ttk.Frame(self.process_tab, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Panel de entrada de audio
        audio_frame = ttk.LabelFrame(main_frame, text="Archivo de Audio/Video", padding=10)
        audio_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(audio_frame, text="Selecciona un archivo de audio o video:").grid(row=0, column=0, sticky="w", pady=5)
        self.audio_entry = ttk.Entry(audio_frame, width=80)
        self.audio_entry.grid(row=1, column=0, padx=5, sticky="we")
        
        btn_frame = ttk.Frame(audio_frame)
        btn_frame.grid(row=1, column=1, sticky="e")
        ttk.Button(btn_frame, text="Examinar", command=self.browse_audio, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="X", command=self.clear_audio, width=2, style="danger.TButton").pack(side=tk.LEFT, padx=2)
        
        # Panel de texto para subtítulos
        text_frame = ttk.LabelFrame(main_frame, text="Texto para Subtítulos", padding=10)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.text_mode = tk.StringVar(value="file")
        ttk.Radiobutton(
            text_frame, text="Cargar desde archivo", 
            variable=self.text_mode, value="file", 
            command=self.toggle_text_input
        ).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        ttk.Radiobutton(
            text_frame, text="Pegar texto directamente", 
            variable=self.text_mode, value="text", 
            command=self.toggle_text_input
        ).grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        # Entrada de archivo
        self.file_frame = ttk.Frame(text_frame)
        self.file_frame.grid(row=1, column=0, columnspan=2, sticky="we", pady=5)
        self.text_entry = ttk.Entry(self.file_frame, width=70)
        self.text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        file_btn_frame = ttk.Frame(self.file_frame)
        file_btn_frame.pack(side=tk.RIGHT)
        ttk.Button(file_btn_frame, text="Examinar", command=self.browse_text, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_btn_frame, text="X", command=self.clear_text, width=2, style="danger.TButton").pack(side=tk.LEFT, padx=2)
        
        # Área de texto directo
        self.text_area_frame = ttk.Frame(text_frame)
        self.text_area = scrolledtext.ScrolledText(
            self.text_area_frame, 
            height=15,
            wrap=tk.WORD,
            font=("Arial", 10)
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # Mostrar el modo de archivo por defecto
        self.toggle_text_input()
        
        # Configuración de procesamiento
        config_frame = ttk.LabelFrame(main_frame, text="Configuración", padding=10)
        config_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(config_frame, text="Idioma del Audio:").grid(row=0, column=0, padx=5, sticky="w")
        self.lang_combo = ttk.Combobox(config_frame, values=list(VOSK_MODELS.keys()), width=20)
        self.lang_combo.grid(row=0, column=1, padx=5, sticky="w")
        self.lang_combo.set("Español")
        self.lang_combo.bind("<<ComboboxSelected>>", self.update_model_types)
        
        ttk.Label(config_frame, text="Tamaño del Modelo:").grid(row=0, column=2, padx=(20,5), sticky="w")
        self.model_type_combo = ttk.Combobox(config_frame, width=15)
        self.model_type_combo.grid(row=0, column=3, padx=5, sticky="w")
        
        ttk.Label(config_frame, text="Modo de Operación:").grid(row=0, column=4, padx=(20,5), sticky="w")
        self.mode_combo = ttk.Combobox(config_frame, values=["Transcripción Automática", "Alineamiento Forzado"], width=20)
        self.mode_combo.grid(row=0, column=5, padx=5, sticky="w")
        self.mode_combo.set("Alineamiento Forzado")
        
        self.download_btn = ttk.Button(
            config_frame, 
            text="Descargar Modelo", 
            command=self.download_model,
            style="info.Outline.TButton",
            width=15
        )
        self.download_btn.grid(row=0, column=6, padx=10)
        
        # Actualizar tipos de modelo disponibles
        self.update_model_types()
        
        # Barra de progreso
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.progress_label = ttk.Label(progress_frame, text="Preparado para comenzar")
        self.progress_label.pack(anchor="w")
        
        self.progress_bar = ttk.Progressbar(
            progress_frame, 
            orient="horizontal", 
            mode="determinate",
            length=500
        )
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Botones de procesamiento
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        
        self.process_btn = ttk.Button(
            btn_frame, 
            text="Generar Subtítulos", 
            command=self.process_files,
            style="success.TButton",
            width=20
        )
        self.process_btn.pack(side=tk.LEFT, padx=10)
        
        self.cancel_btn = ttk.Button(
            btn_frame, 
            text="Cancelar", 
            command=self.cancel_processing,
            style="danger.TButton",
            width=15,
            state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=10)
        
        # Consola de salida
        console_frame = ttk.LabelFrame(main_frame, text="Registro de Progreso", padding=5)
        console_frame.pack(fill=tk.BOTH, expand=True)
        
        self.console = scrolledtext.ScrolledText(
            console_frame, 
            height=8,
            wrap=tk.WORD,
            bg="#2d2d2d", 
            fg="#e0e0e0",
            font=("Consolas", 9),
            state=tk.DISABLED
        )
        self.console.pack(fill=tk.BOTH, expand=True)
    
    def setup_edit_tab(self):
        main_frame = ttk.Frame(self.edit_tab, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Área de edición de texto SRT
        srt_frame = ttk.LabelFrame(main_frame, text="Editor de Subtítulos", padding=10)
        srt_frame.pack(fill=tk.BOTH, expand=True)
        
        self.srt_text = scrolledtext.ScrolledText(
            srt_frame, 
            height=25,
            wrap=tk.WORD,
            font=("Courier New", 10)
        )
        self.srt_text.pack(fill=tk.BOTH, expand=True)
        self.srt_text.bind("<KeyRelease>", self.srt_text_modified)
        
        # Botones de control
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(
            btn_frame, 
            text="Cargar SRT", 
            command=self.load_srt,
            style="info.TButton",
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame, 
            text="Guardar SRT", 
            command=self.save_srt,
            style="success.TButton",
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame, 
            text="Aplicar Cambios", 
            command=self.apply_srt_changes,
            style="primary.TButton",
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        # Información
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(info_frame, text="Puedes editar los subtítulos directamente en este editor.").pack(side=tk.LEFT)
        ttk.Label(info_frame, text="Formato: [Número]\n[HH:MM:SS,mmm --> HH:MM:SS,mmm]\n[Texto]").pack(side=tk.RIGHT)
    
    def setup_preview_tab(self):
        main_frame = ttk.Frame(self.preview_tab, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Previsualización de alineación
        preview_frame = ttk.LabelFrame(main_frame, text="Previsualización de Alineación", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        self.preview_canvas = Canvas(preview_frame, bg="#2d2d2d", highlightthickness=0)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Estado inicial de previsualización
        self.preview_text = self.preview_canvas.create_text(
            self.preview_canvas.winfo_width()/2, 
            self.preview_canvas.winfo_height()/2,
            text="La previsualización se mostrará aquí después del procesamiento",
            fill="#aaaaaa",
            font=("Helvetica", 12),
            anchor=tk.CENTER
        )
        
        # Controles de previsualización
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(
            control_frame, 
            text="Actualizar Previsualización", 
            command=self.update_preview,
            style="info.Outline.TButton"
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            control_frame, 
            text="Exportar SRT", 
            command=self.export_srt,
            style="success.TButton"
        ).pack(side=tk.RIGHT, padx=5)
    
    def toggle_text_input(self):
        if self.text_mode.get() == "file":
            self.file_frame.grid()
            self.text_area_frame.grid_forget()
        else:
            self.file_frame.grid_forget()
            self.text_area_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=5)
            text_frame = self.text_area_frame.master
            text_frame.rowconfigure(2, weight=1)
            text_frame.columnconfigure(0, weight=1)
    
    def update_model_types(self, event=None):
        lang = self.lang_combo.get()
        if lang and lang in VOSK_MODELS:
            model_types = list(VOSK_MODELS[lang].keys())
            self.model_type_combo.config(values=model_types)
            self.model_type_combo.set(model_types[0] if model_types else "")
    
    def check_models(self):
        if not os.path.exists(MODELS_DIR):
            os.makedirs(MODELS_DIR)
            self.log("Carpeta de modelos creada. Por favor descargue los modelos.")
    
    def log(self, message):
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)
    
    def update_progress(self, value, message=None):
        """Actualizar la barra de progreso y la etiqueta de estado"""
        if message:
            self.progress_label.config(text=message)
        self.progress_bar["value"] = value
        self.root.update_idletasks()
    
    def clear_audio(self):
        self.audio_path = ""
        self.audio_entry.delete(0, tk.END)
    
    def clear_text(self):
        self.text_path = ""
        self.text_entry.delete(0, tk.END)
    
    def browse_audio(self):
        filetypes = (
            ("Archivos multimedia", "*.mp3 *.wav *.ogg *.flac *.mp4 *.avi *.mkv"),
            ("Todos los archivos", "*.*")
        )
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self.audio_path = path
            self.audio_entry.delete(0, tk.END)
            self.audio_entry.insert(0, path)
    
    def browse_text(self):
        filetypes = (
            ("Archivos de texto", "*.txt"),
            ("Todos los archivos", "*.*")
        )
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self.text_path = path
            self.text_entry.delete(0, tk.END)
            self.text_entry.insert(0, path)
    
    def download_model(self):
        lang = self.lang_combo.get()
        model_type = self.model_type_combo.get()
        
        if not lang or not model_type:
            messagebox.showerror("Error", "Selecciona un idioma y un tamaño de modelo")
            return
        
        try:
            model_info = VOSK_MODELS[lang][model_type]
        except KeyError:
            self.log(f"No se encontró modelo {model_type} para {lang}")
            return
        
        model_url = model_info["url"]
        model_name = model_info["name"]
        model_path = os.path.join(MODELS_DIR, model_name)
        
        if os.path.exists(model_path):
            self.log(f"Modelo {model_name} ya está instalado.")
            return
        
        # Crear ventana de progreso
        download_window = tk.Toplevel(self.root)
        download_window.title(f"Descargando modelo {model_type} para {lang}")
        download_window.geometry("500x150")
        download_window.resizable(False, False)
        
        ttk.Label(
            download_window, 
            text=f"Descargando modelo {model_type} para {lang}...", 
            font=("Helvetica", 11)
        ).pack(pady=10)
        
        progress = ttk.Progressbar(
            download_window, 
            orient="horizontal", 
            length=400, 
            mode="determinate"
        )
        progress.pack(pady=10)
        
        status = ttk.Label(download_window, text="")
        status.pack(pady=5)
        
        # Función para descargar en segundo plano
        def download():
            try:
                os.makedirs(MODELS_DIR, exist_ok=True)
                
                # Descargar archivo ZIP
                response = urlopen(model_url)
                total_size = int(response.headers.get('Content-Length', 0))
                block_size = 1024 * 1024  # 1 MB
                downloaded = 0
                
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                while not self.cancel_requested:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    
                    downloaded += len(buffer)
                    temp_file.write(buffer)
                    progress_value = (downloaded / total_size) * 100
                    progress['value'] = progress_value
                    status.config(text=f"{downloaded/1024/1024:.2f} MB de {total_size/1024/1024:.2f} MB")
                    download_window.update()
                
                temp_file.close()
                
                if self.cancel_requested:
                    os.unlink(temp_file.name)
                    self.log("Descarga cancelada")
                    download_window.destroy()
                    return
                
                # Extraer archivo ZIP
                status.config(text="Extrayendo modelo...")
                progress['value'] = 0
                download_window.update()
                
                with zipfile.ZipFile(temp_file.name, 'r') as zip_ref:
                    zip_ref.extractall(MODELS_DIR)
                
                # Mover a la carpeta correcta
                extracted_dir = os.path.join(MODELS_DIR, model_name)
                if not os.path.exists(extracted_dir):
                    # Intentar renombrar si es necesario
                    for dirname in os.listdir(MODELS_DIR):
                        if dirname.startswith("vosk-model"):
                            shutil.move(os.path.join(MODELS_DIR, dirname), extracted_dir)
                
                self.log(f"Modelo {model_name} descargado y extraído.")
                messagebox.showinfo("Éxito", f"Modelo para {lang} ({model_type}) instalado correctamente.")
            
            except Exception as e:
                self.log(f"Error al descargar modelo: {str(e)}")
                messagebox.showerror("Error", f"No se pudo descargar el modelo:\n{str(e)}")
            finally:
                download_window.destroy()
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
        
        threading.Thread(target=download, daemon=True).start()
    
    def cancel_processing(self):
        self.cancel_requested = True
        self.log("Cancelando proceso...")
        self.update_progress(0, "Proceso cancelado por el usuario")
    
    def get_text_content(self):
        """Obtener el contenido de texto según el modo seleccionado"""
        if self.text_mode.get() == "file":
            if not self.text_path:
                return ""
            try:
                with open(self.text_path, "r", encoding="utf-8") as f:
                    return clean_text(f.read())
            except:
                return ""
        else:
            return clean_text(self.text_area.get("1.0", tk.END))
    
    def process_files(self):
        if not self.audio_path:
            messagebox.showerror("Error", "Selecciona un archivo de audio/video")
            return
        
        # Obtener configuración
        language = self.lang_combo.get()
        model_type = self.model_type_combo.get()
        mode = self.mode_combo.get()
        
        if not language or not model_type:
            messagebox.showerror("Error", "Selecciona un idioma y tamaño de modelo")
            return
        
        # Verificar modo de alineamiento forzado
        if mode == "Alineamiento Forzado":
            text_content = self.get_text_content()
            if not text_content:
                messagebox.showerror("Error", "Proporciona texto para alineamiento forzado")
                return
        
        # Verificar modelo
        try:
            model_info = VOSK_MODELS[language][model_type]
        except KeyError:
            self.log(f"No se encontró modelo {model_type} para {language}")
            return
        
        model_path = os.path.join(MODELS_DIR, model_info["name"])
        if not os.path.exists(model_path):
            self.log(f"Modelo no encontrado: {model_path}")
            self.log("Por favor, descargue el modelo primero.")
            return
        
        # Preparar interfaz
        self.process_btn.config(state=tk.DISABLED)
        self.download_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.cancel_requested = False
        self.log("Iniciando procesamiento...")
        self.update_progress(0, "Preparando...")
        
        # Limpiar previsualización
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            self.preview_canvas.winfo_width()/2, 
            self.preview_canvas.winfo_height()/2,
            text="Procesando...",
            fill="#aaaaaa",
            font=("Helvetica", 12),
            anchor=tk.CENTER
        )
        
        # Ejecutar en hilo separado
        threading.Thread(
            target=self.generate_subtitles, 
            args=(language, model_type, mode, text_content if mode == "Alineamiento Forzado" else None),
            daemon=True
        ).start()
    
    def convert_to_wav(self):
        try:
            self.update_progress(0, "Convirtiendo audio a formato compatible...")
            self.log("Convirtiendo audio a formato compatible...")
            audio = AudioSegment.from_file(self.audio_path)
            audio = audio.set_frame_rate(16000).set_channels(1)
            audio.export(TEMP_AUDIO, format="wav")
            
            # Calcular duración del audio
            self.audio_duration = len(audio) / 1000.0  # en segundos
            self.log(f"Duración del audio: {self.audio_duration:.2f} segundos")
            
            # Leer datos para previsualización
            self.audio_data, self.sample_rate = sf.read(TEMP_AUDIO)
            return True
        except Exception as e:
            self.log(f"Error en conversión de audio: {str(e)}")
            return False
    
    def generate_subtitles(self, language, model_type, mode, text_content=None):
        try:
            # Paso 1: Convertir audio
            if not self.convert_to_wav():
                return
            
            # Paso 2: Cargar modelo
            model_info = VOSK_MODELS[language][model_type]
            model_path = os.path.join(MODELS_DIR, model_info["name"])
            self.log(f"Cargando modelo: {model_path}...")
            self.update_progress(5, f"Cargando modelo {model_type}...")
            model = Model(model_path)
            
            # Paso 3: Procesar según el modo
            if mode == "Transcripción Automática":
                self.log("Iniciando transcripción automática...")
                self.update_progress(10, "Transcribiendo audio...")
                self.subtitles = self.transcribe_audio(model)
            else:
                self.log("Iniciando alineamiento forzado...")
                self.update_progress(10, "Alineando texto con audio...")
                self.subtitles = self.forced_alignment(model, text_content)
            
            # Paso 4: Generar SRT
            if self.subtitles:
                self.current_srt_file = SUBTITLE_OUTPUT
                self.write_srt(self.current_srt_file, self.subtitles)
                self.log(f"Archivo SRT generado: {self.current_srt_file}")
                self.update_progress(95, "Generando archivo SRT...")
                
                # Cargar SRT en el editor
                self.load_srt_into_editor()
                self.update_progress(100, "Proceso completado con éxito")
                
                # Actualizar previsualización
                self.update_preview()
                
                # Cambiar a la pestaña de edición
                self.notebook.select(self.edit_tab)
            
        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.update_progress(0, f"Error: {str(e)}")
        finally:
            # Limpiar
            if os.path.exists(TEMP_AUDIO):
                os.remove(TEMP_AUDIO)
            self.process_btn.config(state=tk.NORMAL)
            self.download_btn.config(state=tk.NORMAL)
            self.cancel_btn.config(state=tk.DISABLED)
    
    def transcribe_audio(self, model):
        try:
            wf = wave.open(TEMP_AUDIO, "rb")
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                self.log("Formato de audio no compatible: debe ser WAV mono 16-bit")
                return []
                
            rec = KaldiRecognizer(model, wf.getframerate())
            rec.SetWords(True)
            
            results = []
            total_frames = wf.getnframes()
            frames_processed = 0
            chunk_size = 4000
            
            self.log("Transcribiendo audio...")
            
            while not self.cancel_requested:
                data = wf.readframes(chunk_size)
                if len(data) == 0:
                    break
                
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if 'result' in result:
                        results.extend(result['result'])
                
                frames_processed += chunk_size
                progress = 10 + min(85, (frames_processed / total_frames) * 85)
                self.update_progress(progress, f"Transcribiendo... {progress:.1f}%")
                self.log(f"Progreso: {progress:.1f}%")
            
            if self.cancel_requested:
                return []
            
            # Obtener resultado final
            final_result = json.loads(rec.FinalResult())
            if 'result' in final_result:
                results.extend(final_result['result'])
            
            # Agrupar palabras en frases
            return self.group_words_into_phrases(results)
        except Exception as e:
            self.log(f"Error en transcripción: {str(e)}")
            return []

    def forced_alignment(self, model, text_content):
        """Versión mejorada con validación de tiempos"""
        try:
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            if not lines:
                return []
                
            words = self.transcribe_individual_words(model)
            if not words:
                return []
                
            word_list = [w['word'].lower() for w in words]
            word_times = [(w['start'], w['end']) for w in words]
            
            subtitles = []
            current_word_idx = 0
            total_words = len(words)
            
            for line in lines:
                if self.cancel_requested or current_word_idx >= total_words:
                    break
                    
                line_lower = line.lower()
                line_words = re.findall(r"\w+", line_lower)
                
                matched_indices = []
                for word in line_words:
                    found = False
                    for i in range(current_word_idx, min(current_word_idx + 20, total_words)):
                        if word_list[i].startswith(word[:3]):
                            matched_indices.append(i)
                            current_word_idx = i + 1
                            found = True
                            break
                    if not found:
                        break
                        
                if matched_indices:
                    start_time = words[matched_indices[0]]['start']
                    end_time = words[matched_indices[-1]]['end']
                    
                    # Validación y ajuste de duración
                    min_duration = max(1.5, len(line_words) * 0.3)
                    max_duration = min(10.0, len(line_words) * 1.5)
                    actual_duration = end_time - start_time
                    
                    if actual_duration < min_duration:
                        end_time = start_time + min_duration
                    elif actual_duration > max_duration:
                        end_time = start_time + max_duration
                    
                    # Validar superposición con subtítulo anterior
                    if subtitles and start_time < subtitles[-1]['end']:
                        start_time = subtitles[-1]['end'] + 0.1
                        end_time = max(end_time, start_time + min_duration)
                    
                    subtitles.append({
                        'start': start_time,
                        'end': end_time,
                        'text': line
                    })
                else:
                    estimated_duration = max(1.0, min(5.0, len(line.split()) * 0.8))
                    if subtitles:
                        start_time = subtitles[-1]['end'] + 0.3
                    else:
                        start_time = 0.0
                    
                    subtitles.append({
                        'start': start_time,
                        'end': start_time + estimated_duration,
                        'text': line
                    })
            
            # Validación final de toda la secuencia
            return self.validate_subtitle_sequence(subtitles)
        except Exception as e:
            self.log(f"Error en alineamiento: {str(e)}")
            return []

    def validate_subtitle_sequence(self, subtitles):
        """Valida y ajusta la secuencia completa de subtítulos"""
        if not subtitles:
            return []
        
        # 1. Ordenar por tiempo de inicio
        subtitles.sort(key=lambda x: x['start'])
        
        # 2. Ajustar superposiciones y pausas
        for i in range(1, len(subtitles)):
            prev = subtitles[i-1]
            curr = subtitles[i]
            
            # Asegurar que el subtítulo actual comience después del anterior
            if curr['start'] < prev['end']:
                overlap = prev['end'] - curr['start']
                # Distribuir el overlap
                prev['end'] -= overlap / 2
                curr['start'] += overlap / 2
                
                # Asegurar duración mínima después del ajuste
                if prev['end'] - prev['start'] < 0.3:
                    prev['end'] = prev['start'] + 0.3
                if curr['end'] - curr['start'] < 0.3:
                    curr['end'] = curr['start'] + 0.3
            
            # Asegurar pausa mínima entre subtítulos
            pause = curr['start'] - prev['end']
            min_pause = 0.1  # 100ms
            if pause < min_pause:
                adjustment = (min_pause - pause) / 2
                prev['end'] -= adjustment
                curr['start'] += adjustment
                
                # Verificar que no hayamos creado duraciones negativas
                if prev['end'] < prev['start']:
                    prev['end'] = prev['start'] + 0.1
                if curr['end'] < curr['start']:
                    curr['end'] = curr['start'] + 0.1
        
        # 3. Eliminar subtítulos con duración cero o negativa
        subtitles = [sub for sub in subtitles if sub['end'] - sub['start'] > 0.01]
        
        # 4. Renumerar secuencialmente
        for i, sub in enumerate(subtitles, 1):
            sub['index'] = i
        
        return subtitles

    def validate_srt(content):
        """Valida que el contenido cumpla con el formato SRT estándar"""
        errors = []
        lines = content.split('\n')
        i = 0
        subtitle_count = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Esperado: número de subtítulo
            if not line.isdigit():
                i += 1
                continue
                
            subtitle_count += 1
            subtitle_num = int(line)
            if subtitle_num != subtitle_count:
                errors.append(f"Error en subtítulo {subtitle_num}: Numeración incorrecta (esperado {subtitle_count})")
            
            i += 1
            if i >= len(lines):
                errors.append(f"Subtítulo {subtitle_num}: Incompleto (falta línea de tiempo)")
                break
                
            # Línea de tiempo
            time_line = lines[i].strip()
            if '-->' not in time_line:
                errors.append(f"Subtítulo {subtitle_num}: Formato de tiempo inválido")
                i += 1
                continue
                
            times = time_line.split('-->')
            if len(times) != 2:
                errors.append(f"Subtítulo {subtitle_num}: Formato de tiempo inválido")
                i += 1
                continue
                
            start_time = parse_time(times[0].strip())
            end_time = parse_time(times[1].strip())
            
            if start_time >= end_time:
                errors.append(f"Subtítulo {subtitle_num}: Tiempo de inicio ({times[0]}) mayor o igual que tiempo final ({times[1]})")
            
            if end_time - start_time > 10.0:  # Duración máxima de 10 segundos
                errors.append(f"Subtítulo {subtitle_num}: Duración demasiado larga ({(end_time-start_time):.1f}s)")
            elif end_time - start_time < 0.5:  # Duración mínima de 0.5 segundos
                errors.append(f"Subtítulo {subtitle_num}: Duración demasiado corta ({(end_time-start_time):.1f}s)")
            
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
                
            if not text_lines:
                errors.append(f"Subtítulo {subtitle_num}: Falta texto")
                
            # Verificar línea vacía entre subtítulos
            if i < len(lines) and lines[i].strip():
                errors.append(f"Subtítulo {subtitle_num}: Falta línea vacía después del texto")
                
            i += 1
        
        return errors

    def musical_alignment(self, words, lines):
        """Algoritmo especializado para alineamiento musical"""
        subtitles = []
        word_idx = 0
        total_words = len(words)
        
        for line in lines:
            if self.cancel_requested or word_idx >= total_words:
                break
            
            line_words = line.lower().split()
            matched = []
            start_time = words[word_idx]['start']
            
            # Buscar secuencia de palabras coincidentes
            for word in line_words:
                while word_idx < total_words:
                    if words[word_idx]['word'].lower().startswith(word[:3]):
                        matched.append(words[word_idx])
                        word_idx += 1
                        break
                    word_idx += 1
            
            if matched:
                end_time = matched[-1]['end']
                # Extender duración para frases cortas
                min_duration = max(1.5, len(line.split()) * 0.3)
                if (end_time - start_time) < min_duration:
                    end_time = start_time + min_duration
                
                subtitles.append({
                    'start': start_time,
                    'end': end_time,
                    'text': line
                })
        
        return subtitles

    def fine_tune_alignment(self, subtitles):
        """Ajuste fino basado en características musicales"""
        if not subtitles:
            return subtitles
        
        # 1. Asegurar progresión temporal
        subtitles.sort(key=lambda x: x['start'])
        
        # 2. Ajustar superposiciones
        for i in range(1, len(subtitles)):
            prev = subtitles[i-1]
            curr = subtitles[i]
            
            if curr['start'] < prev['end']:
                overlap = prev['end'] - curr['start']
                # Distribuir el overlap
                prev['end'] -= overlap / 2
                curr['start'] += overlap / 2
        
        # 3. Ajustar pausas entre versos
        for i in range(1, len(subtitles)):
            prev = subtitles[i-1]
            curr = subtitles[i]
            
            pause = curr['start'] - prev['end']
            ideal_pause = 0.3  # 300ms entre versos
            
            if pause < ideal_pause:
                # Ajustar tiempos para crear pausa natural
                adjustment = (ideal_pause - pause) / 2
                prev['end'] -= adjustment
                curr['start'] += adjustment
        
        return subtitles

    def transcribe_individual_words(self, model):
        """Transcribe audio y devuelve palabras individuales con timestamps"""
        try:
            wf = wave.open(TEMP_AUDIO, "rb")
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                self.log("Formato de audio no compatible: debe ser WAV mono 16-bit")
                return []
                
            rec = KaldiRecognizer(model, wf.getframerate())
            rec.SetWords(True)
            
            results = []
            total_frames = wf.getnframes()
            frames_processed = 0
            chunk_size = 4000
            
            while not self.cancel_requested:
                data = wf.readframes(chunk_size)
                if len(data) == 0:
                    break
                
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if 'result' in result:
                        results.extend(result['result'])
                
                frames_processed += chunk_size
                progress = min(95, (frames_processed / total_frames) * 95)
                self.update_progress(progress, f"Transcribiendo... {progress:.1f}%")
            
            if self.cancel_requested:
                return []
            
            # Obtener resultado final
            final_result = json.loads(rec.FinalResult())
            if 'result' in final_result:
                results.extend(final_result['result'])
            
            return results
        except Exception as e:
            self.log(f"Error en transcripción: {str(e)}")
            return []

    def group_words_into_phrases(self, words, max_chars=40, max_duration=5.0):
        if not words:
            return []
            
        subtitles = []
        current_phrase = []
        start_time = words[0]['start']
        end_time = words[0]['end']
        
        for i, word_info in enumerate(words):
            if self.cancel_requested:
                return []
            
            word = word_info['word']
            start = word_info['start']
            end = word_info['end']
            
            current_phrase.append(word)
            end_time = end
            
            # Condiciones para finalizar frase
            if (len(" ".join(current_phrase))) > max_chars or \
               (end_time - start_time) > max_duration or \
               word in ['.', '?', '!', ';'] or \
               i == len(words) - 1:
                
                phrase_text = " ".join(current_phrase)
                subtitles.append({
                    'start': start_time,
                    'end': end_time,
                    'text': phrase_text
                })
                
                # Resetear para la siguiente frase
                current_phrase = []
                if i < len(words) - 1:
                    start_time = words[i+1]['start']
        
        return subtitles
    
    def write_srt(self, file_path, subtitles):
        """Escribe archivo SRT con validación mejorada"""
        try:
            content = ""
            prev_end = 0.0
            
            for i, sub in enumerate(subtitles, 1):
                # Validar tiempos
                if sub['start'] >= sub['end']:
                    self.log(f"Advertencia: Subtítulo {i} tiene tiempo de inicio mayor o igual que fin. Ajustando...")
                    sub['end'] = sub['start'] + 1.0  # Asignar duración mínima
                    
                # Validar superposición con subtítulo anterior
                if sub['start'] < prev_end:
                    self.log(f"Advertencia: Subtítulo {i} se superpone con el anterior. Ajustando...")
                    sub['start'] = prev_end + 0.1  # Pequeña pausa
                    if sub['end'] <= sub['start']:
                        sub['end'] = sub['start'] + 1.0
                        
                # Validar duración
                duration = sub['end'] - sub['start']
                if duration > 10.0:  # Duración máxima
                    self.log(f"Advertencia: Subtítulo {i} demasiado largo ({duration:.1f}s). Dividiendo...")
                    sub['end'] = sub['start'] + 10.0
                elif duration < 0.5:  # Duración mínima
                    self.log(f"Advertencia: Subtítulo {i} demasiado corto ({duration:.1f}s). Extendiendo...")
                    sub['end'] = sub['start'] + 0.5
                    
                start = format_time(sub['start'])
                end = format_time(sub['end'])
                content += f"{i}\n{start} --> {end}\n{sub['text']}\n\n"
                prev_end = sub['end']
            
            # Validar contenido completo antes de escribir
            errors = self.validate_srt(content)
            if errors:
                self.log("Advertencias de validación SRT:")
                for error in errors:
                    self.log(f" - {error}")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            self.log(f"Error al escribir SRT: {str(e)}")
            return False

    def load_srt_into_editor(self):
        if not os.path.exists(self.current_srt_file):
            return
            
        try:
            with open(self.current_srt_file, "r", encoding="utf-8") as f:
                content = f.read()
                self.srt_text.config(state=tk.NORMAL)
                self.srt_text.delete("1.0", tk.END)
                self.srt_text.insert(tk.END, content)
                self.srt_text.config(state=tk.NORMAL)
        except Exception as e:
            self.log(f"Error al cargar SRT: {str(e)}")
    
    def load_srt(self):
        filetypes = (
            ("Archivos de subtítulos", "*.srt"),
            ("Todos los archivos", "*.*")
        )
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self.current_srt_file = path
            self.load_srt_into_editor()
            self.log(f"SRT cargado: {path}")
    
    def save_srt(self):
        if not self.current_srt_file:
            self.export_srt()
            return
            
        try:
            content = self.srt_text.get("1.0", tk.END)
            with open(self.current_srt_file, "w", encoding="utf-8") as f:
                f.write(content)
            self.log(f"SRT guardado: {self.current_srt_file}")
        except Exception as e:
            self.log(f"Error al guardar SRT: {str(e)}")
    
    def export_srt(self):
        filetypes = (
            ("Archivos de subtítulos", "*.srt"),
            ("Todos los archivos", "*.*")
        )
        path = filedialog.asksaveasfilename(
            defaultextension=".srt",
            filetypes=filetypes
        )
        if path:
            self.current_srt_file = path
            self.save_srt()
    
    def srt_text_modified(self, event):
        # Actualizar los subtítulos cuando se modifica el texto
        self.apply_srt_changes()
    
    def apply_srt_changes(self):
        try:
            content = self.srt_text.get("1.0", tk.END)
            lines = content.split('\n')
            subtitles = []
            i = 0
            
            while i < len(lines):
                # Buscar número de subtítulo
                if lines[i].strip().isdigit():
                    index = int(lines[i].strip())
                    i += 1
                    
                    # Buscar línea de tiempo
                    if i < len(lines) and '-->' in lines[i]:
                        times = lines[i].split('-->')
                        if len(times) == 2:
                            start = parse_time(times[0].strip())
                            end = parse_time(times[1].strip())
                            i += 1
                            
                            # Recopilar texto
                            text_lines = []
                            while i < len(lines) and lines[i].strip():
                                text_lines.append(lines[i].strip())
                                i += 1
                            
                            text = ' '.join(text_lines)
                            
                            subtitles.append({
                                'index': index,
                                'start': start,
                                'end': end,
                                'text': text
                            })
                i += 1
            
            self.subtitles = subtitles
            self.log(f"Subtítulos actualizados: {len(subtitles)} entradas")
            self.update_preview()
        except Exception as e:
            self.log(f"Error al analizar SRT: {str(e)}")
    
    def update_preview(self):
        if not self.subtitles or self.audio_data is None:
            return
        
        # Limpiar canvas
        self.preview_canvas.delete("all")
        
        # Crear figura de matplotlib
        fig, ax = plt.subplots(figsize=(12, 4))
        fig.set_facecolor("#2d2d2d")
        ax.set_facecolor("#2d2d2d")
        
        # Dibujar forma de onda
        time_axis = np.linspace(0, len(self.audio_data) / self.sample_rate, num=len(self.audio_data))
        ax.plot(time_axis, self.audio_data, color="#4e9a06", linewidth=0.5)
        
        # Dibujar subtítulos
        for i, sub in enumerate(self.subtitles):
            start = sub['start']
            end = sub['end']
            duration = end - start
            
            # Solo mostrar subtítulos con duración razonable
            if duration > 0.1 and duration < 30.0:
                ax.axvspan(start, end, alpha=0.3, color="#3465a4")
                
                # Mostrar texto para subtítulos significativos
                if duration > 1.0 and len(sub['text']) > 3:
                    # Acortar texto largo para visualización
                    display_text = sub['text']
                    if len(display_text) > 30:
                        display_text = display_text[:27] + "..."
                    
                    ax.text(start + duration/2, 0.8, display_text, 
                            ha='center', va='center', color='white', fontsize=8,
                            bbox=dict(facecolor='#204a87', alpha=0.7, boxstyle='round'))
        
        # Configurar ejes
        ax.set_xlabel('Tiempo (s)')
        ax.set_ylabel('Amplitud')
        ax.set_title('Alineación de Subtítulos')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.title.set_color('white')
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('white') 
        ax.spines['right'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.grid(color='#444444', linestyle='--', linewidth=0.5)
        
        # Convertir figura a imagen Tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.preview_canvas)
        canvas.draw()
        
        # Obtener el widget Tkinter
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.config(width=self.preview_canvas.winfo_width(), height=self.preview_canvas.winfo_height())
        self.preview_canvas.create_window(0, 0, anchor=tk.NW, window=canvas_widget)
        
        # Actualizar al cambiar tamaño
        canvas_widget.bind("<Configure>", lambda e: canvas_widget.config(
            width=e.width, 
            height=e.height
        ))

if __name__ == "__main__":
    root = ttk.Window()
    app = SubtitleGeneratorApp(root)
    root.mainloop()