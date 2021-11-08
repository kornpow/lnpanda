def calc():
	a = ln.list_forwards(90)[["fee_msat","eff_fee_rate"]]
	print("Running calculation for last 90 days...")
	for i in range(0,1500,50):
		ix = i + 50
		tx_range = a.sort_values(by="eff_fee_rate").query("@i < eff_fee_rate <= @ix")
		fees = tx_range.fee_msat.sum()/1000
		tx_count = tx_range.shape[0]
		if fees == 0:
			continue
		print(f"for fee range {i}-{ix}, over {tx_count} txns, made {fees} in fees")