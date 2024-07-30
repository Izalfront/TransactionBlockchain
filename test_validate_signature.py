from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError # type: ignore

# Generate a new signing key (private key)
signing_key = SigningKey.generate(curve=SECP256k1)
verifying_key = signing_key.get_verifying_key()

# Message to sign
message = b"Hello, blockchain!"

# Sign the message
signature = signing_key.sign(message)

# Verify the signature
try:
    assert verifying_key.verify(signature, message)
    print("Signature is valid!")
except BadSignatureError:
    print("Signature is invalid!")

# Print keys
print("Private key:", signing_key.to_string().hex())
print("Public key:", verifying_key.to_string().hex())
