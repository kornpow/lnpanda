chans = list(ln.list_channels_and_fees().query("active == False").chan_id)

for chan_id in chans:
    peer_pk = ln.get_peer_pk(chan_id)
    a = ln.lnd.get_node_info(peer_pk, include_channels=False)
    for connection in a.node.addresses:
        ln.lnd.connect_peer(peer_pk, connection.addr)
