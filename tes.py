from web3 import Web3, HTTPProvider

# Inisialisasi koneksi Web3
w3 = Web3(HTTPProvider('http://127.0.0.1:8545'))

# Periksa apakah koneksi berhasil
if w3.is_connected():
    try:
        # Akses block number dari modul eth
        block_number = w3.eth.block_number  # Gunakan block_number alih-alih blockNumber
        print(f"Current block number: {block_number}")
    except Exception as e:
        print(f"Error: {e}")
else:
    print("Failed to connect to the Ethereum node.")

tx_hash = w3.eth.send_transaction({
    'from': w3.eth.accounts[0],
    'to': w3.eth.accounts[1],
    'value': w3.to_wei(1, 'ether')
})
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
print(f"Transaction completed in block: {receipt.blockNumber}")
