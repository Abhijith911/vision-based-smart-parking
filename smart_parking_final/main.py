import cv2
import numpy as np
import time
import pytesseract
import re
import pandas as pd
import os
import threading
import serial
import serial.tools.list_ports
from datetime import datetime
from slot_manager import allocate_slot, free_slot, is_blacklisted, is_whitelisted, confirm_slot

# Fee rate: Rs. 10 per hour (minimum Rs. 10)
FEE_RATE_PER_HOUR = 10

file_name = "parking_data.xlsx"

if not os.path.exists(file_name):
    current_df = pd.DataFrame(columns=["Vehicle Number", "Entry Time", "Fee"])
    history_df = pd.DataFrame(columns=["Vehicle Number", "Entry Time", "Exit Time", "Fee"])

    with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
        current_df.to_excel(writer, sheet_name="CURRENT_VEHICLES", index=False)
        history_df.to_excel(writer, sheet_name="HISTORY_LOG", index=False)


def vehicle_entry(vehicle_number):
    current_df = pd.read_excel(file_name, sheet_name="CURRENT_VEHICLES")
    history_df = pd.read_excel(file_name, sheet_name="HISTORY_LOG")

    if vehicle_number in current_df["Vehicle Number"].values:
        return

    entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    current_df.loc[len(current_df)] = [vehicle_number, entry_time, ""]
    history_df.loc[len(history_df)] = [vehicle_number, entry_time, "", ""]

    with pd.ExcelWriter(file_name, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        current_df.to_excel(writer, sheet_name="CURRENT_VEHICLES", index=False)
        history_df.to_excel(writer, sheet_name="HISTORY_LOG", index=False)


def vehicle_exit(vehicle_number):
    current_df = pd.read_excel(file_name, sheet_name="CURRENT_VEHICLES")
    history_df = pd.read_excel(file_name, sheet_name="HISTORY_LOG")

    if vehicle_number not in current_df["Vehicle Number"].values:
        return

    exit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Calculate fee based on duration
    entry_row = current_df[current_df["Vehicle Number"] == vehicle_number].iloc[0]
    entry_time_dt = pd.to_datetime(entry_row["Entry Time"])
    exit_time_dt = datetime.now()
    duration_hours = (exit_time_dt - entry_time_dt).total_seconds() / 3600
    fee = max(FEE_RATE_PER_HOUR, round(duration_hours * FEE_RATE_PER_HOUR, 2))
    fee_str = f"Rs. {fee}"

    current_df = current_df[current_df["Vehicle Number"] != vehicle_number]

    # FIX ADDED HERE
    history_df["Exit Time"] = history_df["Exit Time"].astype("object")

    mask = (
        (history_df["Vehicle Number"] == vehicle_number)
        & (history_df["Exit Time"].isna() | (history_df["Exit Time"] == ""))
    )
    history_df.loc[mask, "Exit Time"] = exit_time
    history_df["Fee"] = history_df["Fee"].astype("object")
    history_df.loc[mask, "Fee"] = fee_str

    with pd.ExcelWriter(file_name, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        current_df.to_excel(writer, sheet_name="CURRENT_VEHICLES", index=False)
        history_df.to_excel(writer, sheet_name="HISTORY_LOG", index=False)

    print(f"[EXIT] {vehicle_number} | Duration: {round(duration_hours*60)} mins | Fee: {fee_str}")


# ── ESP8266 Serial Setup ───────────────────────────────────────────────────────

# Tracks the last detected plate waiting for ultrasonic confirmation
last_detected_plate = None
last_detected_lock = threading.Lock()


def find_esp_port():
    """Auto detect ESP8266 USB port"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "USB" in port.description or "CH340" in port.description or "CP210" in port.description or "ttyUSB" in port.device:
            return port.device
    return "/dev/ttyUSB0"


def serial_listener():
    """Runs in background thread - listens for VEHICLE_DETECTED from ESP8266"""
    global last_detected_plate

    port = find_esp_port()
    print(f"[SERIAL] Connecting to ESP8266 on {port}")

    try:
        ser = serial.Serial(port, 9600, timeout=1)
        print(f"[SERIAL] Connected to ESP8266 on {port}")

        while True:
            try:
                line = ser.readline().decode("utf-8").strip()
                if line == "VEHICLE_DETECTED":
                    print(f"[ULTRASONIC] Vehicle confirmed by sensor")
                    with last_detected_lock:
                        if last_detected_plate:
                            confirm_slot(last_detected_plate)
                            print(f"[CONFIRMED] Slot confirmed for {last_detected_plate}")
                            last_detected_plate = None
            except Exception as e:
                print(f"[SERIAL] Read error: {e}")
                time.sleep(1)

    except Exception as e:
        print(f"[SERIAL] Could not connect to ESP8266: {e}")
        print("[SERIAL] Running without ultrasonic confirmation")


# Start serial listener in background thread
serial_thread = threading.Thread(target=serial_listener, daemon=True)
serial_thread.start()


# ── Pi Camera V2 initialization ───────────────────────────────────────────────

pipeline = "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink drop=1"
cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

if not cap.isOpened():
    exit()


prev_time = 0
last_box = None
miss_count = 0
MISS_THRESHOLD = 6

prev_box = None
stable_count = 0
STABLE_THRESHOLD = 10
POSITION_TOLERANCE = 15

cooldown_active = False
cooldown_start = 0
COOLDOWN_SECONDS = 5


while True:
    ret, frame = cap.read()
    if not ret:
        break

    current_time = time.time()
    fps = 1 / (current_time - prev_time) if prev_time != 0 else 0
    prev_time = current_time

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(blur, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    best_candidate = None
    best_area = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 400:
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            aspect_ratio = w / float(h)

            if 1.8 < aspect_ratio < 6 and w > 60 and h > 20:
                if area > best_area:
                    best_area = area
                    best_candidate = (x, y, w, h)

    if best_candidate is not None:
        last_box = best_candidate
        miss_count = 0
    else:
        miss_count += 1

    if last_box is not None and miss_count < MISS_THRESHOLD:
        x, y, w, h = last_box
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        if prev_box is not None:
            px, py, pw, ph = prev_box
            if abs(x - px) < POSITION_TOLERANCE and abs(y - py) < POSITION_TOLERANCE:
                stable_count += 1
            else:
                stable_count = 0
        else:
            stable_count = 0

        prev_box = (x, y, w, h)

        if stable_count >= STABLE_THRESHOLD and not cooldown_active:
            plate_img = gray[y:y+h, x:x+w]
            plate_img = cv2.resize(plate_img, None, fx=2, fy=2)
            plate_img = cv2.threshold(plate_img, 150, 255, cv2.THRESH_BINARY)[1]

            config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            text = pytesseract.image_to_string(plate_img, config=config)

            candidate = re.sub(r'[^A-Z0-9]', '', text.upper())

            candidate = candidate.replace('O', '0')
            candidate = candidate.replace('I', '1')
            candidate = candidate.replace('S', '5')
            candidate = candidate.replace('B', '8')

            if re.match(r'^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{3,4}$', candidate):

                # Blacklist check
                if is_blacklisted(candidate):
                    print(f"[BLOCKED] Vehicle {candidate} is blacklisted!")
                    cv2.putText(frame, f"BLOCKED: {candidate}", (10, 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                else:
                    current_df = pd.read_excel(file_name, sheet_name="CURRENT_VEHICLES")

                    if candidate in current_df["Vehicle Number"].values:
                        vehicle_exit(candidate)
                        free_slot(candidate)
                    else:
                        vehicle_entry(candidate)
                        slot_id = allocate_slot(candidate)
                        if slot_id:
                            # Store plate for ultrasonic confirmation
                            with last_detected_lock:
                                last_detected_plate = candidate
                            print(f"[WAITING CONFIRMATION] {candidate} -> Slot {slot_id}")

            cooldown_active = True
            cooldown_start = time.time()
            stable_count = 0

    if cooldown_active:
        if time.time() - cooldown_start > COOLDOWN_SECONDS:
            cooldown_active = False
        else:
            cv2.putText(
                frame,
                "LOCKED",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )

    cv2.putText(
        frame,
        f"FPS: {int(fps)}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 255),
        2,
    )

    cv2.imshow("Smart Parking System", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()