# test_rangeproof

## Setup

Install requirements:

```sh
virtualenv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

Tested with [`elements.conf`](./elements.conf) in this folder.

## Run

```sh
python3 test_embit.py
python3 test_hot.py
```

Resulting psbt will be stored in data folder.