"""A small local shop with one documented, intentionally seeded defect.

This module is the application under test. It deliberately imports nothing from
``bugsafari`` or ``app`` so it stays an independent fixture.
"""

import os

from flask import Flask, render_template

DEMO_HOST = os.environ.get("BUGSAFARI_DEMO_HOST", "127.0.0.1")
# The standalone server uses a predictable port; managed runs pass port 0
# explicitly to ``make_server`` so they never collide with this one.
DEMO_PORT = int(os.environ.get("BUGSAFARI_DEMO_PORT", "5000"))


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def shop():
        return render_template("shop.html")

    return app


if __name__ == "__main__":
    create_app().run(host=DEMO_HOST, port=DEMO_PORT, debug=False)
