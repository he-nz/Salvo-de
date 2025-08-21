# app.py (versão final com threading)
import os
import threading
import secrets
from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
from yt_dlp import YoutubeDL

app = Flask(__name__)

DOWNLOAD_DIR = Path("temp_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Dicionário para rastrear o status e o resultado dos jobs
jobs = {}

def perform_download_threaded(url, fmt, quality, job_id):
    """
    Esta função será executada em uma thread separada.
    Ela executa o download e atualiza o status no dicionário 'jobs'.
    """
    try:
        jobs[job_id]['status'] = 'processing'
        
        outtmpl = str(DOWNLOAD_DIR / '%(title)s - %(id)s.%(ext)s') # Adiciona ID para evitar nomes duplicados

        common_opts = {
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
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
            filename = ydl.prepare_filename(info)
            if fmt == "audio":
                filename = os.path.splitext(filename)[0] + ".mp3"
        
        # Armazena o nome do arquivo no sucesso
        jobs[job_id]['status'] = 'finished'
        jobs[job_id]['filename'] = os.path.basename(filename)

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

    # Cria e inicia a thread para o download
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

# A configuração do gunicorn (no Start Command da Render) cuidará de rodar o app
# O if __name__ == '__main__': não é usado em produção com gunicorn
