from test_framework.authproxy import AuthServiceProxy, JSONRPCException
from embit.liquid.pset import PSET
import time

conf = {
    "rpcuser": "liquid",
    "rpcpassword": "secret",
    "rpcport": "18555",
}
rpc_url = "http://"+conf["rpcuser"]+":"+conf["rpcpassword"]+"@127.0.0.1:"+conf["rpcport"]
rpc = AuthServiceProxy(rpc_url)

def get_wallet_rpc(wallet_name):
    return AuthServiceProxy(rpc_url+f"/wallet/{wallet_name}")

def mine(rpc, blocks=1, address=None):
    if address is None:
        address = rpc.getnewaddress()
    rpc.generatetoaddress(1, address)

def get_default_wallet():
    """
    Checks the default wallet and returns corresponding rpc.
    If the wallet doesn't exist - creates it
    """
    wallets = rpc.listwallets()
    w = AuthServiceProxy(rpc_url+"/wallet/")
    if "" not in wallets:
        rpc.createwallet("")
        print("Created default wallet")
    balance = w.getbalances()["mine"]["trusted"]["bitcoin"]
    if balance == 0:
        w.rescanblockchain()
        time.sleep(0.1)
        balance = w.getbalances()["mine"]["trusted"]["bitcoin"]
        if balance == 0:
            raise RuntimeError("Failed to find free coins")
        # sending to self to make sure it's confidential and owned by us
        addr = w.getnewaddress()
        w.sendtoaddress(addr, balance//2)
        mine(w, 1, addr)
    # check we still have balance
    balance = w.getbalances()["mine"]["trusted"]["bitcoin"]
    print(f"Default wallet balance: {balance} tLBTC")
    if balance == 0:
        raise RuntimeError("Wallet is empty")   
    return w

def to_canonical_pset(pset):
    """
    Removes unblinded information from the transaction
    so Elements Core can decode it
    """
    # if we got psbt, not pset - just return
    tx = PSET.from_string(pset)

    for inp in tx.inputs:
        inp.value = None
        inp.asset = None
        inp.value_blinding_factor = None
        inp.asset_blinding_factor = None

    for out in tx.outputs:
        if out.is_blinded:
            out.asset = None
            out.asset_blinding_factor = None
            out.value = None
            out.value_blinding_factor = None
    return str(tx)
