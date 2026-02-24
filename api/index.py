"""Flask app for subscribe/confirm/unsubscribe — deployed on Vercel."""

from __future__ import annotations

import datetime
import logging
import os
import sys

# Add src/ to path so we can import scraper.* modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
from flask import Flask, render_template, request

load_dotenv()  # for local development; Vercel uses env vars from dashboard

from scraper import db
from scraper.email_sender import send_confirmation, send_digest
from scraper.email_template import render_digest
from scraper.tokens import generate_token, verify_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"))


@app.route("/")
def subscribe_form():
    return render_template("subscribe.html")


@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email", "").strip().lower()
    if not email or "@" not in email:
        return render_template("error.html", message="Please enter a valid email address."), 400

    status = db.create_or_reactivate_subscriber(email)

    if status == "already_active":
        return render_template("success.html", message="You're already subscribed! You'll keep receiving weekly updates.")

    # For created, pending, or reactivated — send (or re-send) confirmation email
    token = generate_token(email, "confirm")
    base_url = os.environ["APP_BASE_URL"].rstrip("/")
    confirm_url = f"{base_url}/confirm?email={email}&token={token}"

    ok = send_confirmation(email, confirm_url)
    if ok:
        return render_template("success.html", message="Check your inbox! Click the confirmation link to complete your subscription.")
    else:
        return render_template("error.html", message="Something went wrong sending the confirmation email. Please try again later."), 500


@app.route("/confirm")
def confirm():
    email = request.args.get("email", "").strip().lower()
    token = request.args.get("token", "")

    if not email or not token:
        return render_template("error.html", message="Invalid confirmation link."), 400

    if not verify_token(email, "confirm", token):
        return render_template("error.html", message="Invalid or expired confirmation link."), 400

    db.activate_subscriber(email)

    # Send this week's digest immediately
    digest_sent = _send_immediate_digest(email)
    if digest_sent:
        message = "You'll receive a weekly digest every Monday. Your first digest is on its way — check your inbox!"
    else:
        message = "You'll receive a weekly digest of upcoming Helsinki GSE seminars every Monday."

    return render_template("confirmed.html", message=message)


def _send_immediate_digest(email: str) -> bool:
    """Send this week's events to a newly confirmed subscriber. Returns True if sent."""
    try:
        events = db.get_week_events()
        if not events:
            return False

        base_url = os.environ.get("APP_BASE_URL", "").rstrip("/")
        unsub_token = generate_token(email, "unsubscribe")
        unsub_url = f"{base_url}/unsubscribe?email={email}&token={unsub_token}"

        html = render_digest(events, unsubscribe_url=unsub_url)

        today = datetime.date.today()
        months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        subject = f"Helsinki GSE Seminars — Week of {today.day} {months[today.month]} {today.year}"

        return send_digest(email, subject, html, unsubscribe_url=unsub_url)
    except Exception:
        logger.exception("Failed to send immediate digest to %s", email)
        return False


@app.route("/unsubscribe")
def unsubscribe():
    email = request.args.get("email", "").strip().lower()
    token = request.args.get("token", "")

    if not email or not token:
        return render_template("error.html", message="Invalid unsubscribe link."), 400

    if not verify_token(email, "unsubscribe", token):
        return render_template("error.html", message="Invalid unsubscribe link."), 400

    db.deactivate_subscriber(email)
    return render_template("unsubscribed.html")
