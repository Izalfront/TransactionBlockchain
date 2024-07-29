import hashlib
import json
from time import time
from uuid import uuid4
import logging
from flask import Flask, jsonify, request # type: ignore
from blockchain import Blockchain
from key_utils import verify_signature

app = Flask(__name__)

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

        # Menggunakan nilai dummy untuk private_key dan signature jika tidak digunakan dalam transaksi
        # private_key = 'dummy_private_key'  
        # signature = 'dummy_signature'  

        # Menambahkan transaksi baru
        blockchain.new_transaction(
            sender="0",
            recipient=node_identifier,
            amount=1,
            # private_key=private_key,  # Sesuaikan jika perlu
            # signature=signature       # Sesuaikan jika perlu
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
        print("Received values:", values)  # Debugging statement

        required = ['sender', 'recipient', 'amount', 'public_key', 'signature'] #'public_key', 'signature'
        if not all(k in values for k in required):
            print("Missing values in request")  # Debugging statement
            return 'Missing values', 400

        # Verify the signature
        # message = values['sender'] + values['recipient'] + str(values['amount'])
        # if not verify_signature(values['public_key'], message, values['signature']):
        #     return 'Invalid signature', 400

        # Add transaction
        index = blockchain.new_transaction(
            values['sender'],
            values['recipient'],
            values['amount'],
            values['public_key'],
            values['private_key'],
            values['signature']
        )

        # Dapatkan saldo terkini untuk pengirim setelah transaksi
        sender_balance = blockchain.balances.get(values['sender'], 0)

        response = {'message': f'Transaction will be added to Block {index}',
                    'total_transaction_amount': values['amount'],
                    'remaining_balance': sender_balance
                   }
        return jsonify(response), 201

    except Exception as e:
        print("Error:", str(e))  # Debugging statement
        return str(e), 500

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.nodes.add(node)

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
    public_key = blockchain.public_keys.get(address, 'N/A')
    response = {
        'address': address,
        'balance': balance,
        'public_key': public_key
    }
    return jsonify(response), 200

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=5000)