import logging
import binascii
import ecdsa # type: ignore
import hashlib
import time
import random
import json
from web3 import Web3
from time import time
from uuid import uuid4
from key_utils import verify_signature
from key_utils import generate_keys
import requests # type: ignore
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

class ConsensusError(Exception):
    pass

# class SmartContract:
#     def __init__(self, code):
#         self.code = code

#     def execute(self, blockchain, transaction):
#         if not self.validate_code(self.code):
#             raise InvalidTransactionError("Invalid smart contract code")

#         safe_globals = {
#             'blockchain': blockchain,
#             'transaction': transaction,
#             'math': __import__('math'),
#         }
#         safe_locals = {}

#         try:
#             exec(self.code, safe_globals, safe_locals)
#             return safe_locals.get('result', None)
#         except Exception as e:
#             logging.error(f"Smart contract execution failed: {e}")
#             return None

#     def validate_code(self, code):
#         restricted_keywords = ['import', 'exec', 'eval', 'open', 'os', 'sys', 'subprocess']
#         for keyword in restricted_keywords:
#             if keyword in code:
#                 logging.error(f"Smart contract code contains restricted keyword: {keyword}")
#                 return False
#         return True

class SmartContractConnection:
    def __init__(self, contract_address, abi):
        self.w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))
        self.contract = self.w3.eth.contract(address=contract_address, abi=abi)

    def call_function(self, function_name, *args):
        function = self.contract.functions[function_name]
        try:
            result = function(*args).call()
            return result
        except Exception as e:
            logging.error(f"Failed to call function {function_name}: {e}")
            return None

    def send_transaction(self, function_name, sender_address, sender_private_key, *args):
        function = self.contract.functions[function_name]
        try:
            transaction = function(*args).buildTransaction({
                'from': sender_address,
                'nonce': self.w3.eth.getTransactionCount(sender_address),
            })
            signed_txn = self.w3.eth.account.signTransaction(transaction, sender_private_key)
            tx_hash = self.w3.eth.sendRawTransaction(signed_txn.rawTransaction)
            receipt = self.w3.eth.waitForTransactionReceipt(tx_hash)
            return receipt
        except Exception as e:
            logging.error(f"Failed to send transaction {function_name}: {e}")
            return None

