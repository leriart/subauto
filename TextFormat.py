import unicodedata
from datetime import timedelta

class TextFormat:
    """
    A class to format text for display in a GUI application.
    """

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
