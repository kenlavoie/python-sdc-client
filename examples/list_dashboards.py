#!/usr/bin/env python
#
# Print the list of dashboards.
#

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), '..'))
from sdcclient import SdcClient

#
# Parse arguments
#
if len(sys.argv) != 2:
    print 'usage: %s <sysdig-token>' % sys.argv[0]
    print 'You can find your token at https://app.sysdigcloud.com/#/settings/user'
    sys.exit(1)

sdc_token = sys.argv[1]

#
# Instantiate the SDC client
#
sdclient = SdcClient(sdc_token)

#
# Fire the request.
#
res = sdclient.get_dashboards()

#
# Show the list of dashboards
#
if res[0]:
    data = res[1]
else:
    print res[1]
    sys.exit(1)

for db in data['dashboards']:
    print "Name: %s, # Charts: %d" % (db['name'], len(db['items'] if 'items' in db else []))
