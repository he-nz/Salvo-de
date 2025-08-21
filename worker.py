# worker.py
import os
from pathlib import Path
from redis import Redis
from rq import Worker, Queue, Connection
from yt_dlp import YoutubeDL

# Configuração da pasta de download
DOWNLOAD_DIR = Path("temp_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Configuração da fila (deve ser a mesma do app.py)
listen = ['default']
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
conn = Redis.from_url(redis_url)

# Função de download real (a tarefa que o worker vai executar)
def perform_download(url, fmt, quality):
    """Executa o download usando yt-dlp."""

    # Esta função é uma versão simplificada da sua 'build_opts'
    # e da lógica de download, agora em um só lugar.
    outtmpl = str(DOWNLOAD_DIR / '%(title)s.%(ext)s')

    common_opts = {
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
    }

    if fmt == "audio":
        opts = {
            **common_opts,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else: # video
        video_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        opts = {
            **common_opts,
            'format': video_format,
            'merge_output_format': 'mp4',
        }

    # Adiciona cookies se o arquivo existir
    COOKIES_FILE = Path("cookies.txt")
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)

    # Executa o download
    with YoutubeDL(opts) as ydl:
        ydl.download([url])

if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()
