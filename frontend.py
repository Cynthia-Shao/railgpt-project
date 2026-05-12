from flask import Flask, send_from_directory
import os, webbrowser, json

app = Flask(__name__)
FILE_DIR = "files"
os.makedirs(FILE_DIR, exist_ok=True)

HTML_PATH = os.path.join(os.path.dirname(__file__), "index.html")


@app.route("/")
def index():
    file_list = [f for f in os.listdir(FILE_DIR) if os.path.isfile(os.path.join(FILE_DIR, f))]
    file_options = ""
    for f in file_list:
        ext = os.path.splitext(f)[1].lower()
        icon = {"pdf": "📑", "xlsx": "📊", "xls": "📊", "doc": "📘", "docx": "📘", "txt": "📄"}.get(ext, "📎")
        file_options += f'<div class="file-item" ondblclick="window.open(\'/file/{f}\',\'_blank\')"><span class="file-icon">{icon}</span><span>{f}</span></div>\n'

    html = open(HTML_PATH, encoding="utf-8").read()
    html = html.replace("{{FILE_LIST}}", file_options)
    return html


@app.route("/file/<filename>")
def get_file(filename):
    return send_from_directory(FILE_DIR, filename)


def _open_app_window(url):
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in chrome_paths:
        if os.path.exists(p):
            import subprocess
            subprocess.Popen([p, f"--app={url}", "--window-size=1200,800"])
            return
    webbrowser.open(url)


if __name__ == "__main__":
    _open_app_window("http://127.0.0.1:5002")
    app.run(port=5002, debug=False)
