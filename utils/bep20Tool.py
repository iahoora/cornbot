from decimal import Decimal
from web3 import Web3
from eth_account import Account
import json

# Connect to Binance Smart Chain (BSC) node
bsc_rpc_url = "https://bsc-dataseed.binance.org/"  # Public BSC RPC URL
web3 = Web3(Web3.HTTPProvider(bsc_rpc_url))

# USDT contract address on BSC
USDT_CONTRACT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"
USDT_ABI = '[{"inputs":[],"payable":false,"stateMutability":"nonpayable","type":"constructor"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"owner","type":"address"},{"indexed":true,"internalType":"address","name":"spender","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Approval","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"previousOwner","type":"address"},{"indexed":true,"internalType":"address","name":"newOwner","type":"address"}],"name":"OwnershipTransferred","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"from","type":"address"},{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Transfer","type":"event"},{"constant":true,"inputs":[],"name":"_decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"_name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"_symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"burn","outputs":[{"internalType":"bool","name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"subtractedValue","type":"uint256"}],"name":"decreaseAllowance","outputs":[{"internalType":"bool","name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"getOwner","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"addedValue","type":"uint256"}],"name":"increaseAllowance","outputs":[{"internalType":"bool","name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":false,"inputs":[{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"mint","outputs":[{"internalType":"bool","name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[],"name":"renounceOwnership","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"internalType":"bool","name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":false,"inputs":[{"internalType":"address","name":"sender","type":"address"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"transferFrom","outputs":[{"internalType":"bool","name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":false,"inputs":[{"internalType":"address","name":"newOwner","type":"address"}],"name":"transferOwnership","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"}]'  # Replace with the actual ABI of the USDT contract

# Load USDT contract
usdt_contract = web3.eth.contract(address=USDT_CONTRACT_ADDRESS, abi=USDT_ABI)

def create_bep20_wallet():
    """Create a new BEP-20 wallet."""
    account = Account.create()
    return {
        "address": account.address,
        "private_key": account.key.hex()
    }

def check_balance_usdt(wallet_address):
    """Check the USDT balance of a wallet."""
    balance = usdt_contract.functions.balanceOf(wallet_address).call()
    print(f"USDT Balance for {wallet_address}: {float(balance) / 10**18} (in wei)")
    return float(balance) / 10**18  # Convert from wei to USDT (18 decimals)

USDT_ADDRESS = Web3.to_checksum_address(
    "0x55d398326f99059fF775485246999027B3197955"
)

# --- minimal ABI: we only need decimals, balanceOf and transfer
USDT_ABI = json.loads("""
[
  {"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
  {"constant":true,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
  {"constant":false,"inputs":[{"name":"recipient","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}
]
""")

usdt = web3.eth.contract(address=USDT_ADDRESS, abi=USDT_ABI)
DECIMALS = usdt.functions.decimals().call()        # 18 on BSC :contentReference[oaicite:0]{index=0}
TEN_POW_DECIMALS = 10 ** DECIMALS                  # 1 000 000 000 000 000 000

# ---------- helpers ---------------------------------------------------------
def to_smallest_unit(amount):
    """Convert human-readable USDT to contract units (wei-like)."""
    return int(Decimal(str(amount)) * TEN_POW_DECIMALS)

def from_smallest_unit(raw):
    """Convert contract units back to human-readable USDT."""
    return Decimal(raw) / TEN_POW_DECIMALS

def check_balance_usdt(addr):
    addr = Web3.to_checksum_address(addr)
    bal_raw = usdt.functions.balanceOf(addr).call()
    return from_smallest_unit(bal_raw)

# ---------- fixed transfer --------------------------------------------------
def transfer_usdt(priv_key, to_addr, amount):
    """
    Send `amount` USDT (human readable) from the wallet behind `priv_key`
    to `to_addr` and return the tx hash.
    """
    sender = Account.from_key(priv_key)
    to_addr = Web3.to_checksum_address(to_addr)
    value_raw = to_smallest_unit(amount)  # Convert to smallest unit (wei-like)

    # 1️⃣ balance check
    if usdt.functions.balanceOf(sender.address).call() < value_raw:
        raise ValueError("Insufficient USDT balance.")

    # 2️⃣ build tx (use snake_case for v6, camelCase for v5)
    nonce = web3.eth.get_transaction_count(sender.address)
    gas_limit = usdt.functions.transfer(to_addr, value_raw).estimate_gas(
        {"from": sender.address}
    )
    gas_price = web3.eth.gas_price

    tx_dict = {
        "chainId": 56,
        "gas": gas_limit,
        "gasPrice": 0,
        "nonce": nonce,
    }

    build_fn = (
        usdt.functions.transfer(to_addr, value_raw).build_transaction  # v6
        if hasattr(usdt.functions.transfer(to_addr, value_raw), "build_transaction")
        else usdt.functions.transfer(to_addr, value_raw).buildTransaction  # v5
    ) 
    tx = build_fn(tx_dict)

    # 3️⃣ sign & broadcast
    signed = sender.sign_transaction(tx)
    tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
    return web3.to_hex(tx_hash), None

# print(web3.__version__) 
# print(create_bep20_wallet())
# bb = check_balance_usdt("0xE61d152c9f2aB1b0BA9908ABb69BFebA526EcD51")  # Replace with actual wallet address
# if bb > 20:
#     print(f"Balance is sufficient: {bb} USDT")
#     transfer_usdt("b0fe5f43fbb34582bf6ee0a23d40ae961b20c8b6875b2f2bb815e65e1048c38a", "0x7e109bbe8DEc88f24F50CC7fFD09A1f21050DE00", bb)
#     print("Transfer successful")
