import ecdsa  # type: ignore
import binascii

def generate_keys():
    sk = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    private_key = binascii.hexlify(sk.to_string()).decode()
    public_key = binascii.hexlify(sk.get_verifying_key().to_string()).decode()
    return private_key, public_key

def create_signature(private_key, message):
    sk = ecdsa.SigningKey.from_string(binascii.unhexlify(private_key), curve=ecdsa.SECP256k1)
    signature = sk.sign(message.encode())
    return binascii.hexlify(signature).decode()

def verify_signature(public_key, message, signature):
    try:
        vk = ecdsa.VerifyingKey.from_string(binascii.unhexlify(public_key), curve=ecdsa.SECP256k1)
        return vk.verify(binascii.unhexlify(signature), message.encode())
    except Exception as e:
        print(f"Verification error: {e}")
        return False

if __name__ == "__main__":
   
    private_key, public_key = generate_keys()
    print("Private Key:", private_key)
    print("Public Key:", public_key)

    sender = "user1"
    recipient = "user2"
    amount = 50
    message = f"{sender}{recipient}{amount}"

    signature = create_signature(private_key, message)
    print("Signature:", signature)

    if verify_signature(public_key, message, signature):
        print("Signature is valid")
    else:
        print("Invalid signature")
