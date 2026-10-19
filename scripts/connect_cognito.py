"""Write public Cognito identifiers to Angular and backend configuration without logging secrets."""

import argparse
import json
import re
from pathlib import Path


def connect(region: str, pool_id: str, client_id: str) -> None:
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", region):
        raise ValueError("Invalid AWS region")
    if not re.fullmatch(re.escape(region) + r"_[A-Za-z0-9]+", pool_id):
        raise ValueError("User pool must belong to the selected region")
    if not re.fullmatch(r"[A-Za-z0-9]{1,128}", client_id):
        raise ValueError("Invalid Cognito app client ID")
    root = Path(__file__).resolve().parents[1]
    updates = {
        "COGNITO_REGION": region,
        "COGNITO_USER_POOL_ID": pool_id,
        "COGNITO_APP_CLIENT_ID": client_id,
    }
    for service in ("catalog", "booking", "payment", "admission"):
        env_file = root / "services" / service / ".env"
        if not env_file.exists():
            env_file.write_text(
                (env_file.parent / ".env.example").read_text(encoding="utf-8-sig"), encoding="utf-8"
            )
        lines = env_file.read_text(encoding="utf-8-sig").splitlines()
        lines = [line for line in lines if line.partition("=")[0].strip() not in updates]
        lines.extend(f"{key}={value}" for key, value in updates.items())
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    config_file = root / "frontend/public/app-config.json"
    config = json.loads(config_file.read_text(encoding="utf-8"))
    config["cognito"] = {"region": region, "userPoolId": pool_id, "userPoolClientId": client_id}
    config_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print("Cognito identifiers configured. Recreate/restart the API and reload Angular.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--pool-id", required=True)
    parser.add_argument("--client-id", required=True)
    arguments = parser.parse_args()
    connect(arguments.region, arguments.pool_id, arguments.client_id)
