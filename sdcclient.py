import sys
import time
import requests
import json
import re

###############################################################################
# The sysdig cloud client
###############################################################################
class SdcClient:
    userinfo = None
    n_connected_agents = None

    def __init__(self, token, sdc_url = 'https://app.sysdigcloud.com'):
        self.token = token
        self.hdrs = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'}
        self.url = sdc_url
   
    def __checkResponse(self, r):
        if r.status_code >= 300:
            self.errorcode = r.status_code

            j = r.json()
            if 'errors' in j:
                if j['errors'][0]['message']:
                    self.lasterr = j['errors'][0]['message']
                else:
                    self.lasterr = j['errors'][0]['reason']
            if 'message' in j:
                    self.lasterr = j['message']
            else:
                self.lasterr = 'status code ' + str(self.errorcode)
            return False
        return True

    def getUserInfo(self):
        if self.userinfo == None:
            r = requests.get(self.url + '/api/user/me', headers=self.hdrs)
            if not self.__checkResponse(r):
                return [False, self.lasterr]
            self.userinfo = r.json()
        return [True, self.userinfo]

    def getNConnectedAgents(self):
        r = requests.get(self.url + '/api/agents/connected', headers=self.hdrs)
        if not self.__checkResponse(r):
            return [False, self.lasterr]
        data = r.json()
        return [True, data['total']]

    def createAlert(self, name, description, condition, for_each, for_atelast_us, severity):
        #
        # Get the list of alerts from the server
        #
        r = requests.get(self.url + '/api/alerts', headers=self.hdrs)
        if not self.__checkResponse(r):
            return [False, self.lasterr]
        j = r.json()

        print 'Creating alert %s' % (description)

        #
        # If this alert already exists, don't create it again
        #
        for db in j['alerts']:
            if 'description' in db:
                if db['description'] == description:
                    return [False, 'alert ' + name + ' already exists']

        #
        # Populate the alert information
        #
        alert_json = {
            'alert' : {
                'type' : 'MANUAL',
                'name' : name,
                'description' : description,
                'enabled' : True,
                'severity' : severity,
                'notify' : [ 'EMAIL' ],
                'timespan' : for_atelast_us,
                'condition' : condition
            }
        }

        if for_each != None and for_each != []: 
            alert_json['alert']['segmentBy'] = [ for_each ]
            alert_json['alert']['segmentCondition'] = { 'type' : 'ANY' }

        #
        # Create the new alert
        #
        r = requests.post(self.url + '/api/alerts', headers=self.hdrs, data = json.dumps(alert_json))
        if not self.__checkResponse(r):
            return [False, self.lasterr]
        return [True, r.json()]

    def getNotificationSettings(self):
        r = requests.get(self.url + '/api/settings/notifications', headers=self.hdrs)
        if not self.__checkResponse(r):
            return [False, self.lasterr]
        return [True, r.json()]

    def setNotificationSettings(self, settings):
        r = requests.put(self.url + '/api/settings/notifications', headers=self.hdrs, data = json.dumps(settings))
        if not self.__checkResponse(r):
            return [False, self.lasterr]
        return [True, r.json()]

    def addEmailNotificationRecipient(self, email):
        #
        # Retirieve the user's notification settings
        #
        r = requests.get(self.url + '/api/settings/notifications', headers=self.hdrs)
        if not self.__checkResponse(r):
            return [False, self.lasterr]
        j = r.json()

        #
        # Enable email notifications
        #
        j['userNotification']['email']['enabled'] = True

        #
        # Add the given recipient
        #
        if not email in j['userNotification']['email']['recipients']:
            j['userNotification']['email']['recipients'].append(email)
        else:
            return [False, 'notification target ' + email + ' already present']

        return self.setNotificationSettings(j)

    def getExploreGroupingHierarchy(self):
        r = requests.get(self.url + '/api/groupConfigurations', headers=self.hdrs)
        if not self.__checkResponse(r):
            return [False, self.lasterr]

        data = r.json()

        if not 'groupConfigurations' in data:
            return [False, 'corrputed groupConfigurations API response']

        gconfs = data['groupConfigurations']

        for gconf in gconfs:
            if gconf['id'] == 'explore':
                res = []
                items = gconf['groups'][0]['groupBy']

                for item in items:
                    res.append(item['metric'])

                return [True, res]

        return [False, 'corrputed groupConfigurations API response, missing "explore" entry']

    def getDataRetentionInfo(self):
        r = requests.get(self.url + '/api/history/timelines/', headers=self.hdrs)
        if not self.__checkResponse(r):
            return [False, self.lasterr]
        return [True, r.json()]

    def getTopologyMap(self, grouping_hierarchy, time_window_s, sampling_time_s):
        #
        # Craft the time interval section
        #
        tlines = self.getDataRetentionInfo()

        for tline in tlines[1]['agents']:
            if tline['sampling'] == sampling_time_s * 1000000:
                timeinfo = tline

        if timeinfo == None:
            return [False, "sampling time " + str(sampling_time_s) + " not supported"]

        timeinfo['from'] = timeinfo['to'] - timeinfo['sampling']

        #
        # Create the grouping hierarchy
        #
        gby = [{'metric': g} for g in grouping_hierarchy]

        #
        # Prepare the json
        #
        req_json = {
            'format': {
                'type': 'map',
                'exportProcess': True
            },
            'time': timeinfo,
            #'filter': {
            #    'filters': [
            #        {
            #            'metric': 'agent.tag.Tag',
            #            'op': '=',
            #            'value': 'production-maintenance',
            #            'filters': None
            #        }
            #    ],
            #    'logic': 'and'
            #},
            'limit': {
                'hostGroups': 20,
                'hosts': 20,
                'containers': 20,
                'processes': 10
            },
            'group': {
                'configuration': {
                    'groups': [
                        {
                            'filters': [],
                            'groupBy': gby
                        }
                    ]
                }
            },
            'nodeMetrics': [
                {
                    'id': 'cpu.used.percent',
                    'aggregation': 'timeAvg',
                    'groupAggregation': 'avg'
                }
            ],
            'linkMetrics': [
                {
                    'id': 'net.bytes.total',
                    'aggregation': 'timeAvg',
                    'groupAggregation': 'sum'
                }
            ]
        }

        #
        # Fire the request
        #
        r = requests.post(self.url + '/api/data?format=map', headers=self.hdrs, data = json.dumps(req_json))
        if not self.__checkResponse(r):
            return [False, self.lasterr]
        return [True, r.json()]

    def getDashboards(self):
        r = requests.get(self.url + '/ui/dashboards', headers=self.hdrs)
        if not self.__checkResponse(r):
            return [False, self.lasterr]
        return [True, r.json()]

    def getAlerts(self):
        r = requests.get(self.url + '/api/alerts', headers=self.hdrs)
        if not self.__checkResponse(r):
            return [False, self.lasterr]
        return [True, r.json()]

    def create_dashboard_from_template(self, newdashname, templatename, scope):
        #
        # Create the unique ID for this dashboard
        #
        baseconfid = newdashname
        for sentry in scope:
            baseconfid = baseconfid + sentry.keys()[0]
            baseconfid = baseconfid + sentry.values()[0]

        print baseconfid

        #
        # Get the list of dashboards from the server
        #
        r = requests.get(self.url + '/ui/dashboards', headers=self.hdrs)
        if not self.__checkResponse(r):
            return [False, self.lasterr]

        j = r.json()

        #
        # Find our template dashboard
        #
        dboard = None

        for db in j['dashboards']:
            if db['name'] == templatename:
                dboard = db
                break

        if dboard == None:
            print 'can\'t find dashboard ' + templatename + ' to use as a template'
            sys.exit(0)

        #
        # Create the dashboard name
        #
        if newdashname:
            dname = newdashname
        else:
            dname = dboard['name'] + ' for ' + service

        #
        # If this dashboard already exists, don't create it another time
        #
        for db in j['dashboards']:
            if db['name'] == dname:
                for view in db['items']:
                    if view['groupId'][0:len(baseconfid)] == baseconfid:
                        print 'dashboard ' + dname + ' already exists - ' + baseconfid
                        return

        #
        # Clean up the dashboard we retireved so it's ready to be pushed
        #
        dboard['id'] = None
        dboard['version'] = None
        dboard['name'] = dname
        dboard['isShared'] = False # make sure the dashboard is not shared
        
        #
        # Assign the filter and the group ID to each view to point to this service
        #
        filters = []
        gby = []
        for sentry in scope:
            filters.append({'metric' : sentry.keys()[0], 'op' : '=', 'value' : sentry.values()[0]   , 'filters' : None})
            gby.append({'metric': sentry.keys()[0]})

        filter = {
            'filters' : 
            {
                'logic' : 'and',
                'filters' : filters
            }
        }

        j = 0

        for view in dboard['items']:
            j = j + 1

            #
            # create the grouping configuration
            #
            confid = baseconfid + str(j)

            gconf = { 'id': confid,
                'groups': [
                    {
                        'groupBy': gby
                    }
                ]
            }

            r = requests.post(self.url + '/api/groupConfigurations', headers=self.hdrs, data = json.dumps(gconf))
            if not self.__checkResponse(r):
                return [False, self.lasterr]

            view['filter'] = filter
            view['groupId'] = confid

    #   print json.dumps(dboard, indent=4, separators=(',', ': '))

        ddboard = {'dashboard': dboard}

        #
        # Create the new dashboard
        #
        r = requests.post(self.url + '/ui/dashboards', headers=self.hdrs, data = json.dumps(ddboard))
        if not self.__checkResponse(r):
            return [False, self.lasterr]
        else:
            return [True, r.json()]
