import json
import pandas
from lnpanda import lnpanda
from pprint import pprint
from datetime import datetime, timedelta

from protobuf_to_dict import protobuf_to_dict


pandas.set_option("display.max_colwidth", None)
pandas.set_option("display.max_rows", None)
pandas.options.display.float_format = "{:.8f}".format


# Create main object
ln = lnpanda()
import code
code.interact(local=dict(globals(), **locals()))
