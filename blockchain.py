import hashlib
import json
import hashlib
import logging
import unittest
import requests  # type: ignore
import ecdsa # type: ignore
import base58 # type: ignore
from time import time
from uuid import uuid4
from flask import Flask, jsonify, request  # type: ignore
from flask_limiter import Limiter # type: ignore
from flask_limiter.util import get_remote_address # type: ignore
from cryptography.hazmat.primitives.asymmetric import rsa # type: ignore
from cryptography.hazmat.primitives import serialization # type: ignore

# welcome back guys :)

# Konfigurasi logging
logging.basicConfig(filename='blockchain.log', level=logging.INFO)

# Exceptions
class InsufficientFundsError(Exception):
    pass

class InvalidTransactionError(Exception):
    pass

# Fungsi untuk membuat tanda tangan
def create_signature(private_key, message):
    sk = ecdsa.SigningKey.from_string(private_key.encode(), curve=ecdsa.SECP256k1)
    signature = sk.sign(message.encode())
    return base58.b58encode(signature).decode()

# Fungsi untuk memverifikasi tanda tangan
def verify_signature(public_key, message, signature):
    vk = ecdsa.VerifyingKey.from_string(public_key.encode(), curve=ecdsa.SECP256k1)
    try:
        vk.verify(base58.b58decode(signature.encode()), message.encode())
        return True
    except ecdsa.BadSignatureError:
        return False

class KeyManager:
    @staticmethod
    def generate_key_pair():
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        public_key = private_key.public_key()
        return private_key, public_key

    @staticmethod
    def serialize_public_key(public_key):
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    
class SmartContract:
    def __init__(self, code):
        self.code = code

    def execute(self, blockchain, transaction):
        # Ini adalah implementasi yang sangat sederhana dan tidak aman coy
        local_vars = {'blockchain': blockchain, 'transaction': transaction}
        exec(self.code, {}, local_vars)
        return local_vars.get('result', None)
    
