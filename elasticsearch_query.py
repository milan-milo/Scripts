#! /usr/bin/env python

""" ca_alerts-tomcat.py Parses ElasticSearch
index based on classes & loglevel messages,
if it finds a match notifies users via email
"""

__author__ = "Milan Marcic"
__version__ = "0.0.3"

from elasticsearch import Elasticsearch
import datetime
import socket
import sendgrid
import sys
from sendgrid.helpers.mail import *

hostname = socket.gethostname()
es = Elasticsearch(hostname, port=9200)
today = datetime.date.today()

search_index = 'tomcat'

classesSearch = [
    "com.symphony.retention.RetentionService",
    "com.gs.ti.wpt.lc.logging.service.AuditTrailLoggingServiceImpl",
    "com.symphony.cecserviceweb.context.AppContext",
    "com.symphony.cecserviceweb.service.PodHealthIndicator",
    "com.symphony.cecserviceweb.service.KeyManagerHealthIndicator"
]

def checkIndexExists():
    if not es.indices.exists(search_index):
        print "%s index doesn't exist, exiting script!" % search_index
        sys.exit(1)

#query elasticseach for class, loglevel and timestamp key/values

def findMatch():
    try:
        for i in range(len(classesSearch)):
            res = es.search(
                index='tomcat',
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "match": {
                                        "class": classesSearch[i]
                                    }
                                },
                                {
                                    "range": {
                                        "@timestamp": {
                                            "gte": "now-1h",
                                            "lte": "now"
                                        }
                                    }
                                }
                            ],
                            "should" : [
                                { "match" : { "loglevel" : "ERROR" } },
                                { "match" : { "loglevel" : "WARN" } }
                            ],
                            "minimum_should_match" : 1
                        }
                    }
                },
                request_timeout=30
            )
            if res['hits']['hits'] != []:
                for hit in res['hits']['hits']:
                    var = ("Host: %(host)s\nLog Level: %(loglevel)s\nMessage: %(message)s" % hit["_source"])
                    print var
    except:
        email('Content Export Alerts Script unable to perform query on elasticsearch and parse %s index. This doesn\'t indicate a problem with Content Export. Please create Jira ticket and assign to ES Team for further investigation') % search_index
        sys.exit(1)

#email function called if result is generated

def email(message):

    sg = sendgrid.SendGridAPIClient(apikey='{{ api_key }}')
    from_email = Email("no-reply@notifications.xxx.com")
    subject = "Content Export Error from: %s on %s" % (hostname, today)
    to_email = Email("{{ support_email }}")
    content = Content("text/plain", message)
    mail = Mail(from_email, subject, to_email, content)
    response = sg.client.mail.send.post(request_body=mail.get())
    print(response.status_code)
    print(response.body)
    print(response.headers)

def main():
    checkIndexExists()
    findMatch()

if __name__ == "__main__":
    main()

