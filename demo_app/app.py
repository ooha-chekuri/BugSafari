"""A small local shop with one documented, intentionally seeded defect."""

from flask import Flask, render_template
from app.config import DEMO_HOST, DEMO_PORT


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def shop():
        return render_template("shop.html")

    return app


if __name__ == "__main__":
    create_app().run(host=DEMO_HOST, port=DEMO_PORT, debug=False)
