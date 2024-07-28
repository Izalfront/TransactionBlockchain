import ecdsa # type: ignore
import binascii

def generate_key_pair():
    sk = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)  # Private key
    vk = sk.get_verifying_key()  # Public key
    private_key = binascii.hexlify(sk.to_string()).decode()
    public_key = binascii.hexlify(vk.to_string()).decode()
    return private_key, public_key

# Generate keys
private_key, public_key = generate_key_pair()
print(f"Private Key: {private_key}")
print(f"Public Key: {public_key}")
