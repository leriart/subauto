import os
import warnings
import logging
import ttkbootstrap as ttk

from ttkbootstrap.constants import *
from pydub import AudioSegment

# Configurar logging para Vosk
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("vosk")
logger.setLevel(logging.WARNING)

from SubtitleGeneratorApp import SubtitleGeneratorApp

# ===================================================
# SOLUCIÓN PARA FFMPEG
# ===================================================
ffmpeg_path = r".\ffmpeg\bin\ffmpeg.exe"
if os.path.exists(ffmpeg_path):
    os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)
    AudioSegment.converter = ffmpeg_path
    AudioSegment.ffmpeg = ffmpeg_path
else:
    warnings.warn("FFmpeg no encontrado en la ruta especificada", RuntimeWarning)

if __name__ == "__main__":
    root = ttk.Window(themename="morph") # Cambia el tema aquí si lo deseas
    app = SubtitleGeneratorApp(root)
    root.mainloop()