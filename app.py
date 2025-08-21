# app.py (versão modificada)
import os
from flask import Flask, render_template, request, jsonify, send_file
from redis import Redis
from rq import Queue
from pathlib import Path

app = Flask(__name__)

# Conexão com a fila Redis
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
conn = Redis.from_url(redis_url)
q = Queue(connection=conn)

# Diretório de downloads (deve ser o mesmo do worker.py)
DOWNLOAD_DIR = Path("temp_downloads")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    """Esta função agora apenas adiciona uma tarefa à fila."""
    url = request.form.get("url")
    fmt = request.form.get("format", "video")
    quality = request.form.get("quality", "best")

    if not url:
        return jsonify({"status": "erro", "message": "Nenhuma URL recebida."})

    # Adiciona a tarefa de download à fila
    # A string 'worker.perform_download' diz ao RQ para executar a função 'perform_download' do arquivo 'worker.py'
    job = q.enqueue('worker.perform_download', url, fmt, quality, job_timeout=3600) # Timeout de 1 hora para o job

    return jsonify({
        "status": "processing",
        "job_id": job.get_id()
    })

@app.route("/status/<job_id>")
def job_status(job_id):
    """Verifica o status de uma tarefa."""
    job = q.fetch_job(job_id)

    if job:
        if job.is_finished:
            # Se o job terminou, precisamos descobrir o nome do arquivo que foi baixado.
            # Esta é uma parte complexa. Para simplificar, vamos assumir que o download foi bem-sucedido
            # e que o frontend vai precisar que o usuário digite o nome do arquivo ou vamos listar os arquivos.
            # Uma solução real exigiria que o worker retornasse o nome do arquivo.
            # Por agora, vamos apenas confirmar a conclusão.
            # NOTA: O resultado do job (o nome do arquivo) não está sendo passado aqui,
            # o que precisaria de uma lógica mais avançada para ser implementado.
            return jsonify({"status": "finished"})
        elif job.is_failed:
            return jsonify({"status": "failed"})
        else:
            return jsonify({"status": "processing"})
    else:
        return jsonify({"status": "not_found"}), 404

# A rota getfile continua a mesma
@app.route("/getfile", methods=["GET"])
def getfile():
    filename = request.args.get("file")
    if not filename or ".." in filename or filename.startswith("/"):
        return "Nome de arquivo inválido.", 400

    filepath = DOWNLOAD_DIR / filename
    if filepath.is_file():
        return send_file(str(filepath), as_attachment=True)
    return "Arquivo não encontrado.", 404

if __name__ == '__main__':
    app.run(debug=True)
