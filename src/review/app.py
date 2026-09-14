"""
Review platform: the human-in-the-loop web UI. Every message the cadence
worker drafts lands here first — an owner reads it, rewrites it if they
want, picks the channel, and only THEIR click sends anything (email) or
records that they sent it themselves (LinkedIn/WhatsApp/iMessage). Nothing
in this codebase sends automatically; this app is the one and only front
door for turning a draft into an actual outreach.

Run locally:
    RM_ENV=development FLASK_APP=src.review.app flask run

The queue is read straight from Attio (status in suggested/in_review/
approved) so there is exactly one source of truth — no separate database
to fall out of sync with the CRM.
"""
from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, render_template_string, request

from src.attio.client import AttioClient
from src.attio.schema import PREFERRED_CHANNELS
from src.review.queue import (
    MANUAL_CHANNELS,
    SendNotAllowedError,
    approve,
    archive,
    confirm_manual_send,
    list_queue,
    save_draft,
    send_email,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)


def get_client() -> AttioClient:
    return AttioClient()


PAGE_TEMPLATE = """
<!doctype html>
<html>
<head>
  <title>Rift Capital — Outreach Review</title>
  <meta charset="utf-8">
  <style>
    body { font-family: -apple-system, sans-serif; max-width: 760px; margin: 2rem auto; color: #222; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1.25rem; }
    .status { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; color: #666; }
    textarea { width: 100%; min-height: 140px; font-family: inherit; font-size: 0.95rem; padding: 0.5rem; }
    select, button { padding: 0.4rem 0.7rem; margin-right: 0.5rem; margin-top: 0.5rem; }
    .evidence { font-size: 0.85rem; color: #555; font-style: italic; margin: 0.5rem 0; }
    button.primary { background: #1a73e8; color: white; border: none; border-radius: 4px; }
    button.danger { background: #b3261e; color: white; border: none; border-radius: 4px; }
    .empty { color: #777; }
  </style>
</head>
<body>
  <h1>Outreach review queue</h1>
  <p>Every draft below was proposed automatically from recorded evidence — none of it has been
  sent. Edit anything you like, pick the channel, approve it, then send it (email) or confirm you
  sent it yourself (LinkedIn / WhatsApp / iMessage). Nothing here ever sends on its own.</p>
  {% if not items %}
    <p class="empty">Nothing waiting on you right now.</p>
  {% endif %}
  {% for item in items %}
  <div class="card" data-record-id="{{ item.record_id }}">
    <div class="status">{{ item.status }} &middot; {{ item.person.name }}</div>
    <div class="evidence">Evidence: {{ item.evidence or "(none recorded)" }}</div>
    <textarea id="draft-{{ item.record_id }}">{{ item.draft_body }}</textarea>
    <div>
      <select id="channel-{{ item.record_id }}">
        {% for c in channels %}
        <option value="{{ c }}" {% if c == item.person.preferred_channel %}selected{% endif %}>{{ c }}</option>
        {% endfor %}
      </select>
      <button onclick="saveDraft('{{ item.record_id }}')">Save edit</button>
      <button class="primary" onclick="approveItem('{{ item.record_id }}')">Approve</button>
      <button class="primary" onclick="sendItem('{{ item.record_id }}')">Send / mark sent</button>
      <button class="danger" onclick="archiveItem('{{ item.record_id }}')">Archive</button>
    </div>
  </div>
  {% endfor %}
  <script>
    async function post(url, body) {
      const resp = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})});
      const data = await resp.json();
      if (!resp.ok) { alert(data.error || 'Request failed'); return null; }
      return data;
    }
    async function saveDraft(id) {
      const draft_body = document.getElementById('draft-' + id).value;
      const channel = document.getElementById('channel-' + id).value;
      const res = await post('/api/queue/' + id + '/save', {draft_body, channel});
      if (res) alert('Saved. Status is now in_review.');
    }
    async function approveItem(id) {
      const res = await post('/api/queue/' + id + '/approve', {});
      if (res) alert('Approved. Nothing has been sent yet.');
    }
    async function sendItem(id) {
      const channel = document.getElementById('channel-' + id).value;
      if (!confirm('Send/confirm on channel: ' + channel + '?')) return;
      const res = await post('/api/queue/' + id + '/send', {channel});
      if (res) { alert(res.message || 'Done.'); location.reload(); }
    }
    async function archiveItem(id) {
      if (!confirm('Archive this draft? It will not be re-suggested and nothing will be sent.')) return;
      const res = await post('/api/queue/' + id + '/archive', {});
      if (res) { alert('Archived.'); location.reload(); }
    }
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    items = list_queue(get_client())
    return render_template_string(PAGE_TEMPLATE, items=items, channels=PREFERRED_CHANNELS)


@app.route("/api/queue")
def api_queue():
    items = list_queue(get_client())
    return jsonify(
        [
            {
                "record_id": i.record_id,
                "name": i.person.name,
                "status": i.status,
                "draft_body": i.draft_body,
                "evidence": i.evidence,
                "channel": i.person.preferred_channel,
            }
            for i in items
        ]
    )


@app.route("/api/queue/<record_id>/save", methods=["POST"])
def api_save(record_id: str):
    body = request.get_json(force=True) or {}
    draft_body = body.get("draft_body", "")
    channel = body.get("channel", "email")
    result = save_draft(get_client(), record_id, draft_body=draft_body, channel=channel, dry_run=False)
    return jsonify({"ok": True, "result": result})


@app.route("/api/queue/<record_id>/approve", methods=["POST"])
def api_approve(record_id: str):
    result = approve(get_client(), record_id, dry_run=False)
    return jsonify({"ok": True, "result": result})


@app.route("/api/queue/<record_id>/archive", methods=["POST"])
def api_archive(record_id: str):
    result = archive(get_client(), record_id, dry_run=False)
    return jsonify({"ok": True, "result": result})


@app.route("/api/queue/<record_id>/send", methods=["POST"])
def api_send(record_id: str):
    body = request.get_json(force=True) or {}
    channel = body.get("channel", "email")
    client = get_client()

    items = {i.record_id: i for i in list_queue(client)}
    item = items.get(record_id)
    if item is None:
        return jsonify({"error": "record not found in queue"}), 404

    try:
        if channel in MANUAL_CHANNELS:
            confirm_manual_send(client, item.person, channel=channel)
            message = (
                f"Recorded: you confirmed sending this yourself via {channel}. "
                f"This system never sends on manual channels."
            )
        elif channel == "email":
            email = (item.person.raw.get("values", {}).get("email_addresses") or [{}])[0].get(
                "email_address", ""
            )
            audience_id = os.environ.get("RM_DEFAULT_MAILCHIMP_AUDIENCE_ID", "")
            send_email(client, item.person, email=email, audience_id=audience_id)
            message = "Email send requested (consent-gated; dry-run unless RM_ENV=production)."
        else:
            return jsonify({"error": f"unsupported channel '{channel}'"}), 400
    except SendNotAllowedError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"ok": True, "message": message})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(debug=os.environ.get("RM_ENV", "development") != "production")
