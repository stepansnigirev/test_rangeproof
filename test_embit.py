import sys
from embit import bip39, bip32
from embit.descriptor.checksum import add_checksum
from embit.liquid import slip77
from embit.liquid.networks import get_network
from embit.liquid.pset import PSET, LSIGHASH
from embit.liquid.finalizer import finalize_psbt

from common import rpc, get_default_wallet, get_wallet_rpc, mine, to_canonical_pset

WALLET_NAME = "test_embit"
FNAME_PREFIX = "./data/embit_"

######### Preparation ##############

info = rpc.getblockchaininfo()
# get correct network dict with all prefixes
net = get_network(info["chain"])

# will create default wallet if it's missing
default_wallet = get_default_wallet()

mnemonic = "abandon "*11 + "about"
seed = bip39.mnemonic_to_seed(mnemonic)
mbk = slip77.master_blinding_from_seed(seed)
root = bip32.HDKey.from_seed(seed)
# derive account and convert to tpub
tpub = root.derive("m/84h/1h/0h").to_public().to_string(net["xpub"])
descriptor_key = f"[{root.my_fingerprint.hex()}/84h/1h/0h]{tpub}"

wallet = get_wallet_rpc(WALLET_NAME)
# Create wallet if it doesn't exist
if WALLET_NAME not in rpc.listwallets():
    # descriptor wallet
    rpc.createwallet(WALLET_NAME, True, True, "", False, True)
    args = [{
        "desc": add_checksum(f"wpkh({descriptor_key}/{change}/*)"),
        "internal": bool(change),
        "timestamp": "now",
        "watchonly": True,
        "active": True,
    } for change in [0, 1]]
    res = wallet.importdescriptors(args)
    assert all([r["success"] for r in res])
    wallet.importmasterblindingkey(mbk.secret.hex())
    print(f"Wallet {WALLET_NAME} created")

# check blinding key is set correctly
assert wallet.dumpmasterblindingkey() == mbk.secret.hex()

# fund wallet
balance = wallet.getbalances()["mine"]["trusted"]["bitcoin"]
if balance < 1:
    addr = wallet.getnewaddress()
    default_wallet.sendtoaddress(addr, 1)
    mine(default_wallet, 1)
balance = wallet.getbalances()["mine"]["trusted"]["bitcoin"]
if balance < 1:
    raise RuntimeError("Not enough funds")

############ Creating PSBT ###########

addr = default_wallet.getnewaddress()
# walletcreatefundedpsbt estimates fee without taking into account rangeproofs,
# so we need to set higher fees in this RPC call
unblinded = wallet.walletcreatefundedpsbt([], [{addr: 0.1}], 0, {"fee_rate": 0.3})["psbt"]

fname = f"{FNAME_PREFIX}_unblinded.pset"
with open(fname, "w") as f:
    print(f"Unblinded tx written to {fname}")
    f.write(unblinded)

# # blind using embit
# pset = PSET.from_string(unblinded)
# # rewind proofs to get blinding factors etc
# pset.unblind(mbk)
# # blind using some random seed
# pset.blind(b"1"*32)

# blinded = to_canonical_pset(str(pset))

# blind using Elements
blinded = wallet.walletprocesspsbt(unblinded)["psbt"]
pset = PSET.from_string(blinded)

fname = f"{FNAME_PREFIX}_blinded.pset"
with open(fname, "w") as f:
    print(f"Blinded tx written to {fname}")
    f.write(blinded)

############ Signing using embit ############

pset.sign_with(root, sighash=(LSIGHASH.ALL | LSIGHASH.RANGEPROOF))
signed_full = str(pset)
signed = to_canonical_pset(str(pset))

fname = f"{FNAME_PREFIX}_signed.pset"
with open(fname, "w") as f:
    print(f"Signed tx written to {fname}")
    f.write(signed)

fname = f"{FNAME_PREFIX}_signed_full.pset"
with open(fname, "w") as f:
    print(f"Signed tx written to {fname}")
    f.write(signed_full)

########## Trying to finalize and send ##############

print("Trying to finalize via RPC")
# depends on the branch - master or elements-0.21 behave differently
try:
    res = rpc.finalizepsbt(signed)
except:
    res = rpc.finalizepsbt(signed_full)

if (res["complete"]):
    print("Success! No complaints.")
    sys.exit()

print("Failed, finalizing manually")
signedpset = PSET.from_string(signed)
tx = finalize_psbt(signedpset)

fname = f"{FNAME_PREFIX}_final.tx"
with open(fname, "w") as f:
    print(f"Finalized tx written to {fname}")
    f.write(str(tx))

res = rpc.testmempoolaccept([str(tx)])
txid = rpc.sendrawtransaction(str(tx))
print(f"Broadcasted manually finalized transaction with txid {txid}")
mine(default_wallet, 1)

print("Summary: Elements-RPC failed to finalize a valid PSET transaction")
