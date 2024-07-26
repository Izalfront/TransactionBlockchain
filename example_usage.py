from key_utils import generate_keys, create_signature, verify_signature

# Generate keys
private_key, public_key = generate_keys()
print("Private Key:", private_key)
print("Public Key:", public_key)

# Prepare message
message = "user1user212"  # Gabungkan pengirim, penerima, dan jumlah

# Create signature
signature = create_signature(private_key, message)
print("Signature:", signature)

# Verify signature
is_valid = verify_signature(public_key, message, signature)
print("Is the signature valid?", is_valid)