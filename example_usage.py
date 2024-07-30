from ecdsa import SigningKey, SECP256k1 # type: ignore
import hashlib

# Generate private key
private_key = SigningKey.generate(curve=SECP256k1)
private_key_hex = private_key.to_string().hex()

# Generate public key
public_key = private_key.get_verifying_key()
public_key_hex = public_key.to_string().hex()

# Function to sign a message
def sign_message(private_key, message):
    message_hash = hashlib.sha256(message.encode()).hexdigest()
    signature = private_key.sign(message_hash.encode())
    return signature.hex()

# Example usage
message = 'Sample message'
signature = sign_message(private_key, message)

print(f'Private Key: {private_key_hex}')
print(f'Public Key: {public_key_hex}')
print(f'Signature: {signature}')