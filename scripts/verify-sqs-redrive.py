"""Exercise SQS redrive using two isolated disposable queues; never receives application queues."""

import json
import os
import time
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config


def main():
    root = Path(__file__).resolve().parents[1]
    os.environ["AWS_CONFIG_FILE"] = str(root / ".local/aws/config")
    os.environ["AWS_LOGIN_CACHE_DIRECTORY"] = str(root / ".local/aws/login/cache")
    client = boto3.Session(profile_name="wonderland-dev", region_name="ap-south-1").client(
        "sqs",
        config=Config(
            connect_timeout=3, read_timeout=8, retries={"max_attempts": 2, "mode": "standard"}
        ),
    )
    name = "wonderland-step05-test-" + uuid4().hex[:12]
    created = []
    try:
        dlq = client.create_queue(
            QueueName=name + "-dlq",
            Attributes={"SqsManagedSseEnabled": "true", "MessageRetentionPeriod": "60"},
            tags={"Project": "Wonderland", "Purpose": "DisposableStep05Test"},
        )["QueueUrl"]
        created.append(dlq)
        arn = client.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"][
            "QueueArn"
        ]
        source = client.create_queue(
            QueueName=name,
            Attributes={
                "SqsManagedSseEnabled": "true",
                "VisibilityTimeout": "1",
                "MessageRetentionPeriod": "60",
                "RedrivePolicy": json.dumps({"deadLetterTargetArn": arn, "maxReceiveCount": 2}),
            },
            tags={"Project": "Wonderland", "Purpose": "DisposableStep05Test"},
        )["QueueUrl"]
        created.append(source)
        client.send_message(QueueUrl=source, MessageBody="step05-isolated-redrive-test")
        deadline = time.monotonic() + 45
        receives = 0
        while time.monotonic() < deadline:
            messages = client.receive_message(
                QueueUrl=source, MaxNumberOfMessages=1, WaitTimeSeconds=1, VisibilityTimeout=1
            ).get("Messages", [])
            receives += len(messages)  # Intentionally no acknowledgement.
            failed = client.receive_message(QueueUrl=dlq, WaitTimeSeconds=1).get("Messages", [])
            if failed:
                assert failed[0]["Body"] == "step05-isolated-redrive-test"
                print(f"PASS: isolated message moved to its DLQ after {receives} receives.")
                return
            time.sleep(1)
        raise SystemExit("Redrive was not observed before the bounded deadline.")
    finally:
        for url in reversed(created):
            assert url.rsplit("/", 1)[-1] in {name, name + "-dlq"}
            client.delete_queue(QueueUrl=url)
        print("Disposable test queues removed; application queues were untouched.")


if __name__ == "__main__":
    main()
