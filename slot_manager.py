import json
import os

SLOT_FILE = "parking_slots.json"
LISTS_FILE = "vehicle_lists.json"


def load_slots():
    with open(SLOT_FILE, "r") as f:
        return json.load(f)


def save_slots(data):
    with open(SLOT_FILE, "w") as f:
        json.dump(data, f, indent=4)


def load_lists():
    if not os.path.exists(LISTS_FILE):
        data = {"blacklist": [], "whitelist": []}
        with open(LISTS_FILE, "w") as f:
            json.dump(data, f, indent=4)
        return data
    with open(LISTS_FILE, "r") as f:
        return json.load(f)


def save_lists(data):
    with open(LISTS_FILE, "w") as f:
        json.dump(data, f, indent=4)


def load_waiting_queue():
    data = load_slots()
    return data.get("waiting_queue", [])


def save_waiting_queue(queue):
    data = load_slots()
    data["waiting_queue"] = queue
    save_slots(data)


# Blacklist / Whitelist

def is_blacklisted(vehicle_number):
    lists = load_lists()
    return vehicle_number in lists.get("blacklist", [])


def is_whitelisted(vehicle_number):
    lists = load_lists()
    return vehicle_number in lists.get("whitelist", [])


def add_to_blacklist(vehicle_number):
    lists = load_lists()
    if vehicle_number not in lists["blacklist"]:
        lists["blacklist"].append(vehicle_number)
        save_lists(lists)
        print(f"[BLACKLIST] Added {vehicle_number}")


def remove_from_blacklist(vehicle_number):
    lists = load_lists()
    if vehicle_number in lists["blacklist"]:
        lists["blacklist"].remove(vehicle_number)
        save_lists(lists)


def add_to_whitelist(vehicle_number):
    lists = load_lists()
    if vehicle_number not in lists["whitelist"]:
        lists["whitelist"].append(vehicle_number)
        save_lists(lists)
        print(f"[WHITELIST] Added {vehicle_number}")


def remove_from_whitelist(vehicle_number):
    lists = load_lists()
    if vehicle_number in lists["whitelist"]:
        lists["whitelist"].remove(vehicle_number)
        save_lists(lists)


# Slot Allocation

def allocate_slot(vehicle_number):
    data = load_slots()

    # Use reserved slot if exists
    for slot in data["slots"]:
        if slot["plate"] == vehicle_number and slot["status"] == "reserved":
            slot["status"] = "pending"
            slot["ir_confirmed"] = False
            save_slots(data)
            print(f"[RESERVED->PENDING] Vehicle {vehicle_number} -> Slot {slot['slot_id']}")
            return slot["slot_id"]

    # Allocate next free slot
    for slot in data["slots"]:
        if slot["status"] == "free" and slot["type"] == "normal":
            slot["status"] = "pending"
            slot["plate"] = vehicle_number
            slot["ir_confirmed"] = False
            save_slots(data)
            print(f"[ALLOCATED] Vehicle {vehicle_number} -> Slot {slot['slot_id']}")
            return slot["slot_id"]

    # No free slot - add to waiting queue
    queue = load_waiting_queue()
    if vehicle_number not in queue:
        queue.append(vehicle_number)
        save_waiting_queue(queue)
        print(f"[WAITING] No free slot - {vehicle_number} added to queue (position {len(queue)})")

    return None


def reserve_slot(vehicle_number):
    data = load_slots()

    for slot in data["slots"]:
        if slot["plate"] == vehicle_number and slot["status"] == "reserved":
            print(f"[RESERVE] {vehicle_number} already has a reservation")
            return slot["slot_id"]

    for slot in data["slots"]:
        if slot["status"] == "free":
            slot["status"] = "reserved"
            slot["plate"] = vehicle_number
            slot["ir_confirmed"] = False
            save_slots(data)
            print(f"[RESERVED] Vehicle {vehicle_number} -> Slot {slot['slot_id']}")
            return slot["slot_id"]

    print(f"[RESERVE FAILED] No free slot for {vehicle_number}")
    return None


def cancel_reservation(vehicle_number):
    data = load_slots()
    for slot in data["slots"]:
        if slot["plate"] == vehicle_number and slot["status"] == "reserved":
            slot["status"] = "free"
            slot["plate"] = None
            slot["ir_confirmed"] = False
            save_slots(data)
            print(f"[RESERVATION CANCELLED] {vehicle_number} -> Slot {slot['slot_id']} freed")
            return slot["slot_id"]
    return None


def free_slot(vehicle_number):
    data = load_slots()

    freed_slot_id = None
    for slot in data["slots"]:
        if slot["plate"] == vehicle_number:
            slot["status"] = "free"
            slot["plate"] = None
            slot["ir_confirmed"] = False
            freed_slot_id = slot["slot_id"]
            save_slots(data)
            print(f"[FREED] Vehicle {vehicle_number} -> Slot {slot['slot_id']}")
            break

    if freed_slot_id is None:
        print(f"[WARNING] No slot found for vehicle {vehicle_number}")
        return None

    # Assign freed slot to next in waiting queue
    queue = load_waiting_queue()
    if queue:
        next_vehicle = queue.pop(0)
        save_waiting_queue(queue)
        allocate_slot(next_vehicle)
        print(f"[QUEUE] Assigned freed slot to waiting vehicle {next_vehicle}")

    return freed_slot_id


def confirm_slot(vehicle_number):
    data = load_slots()
    for slot in data["slots"]:
        if slot["plate"] == vehicle_number and slot["status"] == "pending":
            slot["status"] = "occupied"
            slot["ir_confirmed"] = True
            save_slots(data)
            print(f"[CONFIRMED] Vehicle {vehicle_number} parked in Slot {slot['slot_id']}")
            return slot["slot_id"]
    print(f"[WARNING] No pending slot found for vehicle {vehicle_number}")
    return None
