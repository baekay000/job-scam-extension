from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess

app = Flask(__name__)
CORS(app)  # <-- This allows requests from Chrome extension

@app.route("/check_job", methods=["POST"])
def check_job():
    data = request.json
    job_text = data.get("text", "")
    try:
        with open("temp_job.txt", "w", encoding="utf-8") as f:
            f.write(job_text)
        
        result = subprocess.run(
            ["python3", "../rag_single.py", "--file", "temp_job.txt"],
            capture_output=True,
            text=True
        )
        return jsonify({"output": result.stdout})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
