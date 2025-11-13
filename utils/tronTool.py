from tronpy import Tron
from tronpy.providers import HTTPProvider
from tronpy.keys import PrivateKey



trongrid_api_key = '2c7553a0-2bef-4f22-89f1-36e07743027c'

client = Tron(HTTPProvider('https://api.trongrid.io', api_key=trongrid_api_key))

cntr = client.get_contract("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")

MAIN_ADDRESS = 'TGRkiRPn6TmvNefuEim1nP2u41i7qzXcdq'
MAIN_PRIVATE_KEY = '5928ebeaba8ee9d0f528d67e1dd8a3031b2b399c1c72347cf24a330c6e1218b3'
MAIN_ADDRESS_B = 'TP2Q2ZjxJoYUHdeJN3DQvQ57EvcmJZoLRD'

def create_account():
    return client.generate_address()


def check_usdt_balance(address):
    balance = cntr.functions.balanceOf(address) 
    return balance / 10**6


# transfer some trx for transfer fee to address
def transfer_trx(address):
    # transfer from main address to address, create new client
    client = Tron(HTTPProvider('https://api.trongrid.io', api_key=trongrid_api_key))
    priv_key = PrivateKey(bytes.fromhex(MAIN_PRIVATE_KEY))
    try:
        txn = (client.trx.transfer(MAIN_ADDRESS, address, 14000000).build().sign(priv_key)) # 1 trx\
    except Exception as e:
        return False, str(e)
    
    print(txn.txid)
    print(txn.broadcast().wait())
    return True, txn.txid

    # sign transaction
    # tx = client.trx.sign(tx)
    # print(tx)


    # return status and transaction hash
    # return True, tx['txid']

# transfer usdt address to main address
def transfer_usdt(amount, address, private_key):
    # transfer from main address to address, create new client
    client = Tron(HTTPProvider('https://api.trongrid.io', api_key=trongrid_api_key))
    priv_key = PrivateKey(bytes.fromhex(private_key))
    try:
        txn = (cntr.functions.transfer(MAIN_ADDRESS_B, int(amount * 10**6)).with_owner(address).fee_limit(35000000).build().sign(priv_key)) # 1 trx
    except Exception as e:
        return False, str(e)
    
    print(txn)
    print(txn.txid)
    print(txn.broadcast().wait())

    return True, txn.txid
    

def transfer_usdt_to_address(amount, address):
    # transfer from main address to address, create new client
    client = Tron(HTTPProvider('https://api.trongrid.io', api_key=trongrid_api_key))
    priv_key = PrivateKey(bytes.fromhex(MAIN_PRIVATE_KEY))
    try:
        txn = (cntr.functions.transfer(address, int(amount * 10**6)).with_owner(MAIN_ADDRESS).fee_limit(35000000).build().sign(priv_key)) # 1 trx
    except Exception as e:
        return False, str(e)
    
    print(txn)
    print(txn.txid)
    print(txn.broadcast().wait())

    return True, txn.txid

# test code
# {'base58check_address': 'TWreNzapMWZWFV9u1F5pYXLd3A69TibpoU', 'hex_address': '41e51cea13fa2daa9409ee9bfd9090664658ed70e9', 'private_key': '38021bde009aa56e4d3b902bdaf1212d159e133d267814794b35f93e9f8e7f69', 'public_key': '95d8e66c5698fea0978fe0a3a49ebf7bb5a671c466d69382f750f085c1b1ecac460b20ab560ca0ae2b640502d9368372ec9767f812a9c420e0bc0222b0b3b73f'}
