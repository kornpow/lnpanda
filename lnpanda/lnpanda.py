from pathlib import Path
import json
from pprint import pprint
import os, sys
import base64
from time import sleep
from datetime import datetime, timedelta
import code
from functools import lru_cache

# Pip installed Modules
from lndgrpc import LNDClient
import pdir
import pandas
from protobuf_to_dict import protobuf_to_dict

pandas.set_option("display.max_colwidth", None)
pandas.set_option("display.max_rows", None)
pandas.options.display.float_format = "{:.8f}".format


# from channels import lnpanda
# a = lnpanda()

class lnpanda():
    def __init__(self):
        self.pkdb = {}
        self.graphnodes = {}
        self.graphedges = {}

        if not( "CRED_PATH" in os.environ and "LND_NODE_IP" in os.environ):
            print("ERROR: Must define CRED_PATH and LND_NODE_IP")
            sys.exit(-1)

        credential_path = Path(os.getenv("CRED_PATH"))

        mac = str(credential_path.joinpath("admin.macaroon").absolute())
        tls = str(credential_path.joinpath("tls.cert").absolute())

        # Create the connection to the remote node
        ip_addr = os.getenv("LND_NODE_IP")
        self.lnd = LNDClient(
            f"{ip_addr}:10009",
            macaroon_filepath=mac,
            cert_filepath=tls
        )

    def list_channels(self):
        def getBalance(row):
            return row["local_balance"] / (row["local_balance"] + row["remote_balance"])
        def getChanSize(row):
            return row["local_balance"] + row["remote_balance"]
        def getToBalance(row, target=500000):
            return target - row["local_balance"]

        lnreq = protobuf_to_dict(self.lnd.list_channels())

        # Check if no channels
        if not lnreq["channels"]:
            print("No Channels Available!")
            return lnreq
        # print(lnreq)
        d = pandas.DataFrame(lnreq["channels"])
        y = d[
            [
                "active",
                "chan_id",
                "channel_point",
                "remote_pubkey",
                "local_balance",
                "remote_balance",
                "capacity",
            ]
        ].fillna(0)
        # Convert columns to integers
        y[["local_balance", "remote_balance", "capacity"]] = y[
            ["local_balance", "remote_balance", "capacity"]
        ].apply(pandas.to_numeric, errors="coerce")
        y[["local_balance", "remote_balance", "capacity"]] = y[["local_balance", "remote_balance", "capacity"]].astype(int)
        y["balanced"] = y.apply(getBalance, axis=1)
        y["alias"] = y.apply(lambda x: self.get_alias(x.remote_pubkey), axis=1)
        y["tobalance"] = y.apply(getToBalance, axis=1)
        # y = y.sort_values(by=['balanced'])
        y = y.sort_values(by=["local_balance"], ascending=False)
        # y = y.sort_values(by=['balanced'])
        # Get balance ratio of all channels
        rb = y["remote_balance"].sum()
        lb = y["local_balance"].sum()
        print(f"Local to remote balance ratio: {lb/(lb+rb)}")
        # y = y.set_index("channel_point")

        y["remote_balance"] = y["remote_balance"].astype(int)
        return y[[
            "active",
            "alias",
            "balanced",
            "capacity",
            "local_balance",
            "remote_balance",
            "chan_id",
            "remote_pubkey",
        ]]

    def list_payments(self):
        t = pandas.DataFrame(protobuf_to_dict(self.lnd.list_payments(index_offset=0, max_payments=20000))["payments"])
        t['dest_pk'] = t.htlcs.apply(lambda x: x[0]['route']['hops'][-1]['pub_key'])
        t = t[['value_sat','creation_date','fee_msat','status','dest_pk']]
        return t

    def list_invoices(self):
        return pandas.DataFrame(protobuf_to_dict(self.lnd.list_invoices(index_offset=10000))["invoices"])

    def get_peer(self, list_cids):
        return self.list_channels_and_fees().query("chan_id.isin(@list_cids)")

    def get_peer_pk(self, cid):
        return self.list_channels().query("chan_id == @cid").remote_pubkey.values[0]

    def get_peer_cp(self, cid):
        return self.list_fees().query("chan_id == @cid").channel_point.values[0]

    def get_peer_alias(self, cid):
        return self.get_alias(self.get_peer_pk(cid))

    @lru_cache(maxsize=None)
    def get_alias(self, pubkey):
        return self.lnd.get_node_info(pubkey, include_channels=False).node.alias
        # try:
        #     # Attempt to use index names first
        #     alias = self.pkdb[pubkey]
        #     return alias
        # except KeyError as e:
        #     try:
        #         lnreq = protobuf_to_dict(self.lnd.get_node_info(pubkey, include_channels=False))
        #         alias = lnreq["node"]["alias"]
        #         self.pkdb.update({pubkey: alias})
        #         return lnreq["node"]["alias"]
        #     except KeyError as e:
        #         print(f"{pubkey} doesn't have an alias? Error: {e}")
        #         return "NONE/DELETED"


    def list_node_channels(self, pubkey):
        lnreq = protobuf_to_dict(self.lnd.get_node_info(pubkey, include_channels=True))
        channels = pandas.DataFrame(lnreq["channels"])
        channels['peer_pub'] = channels.apply(lambda x: x.node1_pub if x.node1_pub != pubkey else x.node2_pub, axis=1)
        channels = channels[['channel_id', 'chan_point', 'peer_pub',"capacity"]]
        channels["alias"] = channels.apply(lambda x: self.get_alias(x.peer_pub), axis=1)
        channels = channels[['alias', 'channel_id', 'chan_point', 'peer_pub',"capacity"]]
        return channels


    def graph_ingest_edges(self, include_policy=False):
        c = self.lnd.describe_graph()
        graph = protobuf_to_dict(c)

        edges = graph["edges"]
        edges_frame = pandas.DataFrame(edges)
        if include_policy:
            edges_frame = edges_frame[['channel_id', 'chan_point', 'node1_pub', 'node2_pub', 'capacity','node1_policy', 'node2_policy']]
        else:
            edges_frame = edges_frame[['channel_id', 'chan_point', 'node1_pub', 'node2_pub', 'capacity']]

        return edges_frame

    def graph_ingest_nodes(self):
        c = self.lnd.describe_graph()
        graph = protobuf_to_dict(c)

        pubkeys = graph["nodes"]
        pubkeys_frame = pandas.DataFrame(pubkeys)
        pubkeys_frame.last_update = pubkeys_frame.last_update.fillna(0).astype(int)
        # pubkeys_frame = pubkeys_frame.query("last_update is not NAN")
        pubkeys_frame = pubkeys_frame[['pub_key', 'alias']]

        return pubkeys_frame



    def get_block_height(self):
        return protobuf_to_dict(self.lnd.get_info())["block_height"]


    def get_my_pk(self):
        return protobuf_to_dict(self.lnd.get_info())["identity_pubkey"]

    def list_onchain_txns(self):
        txns_dict = protobuf_to_dict(self.lnd.list_transactions())
        txns = pandas.DataFrame(txns_dict["transactions"])
        txns = txns[["tx_hash","time_stamp","label","amount","total_fees","num_confirmations","block_height"]].fillna(0)
        txns[["time_stamp","amount","total_fees","num_confirmations","block_height"]] = txns[["time_stamp","amount","total_fees","num_confirmations","block_height"]].convert_dtypes(convert_integer=True)
        txns['time_stamp'] = a['time_stamp'].apply(lambda x: datetime.fromtimestamp(x))
        return txns[::-1]


    def list_offchain_txns(self):
        payments_dict = protobuf_to_dict(self.lnd.list_payments())
        payments = pandas.DataFrame(payments_dict["payments"])
        payments = payments[["payment_hash", "creation_date", "value", "fee_msat", "status", "payment_index"]].convert_dtypes(convert_integer=True)
        payments["creation_date"] = payments.creation_date.apply(lambda x: datetime.fromtimestamp(x) )


    def list_fees(self):
        fees_dict = protobuf_to_dict(self.lnd.fee_report())
        fees = pandas.DataFrame(fees_dict["channel_fees"])
        return fees

    def list_forwards(self, days_past):
        # Build up the dataframe
        forwards_dict = protobuf_to_dict(self.lnd.forwarding_history(num_max_events=20000))
        forwards = pandas.DataFrame(forwards_dict["forwarding_events"])

        # Do conversions
        forwards['date_time'] = forwards.timestamp.apply(lambda x: datetime.fromtimestamp(x))
        forwards.amt_in = forwards.amt_in.fillna(0).astype(int)
        forwards.amt_out = forwards.amt_out.fillna(0).astype(int)
        forwards['eff_fee_rate'] =  forwards.fee_msat / forwards.amt_out_msat * 1e6

        # Remove unwanted columns
        forwards.drop("fee", axis=1, inplace=True)
        forwards.drop("timestamp_ns", axis=1, inplace=True)
        forwards.drop("amt_in", axis=1, inplace=True)

        forwards = forwards[["chan_id_in","chan_id_out","amt_in_msat","amt_out_msat","fee_msat","eff_fee_rate","date_time","timestamp"]]

        if days_past:
            forwards = forwards.query(f"timestamp > { int((datetime.now() - timedelta(days=days_past)).timestamp())} ")
        return forwards

    def list_channels_and_fees(self):
        frame = self.list_channels().merge(self.list_fees(), on=["chan_id"])

        frame = frame[[
            'chan_id','active', 'alias', 'balanced',
            'capacity', 'local_balance','remote_balance',
            'base_fee_msat','fee_per_mil','fee_rate'
        ]]
        return frame

    def check_route_cost(self, route, amt):
        try:
            r = self.lnd.build_route(
                amt * 1000, 
                final_cltv_delta=40, 
                oid=0,
                hop_pubkeys=route,
            )
            fee_rate = r.route.total_fees_msat/r.route.total_amt_msat * 1e6
            cost = r.route.total_fees_msat/1000
            print(f"Route Fee Rate: {fee_rate}")
            print(f"Route cost: {cost}")
            return fee_rate,cost
        except Exception as e:
            return 20000, 20000


    def update_fees(self, cid, fee_rate):
        self.lnd.update_channel_policy(
            base_fee_msat=1,
            fee_rate=0.000001 * fee_rate,
            time_lock_delta=25,
            chan_point=self.get_peer_cp(cid)
        )
        print(self.list_channels_and_fees().query("chan_id == @cid"))


    def list_utxos(self):
       frame = pandas.DataFrame(protobuf_to_dict(self.lnd.list_unspent())["utxos"])
       return frame[['address','amount_sat','confirmations']]


if __name__ == "__main__":
    a = lnpanda()
    code.interact(local=locals())