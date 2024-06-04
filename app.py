import base64
import os
import time
from datetime import datetime
from email.message import EmailMessage
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from io import BytesIO
from os.path import basename

import replicate
import requests
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from PIL import Image
from replicate.exceptions import ModelError
from werkzeug.exceptions import BadRequestKeyError
import smtplib

from config import REPLICATE_API_TOKEN, UPLOAD_FOLDER, DEBUG, SECRET_KEY, SMTP_SENDER, SMTP_SERVER, SMTP_PORT, \
    SMTP_USERNAME, SMTP_PASSWORD


def send_mail(send_to, subject, text, files=None):
    if not isinstance(send_to, list):
        send_to = [send_to]
    if files and not isinstance(files, list):
        files = [files]

    msg = EmailMessage()
    msg['From'] = SMTP_SENDER
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach(MIMEText(text))

    for f in files or []:
        with open(f, "rb") as fil:
            msg.add_attachment(fil.read(), maintype="image", subtype="png")

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(SMTP_USERNAME, SMTP_PASSWORD)

        smtp.sendmail(SMTP_SENDER, send_to, msg.as_string())


def create_app():
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["DEBUG"] = DEBUG
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    try:
        os.mkdir(UPLOAD_FOLDER)
    except OSError as e:
        print(e)

    @app.route('/uploads/<filename>')
    def show_file(filename=""):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.route("/", methods=["GET"])
    def upload():
        return render_template("upload.html")

    @app.route("/capture", methods=["POST"])
    def capture():
        if request.method == 'POST':
            image_data_url = request.form.get("image")
            age = request.form.get("age")

            # Decode the base64 data URL to obtain the image data
            image_data = base64.b64decode(image_data_url.split(",")[1])

            # Generate a filename with the current date and time
            filename = f"{datetime.now().isoformat().replace(':', '-').split('.')[0]}.png"

            # Save the image in PNG format
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            with open(file_path, "wb") as fh:
                fh.write(image_data)

            return redirect(url_for("show", filename=filename, age=age))

        return redirect(url_for("upload"))

    @app.route("/show", methods=["GET"])
    def show():
        try:
            filename = request.args["filename"]
            age = request.args["age"]
        except BadRequestKeyError:
            return redirect(url_for("upload"))

        if os.path.isfile(os.path.join(app.config["UPLOAD_FOLDER"], filename)):
            return render_template("show.html", filename=filename, age=age)
        else:
            return redirect(url_for("upload"))

    @app.route("/wait", methods=["GET"])
    def wait():
        try:
            filename = request.args["filename"]
            age = request.args["age"]
        except BadRequestKeyError:
            return redirect(url_for("upload"))

        with open(os.path.join(app.config["UPLOAD_FOLDER"], filename), "rb") as img:
            print(f"Création de l'input pour {filename}.")
            inpt = {
                "image": img,
                "target_age": str(age)
            }

            print(f"Création de l'output pour {filename}.")
            try:
                outpt = {
                    "age": inpt["target_age"],
                    "image": replicate.run(
                        "yuval-alaluf/sam:9222a21c181b707209ef12b5e0d7e94c994b58f01c7b2fec075d2e892362f13c",
                        input=inpt,
                    ),
                }
            except ModelError as e:
                flash(str(e), "warning")
                return redirect(url_for("upload"))

            print(f"Output reçu: {str(outpt)}.")

            filename = f"{filename.split('.')[0]}_result.png"
            print(f"Sauvegarde de l'output {filename}.")
            with open(os.path.join(app.config["UPLOAD_FOLDER"], filename), "wb") as img:
                img.write(requests.get(outpt["image"]).content)

        print(f"Tout bon !.")
        return redirect(url_for("result", filename=filename, age=age))

    @app.route("/result", methods=["POST", "GET"])
    def result():
        try:
            filename = request.args["filename"]
            age = request.args["age"]
        except BadRequestKeyError:
            return redirect(url_for("upload"))

        if request.method == "POST":
            print(request.form)
            if "reset" in request.form:
                return redirect(url_for("upload"))
            if "print" in request.form:
                success = True
                if success:
                    flash("Impression en cours !", "success")
                else:
                    flash("Problème avec l'impression lol", "danger")
            elif "email" in request.form:
                if request.form.get("address", "") == "":
                    flash("Tu as oublié l'email lol", "warning")
                else:
                    try:
                        send_mail(
                            request.form.get("address", ""),
                            "lafet",
                            """on aime la fete ici hihi""",
                            os.path.join(app.config["UPLOAD_FOLDER"], filename),
                        )
                        flash("Email envoyé !", "success")
                    except smtplib.SMTPRecipientsRefused as e:
                        flash("L'adresse email est fausse lol", "warning")
                    except Exception as e:
                        print(e)
                        flash("Il y a eu un souci déso lol", "danger")
            else:
                pass
            return redirect(url_for("result", filename=filename, age=age))

        return render_template("result.html", filename=filename, age=age)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run()
