import hashlib
import json
from time import time
from uuid import uuid4
from flask import Flask, jsonify, request  # type: ignore
from blockchain import Blockchain, InvalidSignatureError, InsufficientFundsError

app = Flask(__name__)

# Hasilkan alamat unik global untuk node ini
node_identifier = str(uuid4()).replace('-', '')

# Buat instance Blockchain
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    last_proof = blockchain.last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # Penambang menerima hadiah karena menambang blok tersebut
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
        private_key='',
        signature=''
    )

    # Forge the new Block by adding it to the chain
    previous_hash = blockchain.hash(blockchain.last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    try:
        values = request.get_json()
        print("Received values:", values)  # Debugging statement

        required = ['sender', 'recipient', 'amount', 'private_key', 'signature']
        if not all(k in values for k in required):
            print("Missing values in request")  # Debugging statement
            return 'Missing values', 400

        # Tambah transaksi
        index = blockchain.new_transaction(
            values['sender'],
            values['recipient'],
            values['amount'],
            values['private_key'],
            values['signature']
        )

        # Ambil saldo terkini untuk pengirim setelah transaksi
        sender_balance = blockchain.balances.get(values['sender'], 0)

        response = {
            'message': f'Transaction will be added to Block {index}',
            'total_transaction_amount': values['amount'],
            'remaining_balance': sender_balance
        }
        return jsonify(response), 201

    except InvalidSignatureError as e:
        print("Invalid signature:", str(e))  # Debugging statement
        return 'Invalid signature', 400
    except InsufficientFundsError as e:
        print("Insufficient funds:", str(e))  # Debugging statement
        return 'Insufficient funds', 400
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
    response = {
        'address': address,
        'balance': balance
    }
    return jsonify(response), 200

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)
