#!/usr/bin/env python3
"""
Generate Ed25519 key pair for TAP (Trusted Agent Protocol) signing.

This script generates a new Ed25519 key pair and saves them to the config/keys directory.
The private key is used by the agent to sign requests.
The public key is used by merchants to verify signatures.

Usage:
    python scripts/generate_keys.py
"""

import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.backends import default_backend


def generate_ed25519_keys(output_dir: Path) -> tuple[str, str]:
    """
    Generate Ed25519 key pair and save to files.

    Returns:
        Tuple of (private_key_path, public_key_path)
    """
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate key pair
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Save keys
    private_path = output_dir / "agent_private.pem"
    public_path = output_dir / "agent_public.pem"

    with open(private_path, "wb") as f:
        f.write(private_pem)
    os.chmod(private_path, 0o600)  # Restrict permissions

    with open(public_path, "wb") as f:
        f.write(public_pem)

    return str(private_path), str(public_path)


def generate_rsa_keys(output_dir: Path, key_size: int = 2048) -> tuple[str, str]:
    """
    Generate RSA key pair for JWT signing (used in MCP token generation).

    Returns:
        Tuple of (private_key_path, public_key_path)
    """
    from cryptography.hazmat.primitives.asymmetric import rsa

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Save keys
    private_path = output_dir / "jwt_signing_private.pem"
    public_path = output_dir / "jwt_signing_public.pem"

    with open(private_path, "wb") as f:
        f.write(private_pem)
    os.chmod(private_path, 0o600)

    with open(public_path, "wb") as f:
        f.write(public_pem)

    return str(private_path), str(public_path)


def main():
    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    keys_dir = project_root / "config" / "keys"

    print("=" * 60)
    print("TAP Key Generator")
    print("=" * 60)

    # Check if keys already exist
    if (keys_dir / "agent_private.pem").exists():
        response = input("\nKeys already exist. Overwrite? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    # Generate Ed25519 keys for TAP signing
    print("\n1. Generating Ed25519 key pair for TAP signing...")
    private_path, public_path = generate_ed25519_keys(keys_dir)
    print(f"   Private key: {private_path}")
    print(f"   Public key:  {public_path}")

    # Generate RSA keys for JWT signing
    print("\n2. Generating RSA key pair for JWT signing...")
    jwt_private, jwt_public = generate_rsa_keys(keys_dir)
    print(f"   Private key: {jwt_private}")
    print(f"   Public key:  {jwt_public}")

    # Print public key for registration
    print("\n" + "=" * 60)
    print("SETUP INSTRUCTIONS")
    print("=" * 60)

    print("\n1. Copy the following public key to your .env file as TAP_AGENT_PUBLIC_KEY:")
    with open(public_path, "r") as f:
        print(f.read())

    print("\n2. Update your .env file:")
    print(f"   TAP_PRIVATE_KEY_PATH={private_path}")
    print(f"   TAP_AGENT_PUBLIC_KEY_PATH={public_path}")

    print("\n3. For Visa MCP integration, provide the JWT signing key:")
    print(f"   USER_SIGNING_PRIVATE_KEY_PATH={jwt_private}")

    print("\n4. Register the public key with Visa's Agent Registry")
    print("   (Contact Visa Developer Support for registration)")

    print("\n" + "=" * 60)
    print("Keys generated successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
