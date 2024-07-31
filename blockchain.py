import logging
import binascii
import ecdsa # type: ignore
import hashlib
import json
from time import time
from uuid import uuid4
from key_utils import verify_signature
from cryptography.hazmat.primitives.asymmetric import rsa # type: ignore
from cryptography.hazmat.primitives import serialization # type: ignore
from flask import Flask, jsonify, request # type: ignore
from flask_limiter import Limiter # type: ignore
from flask_limiter.util import get_remote_address # type: ignore
import requests # type: ignore

# Konfigurasi logging
logging.basicConfig(filename='blockchain.log', level=logging.INFO)

# Exceptions
class InsufficientFundsError(Exception):
    pass

class InvalidTransactionError(Exception):
    pass

class InvalidSignatureError(Exception):
    pass

class SmartContract:
    def __init__(self, code):
        self.code = code

    def execute(self, blockchain, transaction):
        # Ini adalah implementasi yang sangat sederhana dan tidak aman
        local_vars = {'blockchain': blockchain, 'transaction': transaction}
        exec(self.code, {}, local_vars)
        return local_vars.get('result', None)

class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.balances = {}  # Menyimpan saldo pengguna
        self.public_keys = {}  # Menyimpan kunci publik pengguna
        self.node_identifier = '0xf80001110110'  # alamat miner
        self.initial_supply = 21000000  # Misalkan supply maksimum
        self.supply = 1000  # Supply saat ini
        self.mempool = []
        self.pruned_blocks = {}
        self.contracts = {}
        self.current_block = None
        self.create_new_block(previous_hash='1', proof=100)
        self.max_transactions_per_block = 5

        # Buat genesis block
        self.new_block(previous_hash='1', proof=100)
        # Inisialisasi saldo miner dengan reward dari genesis block
        self.balances[self.node_identifier] = 10
        # Inisialisasi saldo awal untuk pengguna tambahan
        self.balances['user1'] = 1000
        self.balances['user2'] = 500

    def prune(self, index):
        if index < len(self.chain):
            self.pruned_blocks.update({block['index']: block for block in self.chain[:index]})
            self.chain = self.chain[index:]
            logging.info(f"Pruned blockchain to index {index}")

    def create_new_block(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': [],
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
            'merkle_root': None
        }
        self.current_block = block
        return block
    
    def new_block(self, proof, previous_hash=None):
        if self.current_block is None or 'transactions' not in self.current_block:
            self.create_new_block(proof, previous_hash)
    
        # Finalisasi blok saat ini
        self.current_block['merkle_root'] = self.merkle_root(self.current_block['transactions'])
        self.chain.append(self.current_block)

        transactions = [
            {
                'sender': '0',  # Penanda untuk transaksi Coinbase
                'recipient': self.node_identifier,  # Alamat miner
                'amount': 10,   # Hadiah blok, misalnya 10 unit cryptocurrency
            }
        ] + self.current_transactions

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

        self.prune(len(self.chain) - 1) # Menyimpan 1000 blok terakhir
        return block    
    
    def new_transaction(self, sender, recipient, amount, signature, public_key=None, fee=5):
        amount = int(amount)
        fee = int(fee) 

        if sender != '0':  
            total_amount = amount + fee
            if sender not in self.balances or self.balances[sender] < total_amount:
                raise InsufficientFundsError(f"Sender {sender} has insufficient funds")
            self.balances[sender] -= total_amount

        # Simpan kunci publik jika belum ada
        if sender not in self.public_keys and public_key:
            self.public_keys[sender] = public_key

        if recipient not in self.balances:
            self.balances[recipient] = 0
        self.balances[recipient] += amount

        self.balances[self.node_identifier] += fee
               
        # Tambahkan transaksi ke daftar transaksi saat ini
        # self.current_transactions.append({
        #     'sender': sender,
        #     'recipient': recipient,
        #     'amount': amount
        # })

        transaction = {
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
            'fee': fee,
            'timestamp': time(),
            'nonce': uuid4().hex
        }

        if not self.validate_transaction(transaction):
            raise InvalidTransactionError("Invalid transaction")
        
        if self.current_block and len(self.current_block['transactions']) < self.max_transactions_per_block:
            self.current_block['transactions'].append(transaction)
        else:
            self.mempool.append(transaction)

        self.current_transactions.append(transaction)
        logging.info(f"Transaction added: sender={sender}, recipient={recipient}, amount={amount}")
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
        self.new_transaction(sender='0', recipient='user1', amount=1000, signature='') 
        self.new_transaction(sender='0', recipient='user2', amount=500, signature='') 
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

    def register_node(self, address):
        self.nodes.add(address)

    def consensus_algorithm(self):
        replaced = self.resolve_conflicts()
        if replaced:
            logging.info("Our chain was replaced")
        else:
            logging.info("Our chain is authoritative")