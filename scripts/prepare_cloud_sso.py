"""Prepare public SSO configuration only. Never signs in or handles credentials."""

import argparse
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSION = "sso-session wonderland-personal"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=["wonderland-readonly", "wonderland-feasibility"],
        default="wonderland-readonly",
    )
    args = parser.parse_args()
    profile = f"profile {args.profile}"
    role = {
        "wonderland-readonly": "WonderlandReadOnly",
        "wonderland-feasibility": "WonderlandFeasibility",
    }[args.profile]
    path = ROOT / ".local/aws/config"
    config = configparser.ConfigParser(interpolation=None)
    config.read(path, encoding="utf-8")
    if config.has_section(profile) and any(
        key in config[profile] for key in ("login_session", "credential_process", "role_arn")
    ):
        raise RuntimeError("Existing profile has another authentication method; review it")
    for name in (profile, SESSION):
        if not config.has_section(name):
            config.add_section(name)
    config[profile].update(
        sso_session="wonderland-personal",
        sso_account_id="708919751353",
        sso_role_name=role,
        region="ap-south-1",
        output="json",
    )
    config[SESSION].update(
        sso_start_url="https://d-9f675820da.awsapps.com/start",
        sso_region="ap-south-1",
        sso_registration_scopes="sso:account:access",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".pending")
    with temporary.open("w", encoding="utf-8") as output:
        config.write(output)
    temporary.replace(path)
    print(f"Prepared {args.profile} for {role} in account 708919751353.")
    print("User creation, account assignment and browser sign-in are still required.")


if __name__ == "__main__":
    main()
