"""Generate disposable TLS test material; never a cloud credential or application password."""

import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

directory = Path(__file__).resolve().parents[1] / ".local/deployment/db-bootstrap-test"
certs = directory / "certs"
certs.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc)


def make_ca(name):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    return key, cert


ca_key, ca = make_ca("Disposable Step10B test CA")
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "postgres")]))
        .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=2))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("postgres")]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256()))
(certs / "ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
(certs / "server.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
(certs / "server.key").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
_, untrusted = make_ca("Untrusted test CA")
(certs / "untrusted-ca.pem").write_bytes(untrusted.public_bytes(serialization.Encoding.PEM))
(directory / "password").write_text(secrets.token_urlsafe(48))
print("Disposable isolated-test material prepared under ignored .local; no values displayed.")
