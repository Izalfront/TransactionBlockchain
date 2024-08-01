import hashlib
import json
from time import time
from uuid import uuid4
import logging
from flask import Flask, jsonify, request # type: ignore
from flask_limiter import Limiter # type: ignore
from flask_limiter.util import get_remote_address # type: ignore
from blockchain import Blockchain
from key_utils import verify_signature

# Konfigurasi logging
logging.basicConfig(filename='blockchain.log', level=logging.INFO)

# Exceptions
class InsufficientFundsError(Exception):
    pass

class InvalidTransactionError(Exception):
    pass

class InvalidSignatureError(Exception):
    pass

# Setup Flask app
app = Flask(__name__)
limiter = Limiter(get_remote_address, app=app)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    logging.info('Mining endpoint called')
    try:
        # Mendapatkan blok terakhir dan proof terakhir
        last_block = blockchain.last_block
        last_proof = last_block['proof']
        
        # Menyelesaikan proof of work untuk blok baru
        proof = blockchain.proof_of_work(last_proof)

        # Menambahkan transaksi baru (reward untuk mining)
        blockchain.new_transaction(
            sender="0",
            recipient=node_identifier,
            amount=1,
            signature='',
            public_key=''
        )

        # Membuat blok baru
        previous_hash = blockchain.hash(last_block)
        block = blockchain.new_block(proof, previous_hash)

        # Membuat respons
        response = {
            'message': "New Block Forged",
            'index': block['index'],
            'transactions': block['transactions'],
            'proof': block['proof'],
            'previous_hash': block['previous_hash'],
        }
        logging.info(f'Mining successful: {response}')
        return jsonify(response), 200
    except Exception as e:
        logging.error(f'Error during mining: {e}')
        return jsonify({'message': 'Internal server error'}), 500

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    try:
        values = request.get_json()
        logging.info(f"Received values: {values}")

        required = ['sender', 'recipient', 'amount', 'signature', 'public_key']
        if not all(k in values for k in required):
            logging.warning("Missing values in request")
            return 'Missing values', 400
        
        # # Siapkan pesan untuk validasi tanda tangan
        # message = f"{values['sender']}{values['recipient']}{values['amount']}"
        # logging.info(f"Message to verify: {message}")
        # logging.info(f"Public key: {values['public_key']}")
        # logging.info(f"Signature: {values['signature']}")
                
        # # Validasi tanda tangan
        # is_valid = verify_signature(values['public_key'], message, values['signature'])
        # logging.info(f"Signature validation result: {is_valid}")
        
        # if not is_valid:
        #     logging.error("Invalid signature")
        #     return 'Invalid signature', 400
        
        # Tambah transaksi
        index = blockchain.new_transaction(
            sender=values['sender'],
            recipient=values['recipient'],
            amount=int(values['amount']),
            signature=values['signature'],
            public_key=values['public_key'],
            fee=values.get('fee', 5)  # default fee is 5
        )

        # Dapatkan saldo terkini untuk pengirim setelah transaksi
        sender_balance = blockchain.balances.get(values['sender'], 0)

        response = {
            'message': f'Transaction will be added to Block {index}',
            'total_transaction_amount': values['amount'],
            'remaining_balance': sender_balance
        }
        return jsonify(response), 201

    except InvalidTransactionError  as e:
        logging.error(f"Invalid transaction: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except InsufficientFundsError as e:
        logging.error(f"Insufficient funds: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in new_transaction: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/balances', methods=['GET'])
def balances():
    response = blockchain.balances
    return jsonify(response), 200

@app.route('/mempool', methods=['GET'])
def get_mempool():
    response = blockchain.mempool
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200

@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    balance = blockchain.balances.get(address, 0)
    public_key = blockchain.public_keys.get(address, 'Not found')
    response = {
        'address': address,
        'balance': balance,
        'public_key': public_key
    }
    logging.info(f"Balance check for {address}: {response}")
    return jsonify(response), 200

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port, debug=True)
