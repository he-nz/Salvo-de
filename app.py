# app.py (versão com sanitização de nome de arquivo)
import os
import threading
import secrets
import re  
from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
from yt_dlp import YoutubeDL

app = Flask(__name__)

DOWNLOAD_DIR = Path("temp_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

jobs = {}

# <<< NOVO: Função para limpar/sanitizar o nome do arquivo
def sanitize_filename(filename):
    """
    Remove caracteres inválidos de um nome de arquivo, mantendo apenas
    letras, números, pontos, hífens e underscores.
    Espaços são substituídos por underscores.
    """
    # Substitui espaços por underscores
    filename = filename.replace(' ', '_')
    # Remove todos os caracteres que não sejam alfanuméricos, pontos, hífens ou underscores
    filename = re.sub(r'[^\w.\-]', '', filename)
    # Garante que não comece com caracteres que possam ser problemáticos
    filename = re.sub(r'^[._-]+', '', filename)
    if not filename:
        # Se o nome do arquivo ficar vazio após a limpeza, gera um nome aleatório
        return f"download_{secrets.token_hex(4)}.mp4"
    return filename

def perform_download_threaded(url, fmt, quality, job_id):
    """
    Esta função será executada em uma thread separada.
    """
    try:
        jobs[job_id]['status'] = 'processing'
        
        outtmpl = str(DOWNLOAD_DIR / '%(title)s - %(id)s.%(ext)s')

        common_opts = {
            'outtmpl': outtmpl, 'quiet': True, 'no_warnings': True,
        }
        if fmt == "audio":
            opts = {**common_opts, 'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]}
        else:
            video_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            opts = {**common_opts, 'format': video_format, 'merge_output_format': 'mp4'}
        COOKIES_FILE = Path("cookies.txt")
        if COOKIES_FILE.exists():
            opts["cookiefile"] = str(COOKIES_FILE)

        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            original_full_path_str = ydl.prepare_filename(info)
            if fmt == "audio":
                original_full_path_str = os.path.splitext(original_full_path_str)[0] + ".mp3"
        
        # --- LÓGICA DE SANITIZAÇÃO E RENOMEAÇÃO ---
        original_basename = os.path.basename(original_full_path_str)
        safe_basename = sanitize_filename(original_basename) # Limpa o nome do arquivo

        original_filepath = DOWNLOAD_DIR / original_basename
        safe_filepath = DOWNLOAD_DIR / safe_basename

        # Renomeia o arquivo no disco para o nome seguro
        os.rename(original_filepath, safe_filepath)
        
        # Armazena o nome do arquivo SEGURO no sucesso
        jobs[job_id]['status'] = 'finished'
        jobs[job_id]['filename'] = safe_basename # <<< Usa o nome seguro

    except Exception as e:
        print(f"Erro no Job {job_id}: {e}")
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url")
    fmt = request.form.get("format", "video")
    quality = request.form.get("quality", "best")

    if not url:
        return jsonify({"status": "erro", "message": "Nenhuma URL recebida."})

    job_id = secrets.token_hex(8)
    jobs[job_id] = {'status': 'queued'}

    thread = threading.Thread(target=perform_download_threaded, args=(url, fmt, quality, job_id))
    thread.start()

    return jsonify({"status": "processing", "job_id": job_id})

@app.route("/status/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"status": "not_found"}), 404
    return jsonify(job)

@app.route("/getfile", methods=["GET"])
def getfile():
    filename = request.args.get("file")
    if not filename or ".." in filename or filename.startswith("/"):
        return "Nome de arquivo inválido.", 400
        
    filepath = DOWNLOAD_DIR / filename
    if filepath.is_file():
        return send_file(str(filepath), as_attachment=True)
    return "Arquivo não encontrado.", 404
