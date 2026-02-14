import subprocess
import os
import signal
import sys

class BotManager:
    _instances = {}

    @classmethod
    def get_status(cls, bot_name):
        process = cls._instances.get(bot_name)
        if process and process.poll() is None:
            return "Running"
        return "Stopped"

    @classmethod
    def start_bot(cls, bot_name, script_path):
        if cls.get_status(bot_name) == "Running":
            return False, f"{bot_name} zaten çalışıyor."
        
        try:
            # Python executable yolunu al
            python_exe = sys.executable
            
            # Botu yeni bir process olarak başlat
            process = subprocess.Popen(
                [python_exe, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(os.path.abspath(script_path))
            )
            cls._instances[bot_name] = process
            return True, f"{bot_name} başlatıldı."
        except Exception as e:
            return False, f"Hata oluştu: {str(e)}"

    @classmethod
    def stop_bot(cls, bot_name):
        process = cls._instances.get(bot_name)
        if process and process.poll() is None:
            try:
                # Windows'ta process'i sonlandır
                if os.name == 'nt':
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(process.pid)])
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                
                cls._instances[bot_name] = None
                return True, f"{bot_name} durduruldu."
            except Exception as e:
                return False, f"Hata oluştu: {str(e)}"
        return False, f"{bot_name} zaten çalışmıyor."

    @classmethod
    def get_all_statuses(cls):
        return {
            'discord': cls.get_status('discord'),
            'telegram': cls.get_status('telegram')
        }
