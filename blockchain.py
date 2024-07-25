import hashlib
import json
from time import time
from uuid import uuid4
from flask import Flask, jsonify, request  # type: ignore
import requests  # type: ignore

class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.balances = {}  # Menyimpan saldo pengguna
        self.node_identifier = '0xf80001110110'  # Ganti dengan alamat miner
        self.initial_supply = 21000000  # Misalkan supply maksimum
        self.supply = 1000  # Supply saat ini

        # Buat genesis block
        self.new_block(previous_hash='1', proof=100)
        # Inisialisasi saldo miner dengan reward dari genesis block
        self.balances[self.node_identifier] = 10
        # Inisialisasi saldo awal untuk pengguna tambahan
        self.balances['user1'] = 1000
        self.balances['user2'] = 500

    def new_block(self, proof, previous_hash=None):
        # Tambahkan transaksi Coinbase sebelum transaksi yang ada
        transactions = [
            {
                'sender': '0',  # Penanda untuk transaksi Coinbase
                'recipient': self.node_identifier,  # Alamat miner
                'amount': 10,  # Hadiah blok, misalnya 10 unit cryptocurrency
            }
        ] + self.current_transactions

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        self.current_transactions = []
        self.chain.append(block)

        # Update supply
        self.supply += 10  # Tambah sesuai dengan hadiah blok

        if self.supply > self.initial_supply:
            raise Exception("Total supply exceeded the maximum limit")

        # Update balances
        for transaction in transactions:
            sender = transaction['sender']
            recipient = transaction['recipient']
            amount = transaction['amount']

            if sender != '0':  # Bukan transaksi Coinbase
                if sender not in self.balances:
                    self.balances[sender] = 0
                if self.balances[sender] < amount:
                    raise Exception(f"Sender {sender} has insufficient funds")
                self.balances[sender] -= amount

            if recipient not in self.balances:
                self.balances[recipient] = 0
            self.balances[recipient] += amount

        return block

    def new_transaction(self, sender, recipient, amount):
        transaction = {
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        }

        # Periksa saldo sender
        if sender != '0' and (sender not in self.balances or self.balances[sender] < amount):
            raise Exception("Insufficient funds")

         # Tambahkan transaksi ke daftar transaksi saat ini
        self.current_transactions.append(transaction)
        return self.last_block['index'] + 1

    def initialize_balances(self):
        # Menetapkan saldo awal untuk beberapa pengguna
        self.new_transaction(sender='0', recipient='user1', amount=1000)
        self.new_transaction(sender='0', recipient='user2', amount=500)
        # Tambang blok pertama untuk memproses transaksi ini
        last_proof = self.last_block['proof']
        proof = self.proof_of_work(last_proof)
        self.new_block(proof)
        
    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(last_block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        neighbours = self.nodes
        new_chain = None

        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False

# Flask API untuk berinteraksi dengan blockchain
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    last_proof = blockchain.last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # Miner receives reward for mining the block
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=10,
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

        required = ['sender', 'recipient', 'amount']
        if not all(k in values for k in required):
            print("Missing values in request")  # Debugging statement
            return 'Missing values', 400

        # Tambahkan transaksi
        index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

        # Tambang blok baru untuk memproses transaksi
        last_proof = blockchain.last_block['proof']
        proof = blockchain.proof_of_work(last_proof)
        block = blockchain.new_block(proof)

        response = {
            'message': f'Transaction will be added to Block {index}',
            'index': block['index']
        }
        return jsonify(response), 201

    except Exception as e:
        print("Error:", str(e))  # Debugging statement
        return 'Internal Server Error', 500

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

if __name__ == '__main__':
    from argparse import ArgumentParser
    # Instantiate the Blockchain
    blockchain = Blockchain()

    # Inisialisasi saldo awal
    blockchain.initialize_balances()

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)
