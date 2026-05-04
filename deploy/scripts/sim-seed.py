#!/usr/bin/env python3
"""sim-seed.py — Seed minimal data for sim mode.

Inserts:
  - 1 company (IoT Sim Co.)
  - 1 site (Sim Farm)
  - 1 user (admin@sim.local) + admin role
  - 1 gateway (serial = $SEED_GATEWAY env var)
  - 1 sensor profile (env-6in1-sim)
  - 6 sensor channels (slug: env-1, all measurements come from same channel)
  - 2 actuator channels (slug: relay-vent, relay-spray)

Idempotent: if rows already exist (matched by unique columns), skip.

env vars:
  SEED_DB, SEED_USER, SEED_PASSWORD — PostgreSQL credentials
  SEED_GATEWAY — gateway serial_number (default: GW-SIMTEST)
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras

DB = os.environ.get("SEED_DB", "iot_sim")
USER = os.environ.get("SEED_USER", "iot_sim")
PASS = os.environ.get("SEED_PASSWORD", "")
GATEWAY_SERIAL = os.environ.get("SEED_GATEWAY", "GW-SIMTEST")


def main() -> int:
    if not PASS:
        print("ERROR: SEED_PASSWORD env var required", file=sys.stderr)
        return 1
    conn = psycopg2.connect(
        host="127.0.0.1", port=5432, dbname=DB, user=USER, password=PASS
    )
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Company
    cur.execute("SELECT id FROM companies WHERE name = %s", ("IoT Sim Co.",))
    row = cur.fetchone()
    if row:
        company_id = row["id"]
        print(f"  company exists: {company_id}")
    else:
        company_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO companies (id, name, company_type) VALUES (%s, %s, 'management')",
            (str(company_id), "IoT Sim Co."),
        )
        print(f"  company created: {company_id}")

    # Site
    cur.execute(
        "SELECT id FROM sites WHERE company_id = %s AND name = %s",
        (str(company_id), "Sim Farm"),
    )
    row = cur.fetchone()
    if row:
        site_id = row["id"]
    else:
        site_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO sites (id, company_id, name) VALUES (%s, %s, %s)",
            (str(site_id), str(company_id), "Sim Farm"),
        )
        print(f"  site created: {site_id}")

    # User (Keycloak ID = sim-admin, email = admin@sim.local)
    cur.execute("SELECT id FROM users WHERE email = %s", ("admin@sim.local",))
    row = cur.fetchone()
    if row:
        user_id = row["id"]
    else:
        user_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO users (id, keycloak_user_id, email, name) VALUES (%s, %s, %s, %s)",
            (str(user_id), "sim-admin", "admin@sim.local", "Sim Admin"),
        )
        print(f"  user created: {user_id}")

    # User-company admin role
    cur.execute(
        """
        INSERT INTO user_company_roles (id, user_id, company_id, role)
        VALUES (%s, %s, %s, 'company_admin')
        ON CONFLICT (user_id, company_id, role) DO NOTHING
        """,
        (str(uuid.uuid4()), str(user_id), str(company_id)),
    )

    # Gateway
    cur.execute("SELECT id FROM gateways WHERE serial_number = %s", (GATEWAY_SERIAL,))
    row = cur.fetchone()
    if row:
        gateway_id = row["id"]
        print(f"  gateway exists: {gateway_id} ({GATEWAY_SERIAL})")
    else:
        gateway_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO gateways (id, serial_number, name, company_id, site_id, status)
            VALUES (%s, %s, %s, %s, %s, 'offline')
            """,
            (str(gateway_id), GATEWAY_SERIAL, "Sim Gateway 01", str(company_id), str(site_id)),
        )
        print(f"  gateway created: {gateway_id} ({GATEWAY_SERIAL})")

    # User-gateway permission (admin)
    cur.execute(
        """
        INSERT INTO user_gateway_permissions (id, user_id, gateway_id, permission)
        VALUES (%s, %s, %s, 'admin')
        ON CONFLICT (user_id, gateway_id, permission) DO NOTHING
        """,
        (str(uuid.uuid4()), str(user_id), str(gateway_id)),
    )

    # Sensor profile (read shared schema example)
    profile_path = (
        Path(__file__).resolve().parents[2]
        / "shared" / "examples" / "livestock_6in1_rs485.json"
    )
    profile_json = json.loads(profile_path.read_text())
    cur.execute(
        "SELECT id FROM sensor_profiles WHERE name = %s", ("env-6in1-sim",)
    )
    row = cur.fetchone()
    if row:
        profile_id = row["id"]
    else:
        profile_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO sensor_profiles (id, name, vendor, model, protocol, profile_schema, enabled)
            VALUES (%s, %s, 'Sim Vendor', 'env-6in1-sim', 'modbus_rtu', %s, true)
            """,
            (str(profile_id), "env-6in1-sim", json.dumps(profile_json)),
        )
        print(f"  sensor profile created: {profile_id}")

    # Sensor channel (slug = env-1, gateway YAML과 일치)
    cur.execute(
        "SELECT id FROM sensor_channels WHERE gateway_id = %s AND slug = %s",
        (str(gateway_id), "env-1"),
    )
    row = cur.fetchone()
    if row:
        sensor_ch_id = row["id"]
    else:
        sensor_ch_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO sensor_channels
              (id, gateway_id, slug, sensor_profile_id, display_name,
               interface_name, protocol, address, slave_id, polling_interval_sec, enabled)
            VALUES (%s, %s, 'env-1', %s, '환경 6-in-1 센서',
                    '/dev/null', 'modbus_rtu', '0001', 1, 5, true)
            """,
            (str(sensor_ch_id), str(gateway_id), str(profile_id)),
        )
        print(f"  sensor channel env-1 created: {sensor_ch_id}")

    # Actuator channels (slug = relay-vent, relay-spray)
    for slug, name, hw, max_on in [
        ("relay-vent", "환기팬", "GPIO17", 600),
        ("relay-spray", "살균기", "GPIO27", 60),
    ]:
        cur.execute(
            "SELECT id FROM actuator_channels WHERE gateway_id = %s AND slug = %s",
            (str(gateway_id), slug),
        )
        row = cur.fetchone()
        if row:
            print(f"  actuator {slug} exists: {row['id']}")
            continue
        ch_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO actuator_channels
              (id, gateway_id, slug, display_name, actuator_type, hardware_channel,
               default_state, enabled, safety_config)
            VALUES (%s, %s, %s, %s, 'relay', %s, 'off', true, %s)
            """,
            (
                str(ch_id),
                str(gateway_id),
                slug,
                name,
                hw,
                json.dumps({"max_on_duration_sec": max_on}),
            ),
        )
        print(f"  actuator {slug} created: {ch_id}")

    conn.commit()
    cur.close()
    conn.close()

    print()
    print("Seed complete.")
    print(f"  Gateway UUID:   {gateway_id}")
    print(f"  Gateway serial: {GATEWAY_SERIAL}")
    print(f"  Admin user:     admin@sim.local (kc_id=sim-admin)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
