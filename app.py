from flask import Flask, render_template, request, jsonify, send_file
from yt_dlp import YoutubeDL
from pathlib import Path
import os
import secrets  # Importado para segurança

app = Flask(__name__)

# --- ALTERAÇÃO 1: Pasta de Download ---
# Alterado para uma pasta local. Em um servidor, não temos acesso à pasta "Downloads" do usuário.
# Esta pasta será criada dentro do diretório do seu projeto.
DOWNLOAD_DIR = Path("temp_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- ALTERAÇÃO 2: Remoção do Caminho do FFmpeg ---
# A linha abaixo foi removida. Vamos confiar no FFmpeg que já está instalado no servidor (ambiente nativo da Render).
# FFMPEG_PATH = str(Path(__file__).parent / "ffmpeg.exe")

def build_opts(fmt, quality):
    # Seleção de qualidade (simplificada para compatibilidade)
    if quality == "best":
        video_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    elif quality == "medium":
        video_format = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
    else: # low
        video_format = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best"

    # Caminho de saída
    outtmpl = str(DOWNLOAD_DIR / '%(title)s.%(ext)s')

    common_opts = {
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        # --- ALTERAÇÃO 3: Remoção da localização do FFmpeg ---
        # A opção 'ffmpeg_location' foi removida. yt-dlp irá procurar o ffmpeg no sistema.
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
        opts = {
            **common_opts,
            'format': video_format,
            'merge_output_format': 'mp4',
        }

    # cookies.txt (se existir)
    COOKIES_FILE = Path("cookies.txt") # Simplificado para buscar na raiz do projeto
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)

    return opts


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url")
    fmt = request.form.get("format", "video")
    quality = request.form.get("quality", "best") # Valores do HTML: best, medium, low

    if not url:
        return jsonify({"status": "erro", "message": "Nenhuma URL recebida."})

    opts = build_opts(fmt, quality)

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Se for áudio, a extensão já será trocada para .mp3 pelo postprocessor
            if fmt == "audio":
                # yt-dlp pode retornar o nome do arquivo antes da conversão, então trocamos a extensão
                base, _ = os.path.splitext(filename)
                final_filename = base + ".mp3"
            else:
                final_filename = filename
            
            # --- ALTERAÇÃO 4: Melhoria de Segurança e Lógica ---
            # Retornamos apenas o nome do arquivo, não o caminho completo.
            base_filename = os.path.basename(final_filename)

        return jsonify({
            "status": "ok",
            "message": "Download concluído!",
            "file": base_filename 
        })
    except Exception as e:
        # Não exponha o erro completo ao usuário por segurança
        error_id = secrets.token_hex(4)
        print(f"Erro {error_id}: {e}")
        return jsonify({"status": "erro", "message": f"Ocorreu um erro interno (ID: {error_id}). Verifique se o link é válido."})


@app.route("/getfile", methods=["GET"])
def getfile():
    # --- ALTERAÇÃO 5: Melhoria de Segurança ---
    # Recebemos apenas o nome do arquivo e o juntamos com nosso diretório seguro.
    filename = request.args.get("file")
    
    if not filename:
        return "Parâmetro 'file' ausente.", 400

    # Validação para impedir que usuários acessem outros diretórios (Path Traversal)
    if ".." in filename or filename.startswith("/"):
        return "Nome de arquivo inválido.", 400
        
    filepath = DOWNLOAD_DIR / filename

    if filepath.is_file():
        return send_file(str(filepath), as_attachment=True)
    
    return "Arquivo não encontrado ou já expirado.", 404


if __name__ == "__main__":
    # O host '0.0.0.0' é importante para a visibilidade em redes de contêineres como a da Render
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)