class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.balances = {}  # Menyimpan saldo pengguna
        self.node_identifier = '0xf80001110110' # alamat miner 0xf itu code ethereum ini example aja
        self.initial_supply = 21000000  # Misalkan supply maksimum
        self.supply = 1000  # Supply saat ini
        self.mempool = []
        self.pruned_blocks = {}
        self.contracts = {}

        # Buat genesis block
        self.new_block(previous_hash='1', proof=100)
        # Inisialisasi saldo miner dengan reward dari genesis block
        self.balances[self.node_identifier] = 10
        # Inisialisasi saldo awal untuk pengguna tambahan
        self.balances['user1'] = 1000
        self.balances['user2'] = 500

    def add_to_mempool(self, transaction):
        self.mempool.append(transaction)

    def get_transactions_from_mempool(self, max_transactions=10):
        transactions = self.mempool[:max_transactions]
        self.mempool = self.mempool[max_transactions:]
        return transactions
    
    # Halving genesis block
    def get_block_reward(self):
        halving_interval = 210000
        reward = 50
        halvings = len(self.chain) / halving_interval
        return reward / (2 ** halvings)

    def prune(self, block_height):
        if block_height <= len(self.chain) - 100:  # Simpan 100 blok terakhir
            pruned_block = self.chain.pop(0)
            self.pruned_blocks[pruned_block['index']] = self.hash(pruned_block)
            return True
        return False
    
    def deploy_contract(self, address, code):
        self.contracts[address] = SmartContract(code)

    def execute_contract(self, address, transaction):
        if address in self.contracts:
            return self.contracts[address].execute(self, transaction)
        return None
    
    def new_block(self, proof, previous_hash=None):
        # transaksi Coinbase sebelum transaksi yang ada
        transactions = [
            {
                'sender': '0',  # Penanda untuk transaksi Coinbase
                'recipient': self.node_identifier,  # Alamat miner
                'amount': 10,   # Hadiah blok, misalnya 10 unit cryptocurrency
            }
        ] + self.current_transactions

        transactions = self.get_transactions_from_mempool() + self.current_transactions
    
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
            'merkle_root': self.merkle_root(transactions)
        }

        self.current_transactions = []
        self.chain.append(block)

        self.supply += 10
        if self.supply > self.initial_supply:
            raise Exception("Total supply exceeded the maximum limit")

        # Update balances

        for transaction in transactions:
            sender, recipient, amount = transaction['sender'], transaction['recipient'], transaction['amount']
            if sender != '0':
                if sender not in self.balances or self.balances[sender] < amount:
                    raise InsufficientFundsError(f"Sender {sender} has insufficient funds")
                self.balances[sender] -= amount
            if recipient not in self.balances:
                self.balances[recipient] = 0
            self.balances[recipient] += amount

        self.prune(len(self.chain) - 1)
        return block

    def new_transaction(self, sender, recipient, amount, private_key, signature):
        if sender != '0' and (sender not in self.balances or self.balances[sender] < amount):
            raise InsufficientFundsError("Insufficient funds")
        
        message = f'{sender}{recipient}{amount}'
        if not verify_signature(sender, message, signature):
            raise InvalidSignatureError("Invalid signature") # type: ignore

        transaction = {
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
            'timestamp': time(),
            'nonce': uuid4().hex
        }

        if not self.validate_transaction(transaction):
            raise InvalidTransactionError("Invalid transaction")

        self.current_transactions.append(transaction)
        logging.info(f"New transaction: {transaction}")
        return self.last_block['index'] + 1

    def validate_transaction(self, transaction):
        return all(k in transaction for k in ["sender", "recipient", "amount"]) and \
               isinstance(transaction['amount'], (int, float)) and transaction['amount'] > 0 and \
               transaction['sender'] != transaction['recipient']

    def validate_block(self, block):
        return block['index'] == len(self.chain) + 1 and \
               block['previous_hash'] == self.hash(self.chain[-1]) and \
               self.valid_proof(self.chain[-1]['proof'], block['proof'])
    
    @staticmethod
    def merkle_root(transactions):
        if not transactions:
            return hashlib.sha256(b'').hexdigest()
        if len(transactions) == 1:
            return hashlib.sha256(json.dumps(transactions[0]).encode()).hexdigest()
        mid = len(transactions) // 2
        left = Blockchain.merkle_root(transactions[:mid])
        right = Blockchain.merkle_root(transactions[mid:])
        return hashlib.sha256(f'{left}{right}'.encode()).hexdigest()

    def initialize_balances(self):
        self.new_transaction(sender='0', recipient='user1', amount=1000, private_key='', signature='')
        self.new_transaction(sender='0', recipient='user2', amount=500, private_key='', signature='')
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
        while not self.valid_proof(last_proof, proof):
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

# Flask API
app = Flask(__name__)
limiter = Limiter(app, key_func=get_remote_address)
node_identifier = str(uuid4()).replace('-', '')
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    last_proof = blockchain.last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=10,
        private_key='',
        signature=''
    )

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
@limiter.limit("5 per minute")
def new_transaction():
    try:
        values = request.get_json()
        required = ['sender', 'recipient', 'amount', 'private_key', 'signature']
        if not all(k in values for k in required):
            return 'Missing values', 400

        index = blockchain.new_transaction(
            values['sender'],
            values['recipient'],
            values['amount'],
            values['private_key'],
            values['signature']
        )

        response = {'message': f'Transaction will be added to Block {index}'}
        return jsonify(response), 201

    except (InsufficientFundsError, InvalidTransactionError, InvalidSignatureError) as e: # type: ignore
        return str(e), 400
    except Exception as e:
        logging.error(f"Error in new_transaction: {str(e)}")
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

@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    balance = blockchain.balances.get(address, 0)
    return jsonify({'address': address, 'balance': balance}), 200

if __name__ == '__main__':
    from argparse import ArgumentParser

    blockchain.initialize_balances()

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()

    app.run(host='0.0.0.0', port=args.port)

# Unit Tests
class TestBlockchain(unittest.TestCase):
    def setUp(self):
        self.blockchain = Blockchain()

    def test_new_block(self):
        initial_length = len(self.blockchain.chain)
        self.blockchain.new_block(proof=100)
        self.assertEqual(len(self.blockchain.chain), initial_length + 1)