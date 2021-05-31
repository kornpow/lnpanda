# lnpanda

lnpanda allows you to query Bitcoin lightning network data using Pandas dataframes. Pandas is a powerful data science tool, and the combination can be used to find insights about your node. In addition, pandas dataframes are a just convenient and powerful way to interact with your node, while staying on the command line!


## Install

```python
pip install lnpanda
```

## Environment Variables

Add information like node ip address, and directory containing:
- tls.cert 
- admin.macaroon

```bash
export CRED_PATH=/path/to/macaroon/and/tls/cert
export LND_NODE_IP=192.168.1.xx
```

## Basic Usage

```python
from lnpanda import lnpanda

# initialize lnpanda object
a = lnpanda()

# Get info about channel balances and fee rates in 1 view 
a.list_channels_and_fees()

# List routed transactions, shows eff_fee_rate of fwd
a.list_forwards()
```

## Using pandas queries

```python
# List channels with a fee rate > 100
a.list_channels_and_fees().query("fee_rate > 0.000100")

# Get sum of latest 25 routed transactions in sats
a.list_forwards().tail(25).fee_msat.sum()/1000

# Get a set of alias' of the last 10 outgoing forwards
outgoing_chan_ids = list(a.list_forwards().tail(10).chan_id_out)
set(map(lambda x: a.get_peer_alias(x), outgoing_chan_ids))
```