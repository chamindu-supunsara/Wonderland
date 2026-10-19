"""Use existing Git Credential Manager authentication without printing credentials."""
import json
import subprocess
import urllib.error
import urllib.request

REPOSITORY = "chamindu-supunsara/Wonderland"


def credential_token():
    result = subprocess.run(["git", "credential", "fill"],
                            input="protocol=https\nhost=github.com\n\n", text=True,
                            capture_output=True, check=True, timeout=120)
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if not fields.get("password"):
        raise RuntimeError("GitHub authentication required")
    return fields["password"]


def artifact_bytes(artifact_id):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    url = f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{int(artifact_id)}/zip"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + credential_token(),
        "Accept": "application/vnd.github+json", "User-Agent": "Wonderland-Step11"})
    try:
        urllib.request.build_opener(NoRedirect).open(req, timeout=45)
    except urllib.error.HTTPError as error:
        if error.code != 302:
            raise RuntimeError(f"Artifact download HTTP {error.code}") from None
        target = error.headers["Location"]
    else:
        raise RuntimeError("Expected GitHub artifact redirect")
    if not target.startswith("https://"):
        raise RuntimeError("Unexpected artifact transport")
    # Do not forward the GitHub credential to blob storage.
    with urllib.request.urlopen(target, timeout=120) as response:
        return response.read()


def request(path, method="GET", data=None):
    token = credential_token()
    req = urllib.request.Request(
        "https://api.github.com/" + path,
        method=method,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Wonderland-Step11"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            body = response.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"GitHub {method} failed with HTTP {error.code}") from None


if __name__ == "__main__":
    repo = request("repos/" + REPOSITORY)
    print(json.dumps({key: repo.get(key) for key in
                      ["full_name", "private", "default_branch", "size", "permissions"]}, indent=2))
