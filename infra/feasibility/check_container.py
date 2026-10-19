"""Run through stdin inside the probe image to check its restricted runtime."""

import errno
import json
import os
import threading
import time
import urllib.error
import urllib.request

import uvicorn

assert os.getuid() == 10001
try:
    with open("/app/read-only-check", "w"):
        pass
except OSError as error:
    assert error.errno == errno.EROFS
else:
    raise AssertionError("Root filesystem is writable")

server = uvicorn.Server(uvicorn.Config("main:app", host="127.0.0.1", port=8000, log_level="error"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
try:
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started
    with urllib.request.urlopen("http://127.0.0.1:8000/smoke/health", timeout=5) as response:
        body = json.load(response)
        assert response.status == 200 and body["mode"] == "MOCK" and body["status"] == "ok"
    for path in ("/api/v1/bookings", "/admin", "/docs"):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000" + path, timeout=5)
        except urllib.error.HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError(f"Unexpected route exposed: {path}")
    print(
        json.dumps(
            {
                "uid": os.getuid(),
                "read_only_root": True,
                "health": body,
                "application_routes": "404",
            }
        )
    )
finally:
    server.should_exit = True
    thread.join(timeout=5)
