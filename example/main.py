"""A tiny Flask app: type a URL, get a PNG or PDF snapshot of it back.

    pip install playwright-snap flask
    python -m playwright install chromium
    python main.py        # then open http://127.0.0.1:9898

It is pyppeteer-snap's example with the import switched from pyppesnap to playsnap.

Do not put it on the internet as it is: it opens any URL a visitor types,
including addresses inside your own network.
"""
from flask import Flask, render_template, request

from playsnap import get_image_snapshot_by_url, get_pdf_snapshot_by_url

app = Flask(__name__)


def snapshot(take):
    data = take(request.form.get("web_address", ""))
    if data is None:
        return "Could not take a snapshot of that page.", 502
    return data


@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")


@app.route("/get_web_image", methods=["POST"])
def get_web_image():
    return snapshot(get_image_snapshot_by_url)


@app.route("/get_web_pdf", methods=["POST"])
def get_web_pdf():
    return snapshot(get_pdf_snapshot_by_url)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=9898)
