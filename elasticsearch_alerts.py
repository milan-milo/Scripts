#! /usr/bin/env python

from elasticsearch import Elasticsearch
import datetime
import socket
import sendgrid
import os
import sys
from sendgrid.helpers.mail import *

hostname = socket.gethostname()
es = Elasticsearch(hostname, port=9200)
today = datetime.date.today()

#query elasticseach for class, loglevel and timestamp key/values

classesSearch = [
    "com.symphony.retention.RetentionService",
    "com.gs.ti.wpt.lc.logging.service.AuditTrailLoggingServiceImpl",
    "com.symphony.cecserviceweb.context.AppContext"
        ]

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
                                  "match": {
                                    "loglevel": "ERROR"
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
                              ]
                            }
                          }
                        }
                      )
            if res['hits']['hits'] != []:
                for hit in res['hits']['hits']:
                    var = ("Host: %(host)s\nLog Level: %(loglevel)s\nMessage: %(message)s" % hit["_source"])
                    email(var)
    except:
        email('Content Export Alerts Script unable to perform query on elasticsearch and parse tomcat index. This doesn\'t indicate a problem with Content Export. Please forward this email to Milan or ES Team for further investigation')
        sys.exit(1)


#email function called if result is generated

def email(message):

    sg = sendgrid.SendGridAPIClient(apikey='{{ api_key }}')
    from_email = Email("test@email.com")
    subject = "Content Export Error from: %s on %s" % (hostname, today)
    to_email = Email("{{ support_email }}")
    content = Content("text/plain", message)
    mail = Mail(from_email, subject, to_email, content)
    response = sg.client.mail.send.post(request_body=mail.get())
    print(response.status_code)
    print(response.body)
    print(response.headers)


def main():
    findMatch()

if __name__ == "__main__":
    main()