class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.balances = {}  
        self.public_keys = {}  
        self.node_identifier = '0xf80001110110'  
        self.initial_supply = 21000000  
        self.supply = 1000  
        self.mempool = []
        self.pruned_blocks = {}
        self.contracts = {}
        self.current_block = None
        self.last_index = 0     
        self.max_transactions_per_block = 5   
        self.create_genesis_block()

        # Inisialisasi saldo miner dengan reward dari genesis block
        self.balances[self.node_identifier] = 5
        # Inisialisasi saldo awal untuk pengguna tambahan
        self.balances['user1'] = 10000
        self.balances['user2'] = 50

    def prune(self, index):
        if index > 1:
            self.pruned_blocks.update({block['index']: block for block in self.chain[:index-1]})
            self.chain = self.chain[index-1:]
            logging.info(f"Pruned blockchain to index {index}")
        else:
            logging.warning("Cannot prune to index less than or equal to 1")

    def create_genesis_block(self):
        if not self.chain:
            genesis_block = self.new_block(proof=100, previous_hash='1', is_genesis=True)
            logging.info("Genesis block created")

    def new_block(self, proof, previous_hash=None, is_genesis=False):
        self.last_index += 1  # Increment indeks

        block = {
            'index': self.last_index,
            'timestamp': time(),
            'transactions': [],
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
    
        if not is_genesis:
            # Pindahkan transaksi dari mempool ke blok baru
            while len(block['transactions']) < self.max_transactions_per_block and self.mempool:
                block['transactions'].append(self.mempool.pop(0))

            # Tambahkan coinbase transaction
            coinbase_transaction = {
                'sender': '0',
                'recipient': self.node_identifier,
                'amount': 5,
            }
            block['transactions'].insert(0, coinbase_transaction)

        self.chain.append(block)
        self.supply += 5
        if self.supply > self.initial_supply:
            raise Exception("Total supply exceeded the maximum limit")

        if len(self.chain) > 1000:
            self.prune(len(self.chain) - 1000)

        block['merkle_root'] = self.merkle_root(block['transactions'])
        self.current_block = block  # Set current_block ke blok baru
        return block

    def finalize_current_block(self):
        if self.current_block and self.current_block['transactions']:
            self.chain.append(self.current_block)
            self.current_block = None

    def new_transaction(self, sender, recipient, amount, signature, public_key, fee=5):
        amount = int(amount)
        fee = int(fee) 

        if sender not in self.public_keys and public_key:
            self.public_keys[sender] = public_key

        if recipient not in self.public_keys:
            private_key, new_public_key = generate_keys()
            self.public_keys[recipient] = new_public_key
            logging.info(f"Generated public key for {recipient}: {new_public_key}") 

        transaction = {
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
            'signature': signature,
            'public_key': public_key,
            'fee': fee,
            'timestamp': time(),
            'nonce': uuid4().hex,     
        }

        if not self.validate_transaction(transaction):
            raise InvalidTransactionError("Invalid transaction")
        
        # Cek apakah blok saat ini sudah penuh
        if self.current_block and len(self.current_block['transactions']) < self.max_transactions_per_block:
            self.current_block['transactions'].append(transaction)
        else:
            self.mempool.append(transaction)

        # Update saldo
        if sender != '0':
            self.balances[sender] -= (amount + fee)
        self.balances[recipient] = self.balances.get(recipient, 0) + amount
        self.balances[self.node_identifier] = self.balances.get(self.node_identifier, 0) + fee

        # Mengelola pembagian transaksi ke blok berikutnya jika mempool sudah penuh
        if len(self.mempool) > 0 and len(self.current_block['transactions']) == self.max_transactions_per_block:
            self.mine()  # Menambang blok baru untuk mengosongkan mempool

        return self.last_index + 1

    def mine(self):
        last_block = self.chain[-1]
        new_proof = self.proof_of_work(last_block['proof'])

        # Buat blok baru
        previous_hash = self.hash(last_block)
        block = self.new_block(new_proof, previous_hash)
        
        # Bersihkan mempool dari transaksi yang sudah masuk ke blok
        self.clean_mempool(block['transactions'])

        # Tambahkan transaksi dari mempool ke blok berikutnya jika ada
        while len(self.mempool) > 0:
            new_proof = self.proof_of_work(last_block['proof'])
            block = self.new_block(new_proof, previous_hash)
            self.clean_mempool(block['transactions'])

        return block

    def clean_mempool(self, processed_transactions):
        # Hapus transaksi yang sudah diproses dari mempool
        processed_tx_hashes = set(self.hash(tx) for tx in processed_transactions)
        self.mempool = [tx for tx in self.mempool if self.hash(tx) not in processed_tx_hashes]
    
    def validate_transaction(self, transaction):
        if not all(k in transaction for k in ["sender", "recipient", "amount", "signature", "public_key"]):
            return False
        if not isinstance(transaction['amount'], (int, float)) or transaction['amount'] <= 0:
            return False
        if transaction['sender'] == transaction['recipient']:
            return False
    
        # Validasi tanda tangan
        if transaction['sender'] != '0':
            public_key = transaction['public_key']
            message = f"{transaction['sender']}{transaction['recipient']}{transaction['amount']}"
            if not verify_signature(public_key, message, transaction['signature']):
                logging.error(f"Invalid signature for transaction: {transaction}")
                return False
    
        return True

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
        self.new_transaction(sender='0', recipient='user1', amount=10000, signature='', public_key='', fee=0)
        self.new_transaction(sender='0', recipient='user2', amount=50, signature='', public_key='', fee=0)
        last_proof = self.last_block['proof']
        proof = self.proof_of_work(last_proof)
        self.new_block(proof)

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1] if self.chain else None

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

        try:
            for node in neighbours:
                response = requests.get(f'http://{node}/chain')
                if response.status_code == 200:
                    length = response.json()['length']
                    chain = response.json()['chain']

                    if length > max_length and self.valid_chain(chain):
                        max_length = length
                        new_chain = chain
        except requests.RequestException as e:
            logging.error(f"Failed to connect to node {node}: {e}")

        if new_chain:
            self.chain = new_chain
            logging.info("Chain was replaced with a longer valid chain from the network")
            return True
        
        logging.info("Chain is authoritative and no longer valid chain found")
        return False

    def register_node(self, address):
        self.nodes.add(address)

    def consensus_algorithm(self):
        try:
            start_time = time.time()
            max_attempts = 3
            attempt = 0

            while attempt < max_attempts:
                replaced = self.resolve_conflicts()
                
                if replaced:
                    logging.info("Our chain was replaced")
                    self.validate_new_chain()
                    self.update_mempool()
                    self.broadcast_new_chain()
                    return True
                else:
                    logging.info("Our chain is authoritative")
                    if self.validate_local_chain():
                        self.broadcast_chain_validity()
                        return False
                    else:
                        logging.warning("Local chain validation failed. Retrying consensus...")
                
                attempt += 1
                if attempt < max_attempts:
                    wait_time = random.uniform(1, 5)
                    time.sleep(wait_time)

            if attempt == max_attempts:
                raise ConsensusError("Failed to reach consensus after maximum attempts")

        except Exception as e:
            logging.error(f"Error in consensus algorithm: {str(e)}")
            raise
        finally:
            end_time = time.time()
            logging.info(f"Consensus algorithm took {end_time - start_time:.2f} seconds")

    def validate_new_chain(self):
        if not self.valid_chain(self.chain):
            raise ConsensusError("Newly received chain is invalid")
        logging.info("New chain validated successfully")

    def update_mempool(self):
        new_mempool = [tx for tx in self.mempool if not self.transaction_in_chain(tx)]
        removed_count = len(self.mempool) - len(new_mempool)
        self.mempool = new_mempool
        logging.info(f"Updated mempool. Removed {removed_count} transactions.")

    def broadcast_new_chain(self):
        for node in self.nodes:
            try:
                logging.info(f"Broadcasting new chain to {node}")
            except Exception as e:
                logging.error(f"Failed to broadcast new chain to {node}: {str(e)}")

    def validate_local_chain(self):
        return self.valid_chain(self.chain)

    def broadcast_chain_validity(self):
        for node in self.nodes:
            try:
                logging.info(f"Broadcasting chain validity to {node}")
            except Exception as e:
                logging.error(f"Failed to broadcast chain validity to {node}: {str(e)}")

    def transaction_in_chain(self, transaction):
        return any(tx == transaction for block in self.chain for tx in block['transactions'])
