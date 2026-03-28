from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os
import sys
import pandas as pd
from datetime import datetime

app = Flask(__name__)

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
SLOT_FILE = os.path.join(BASE_DIR, "parking_slots.json")
DATA_FILE = os.path.join(BASE_DIR, "parking_data.xlsx")
LISTS_FILE = os.path.join(BASE_DIR, "vehicle_lists.json")

sys.path.insert(0, BASE_DIR)
from slot_manager import (
    reserve_slot, cancel_reservation,
    add_to_blacklist, remove_from_blacklist,
    add_to_whitelist, remove_from_whitelist,
    load_lists
)

OVERSTAY_HOURS = 2      # Flag vehicle if parked longer than this
FEE_RATE = 10           # Rs per hour


def load_slots():
    with open(SLOT_FILE, "r") as f:
        return json.load(f)


def load_fee_map():
    try:
        df = pd.read_excel(DATA_FILE, sheet_name="CURRENT_VEHICLES")
        return dict(zip(df["Vehicle Number"].astype(str), df["Entry Time"].astype(str)))
    except Exception:
        return {}


@app.route("/")
def dashboard():
    data = load_slots()
    slots = data["slots"]
    waiting_queue = data.get("waiting_queue", [])
    fee_map = load_fee_map()

    for slot in slots:
        slot["duration"] = ""
        slot["estimated_fee"] = ""
        slot["overstay"] = False

        if slot["plate"] and slot["plate"] in fee_map:
            try:
                entry_dt = pd.to_datetime(fee_map[slot["plate"]])
                now = datetime.now()
                duration_mins = int((now - entry_dt).total_seconds() / 60)
                hours = duration_mins // 60
                mins = duration_mins % 60
                estimated_fee = max(FEE_RATE, round((duration_mins / 60) * FEE_RATE, 2))
                slot["duration"] = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
                slot["estimated_fee"] = f"Rs. {estimated_fee}"
                slot["overstay"] = (duration_mins / 60) > OVERSTAY_HOURS
            except Exception:
                pass

    total = len(slots)
    free = sum(1 for s in slots if s["status"] == "free")
    occupied = sum(1 for s in slots if s["status"] in ["pending", "occupied"])
    reserved = sum(1 for s in slots if s["status"] == "reserved")
    overstay_count = sum(1 for s in slots if s.get("overstay"))
    occupancy_rate = int((occupied / total) * 100) if total > 0 else 0

    lists = load_lists()

    return render_template(
        "dashboard.html",
        slots=slots,
        total=total,
        free=free,
        occupied=occupied,
        reserved=reserved,
        overstay_count=overstay_count,
        occupancy_rate=occupancy_rate,
        waiting_queue=waiting_queue,
        blacklist=lists.get("blacklist", []),
        whitelist=lists.get("whitelist", []),
    )


# ── Reservation ───────────────────────────────────────────────────────────────

@app.route("/reserve", methods=["POST"])
def reserve():
    vehicle_number = request.form.get("vehicle_number", "").strip().upper()
    if vehicle_number:
        slot_id = reserve_slot(vehicle_number)
        if slot_id:
            return redirect(url_for("dashboard") + f"?msg=Reserved+Slot+{slot_id}+for+{vehicle_number}")
        else:
            return redirect(url_for("dashboard") + "?msg=No+free+slots+available")
    return redirect(url_for("dashboard"))


@app.route("/cancel_reservation", methods=["POST"])
def cancel_res():
    vehicle_number = request.form.get("vehicle_number", "").strip().upper()
    if vehicle_number:
        cancel_reservation(vehicle_number)
    return redirect(url_for("dashboard"))


# ── Blacklist / Whitelist ─────────────────────────────────────────────────────

@app.route("/blacklist/add", methods=["POST"])
def blacklist_add():
    v = request.form.get("vehicle_number", "").strip().upper()
    if v:
        add_to_blacklist(v)
    return redirect(url_for("dashboard"))


@app.route("/blacklist/remove", methods=["POST"])
def blacklist_remove():
    v = request.form.get("vehicle_number", "").strip().upper()
    if v:
        remove_from_blacklist(v)
    return redirect(url_for("dashboard"))


@app.route("/whitelist/add", methods=["POST"])
def whitelist_add():
    v = request.form.get("vehicle_number", "").strip().upper()
    if v:
        add_to_whitelist(v)
    return redirect(url_for("dashboard"))


@app.route("/whitelist/remove", methods=["POST"])
def whitelist_remove():
    v = request.form.get("vehicle_number", "").strip().upper()
    if v:
        remove_from_whitelist(v)
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
