"""Seed doctors into the production API via HTTP POST."""
import urllib.request
import urllib.error
import json

BASE_URL = "https://neocortex-api.onrender.com/api/v1"

DOCTORS = [
    {
        "name": "Dr. Sarah Levi",
        "specialty": "Neurology",
        "email": "sarah.levi@neocortex.health",
        "phone": "+972-50-1001001",
        "license_number": "IL-NEU-001",
    },
    {
        "name": "Dr. Alex Goren",
        "specialty": "Internal Medicine",
        "email": "alex.goren@neocortex.health",
        "phone": "+972-50-2002002",
        "license_number": "IL-INT-002",
    },
    {
        "name": "Dr. Dana Cohen",
        "specialty": "Cardiology",
        "email": "dana.cohen@neocortex.health",
        "phone": "+972-50-3003003",
        "license_number": "IL-CAR-003",
    },
]


def post_json(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get_json(url):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def seed():
    print(f"Target: {BASE_URL}\n")

    for doctor in DOCTORS:
        status, body = post_json(f"{BASE_URL}/doctors/", doctor)
        if status == 201:
            print(f"  Added    [{body['id']}] {body['name']} — {body['specialty']}")
        elif status == 409:
            print(f"  Skipped  {doctor['name']} (already exists)")
        else:
            print(f"  ERROR    {doctor['name']} — HTTP {status}: {body}")

    print("\nVerifying — current doctors in production:")
    doctors = get_json(f"{BASE_URL}/doctors/")
    for d in doctors:
        print(f"  [{d['id']}] {d['name']} — {d['specialty']} ({d['email']})")


if __name__ == "__main__":
    seed()
