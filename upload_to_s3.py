#!/usr/bin/env python

__author__ = 'milan marcic'
__version__ = '0.1'

"""
Description:
    Finds audit logs inside tomcat logs dir.
    Checks if audit S3 bucket exists, if doesn't exist creates one.
    Checks if audit logs already exist in S3 bucket, if not uploads them.
    If there's any exceptions, sends email to xxxx@gmail.com.

Prerequisites:
    boto3, sendgrid

Execution Frequency:
    daily cronjob
"""

import fnmatch
import os
import sys
import boto3
import sendgrid
import datetime
from sendgrid.helpers.mail import *
import urllib2 as urllib

# audit logs found in tomcat dir
audit_logs = []

# audit log files not in S3 bucket to be uploaded
audit_logs_to_upload = []

# create session
aws_access_key_id = '{{ aws_access_key_id }}'
aws_secret_access_key = '{{ aws_secret_access_key }}'
client = boto3.client('s3',
                      aws_access_key_id=aws_access_key_id ,
                      aws_secret_access_key=aws_secret_access_key
                      )

# create bucket name
instance_hostname = os.uname()[1]
bucket_name = instance_hostname + '-auditlogs'

# audit logs path
path = '/data/tomcat/logs'

sendgrid_api_key = '{{ sendgrid_api_key }}'

today = datetime.date.today()

def findFile():
    """
    finds audit logs inside /data/tomcat/logs
    """
    for file in os.listdir(path):
        if fnmatch.fnmatch(file, 'audit.log.20*'):
            audit_logs.append(file)
    print "List of audit logs inside directory:"
    print audit_logs


def createBucket():
    """
    creates an S3 bucket if it doesn't already exist
    """
    try:
        list_buckets_output = client.list_buckets()
    except Exception as e:
        email(e.message)
        print e.message

    bucket_list = [list_buckets_output['Buckets'][n]['Name'] for n in range(len(list_buckets_output['Buckets']))]

    try:
        # create bucket if it doesn't exist
        if bucket_name in bucket_list:
            print "Bucket '{b}' already exists".format(b=bucket_name)
        else:
            print "Bucket {b} 'doesn't exist', creating one".format(b=bucket_name)
            create_bucket_output = client.create_bucket(
                Bucket=bucket_name
            )

    except Exception as e:
        email(e.message)
        print e.message



def listBucketObjects():
    """
    lists objects inside S3 bucket
    """
    list_bucket_objects_output = client.list_objects(
        Bucket=bucket_name,
    )

    # check if bucket is empty, if not list bucket's contents
    if 'Contents' in list_bucket_objects_output:
        bucket_objects_list = [list_bucket_objects_output['Contents'][n]['Key'] for n in range(len(list_bucket_objects_output['Contents']))]
        return list(bucket_objects_list)
    else:
        print "No objects in S3 bucket '{b}'".format(b=bucket_name)



def checkLogExists():
    """
    check if audit file already exists in the S3 bucket
    """
    bucket_objects_list = listBucketObjects()

    try:
        if audit_logs is not None:
            for file in audit_logs:
                if bucket_objects_list is not None:
                    if file in bucket_objects_list:
                        print "File {f} already in the bucket".format(f=file)
                    else:
                        print "File {f} not in the bucket, needs to be uploaded".format(f=file)
                        audit_logs_to_upload.append(file)
                else:
                    print "Bucket is empty, file {f} needs to be uploaded".format(f=file)
                    audit_logs_to_upload.append(file)

        else:
            print "No audit logs found inside /data/tomcat/logs/ directory, Exiting program"
            sys.exit(0)
    except Exception as e:
        email(e.message)
        print e.message



def uploadFile():
    """
    uploads audit logs to S3 bucket
    """
    try:
        for file in audit_logs_to_upload:
            print 'Uploading {f}'.format(f=file)
            response = client.upload_file(path + '/' + file, bucket_name, file, ExtraArgs={'ServerSideEncryption': "AES256"})
    except Exception as e:
        email(e.message)
        print e.message


def email(message):
    """
    sends email if any exceptions
    """
    sg = sendgrid.SendGridAPIClient(apikey=sendgrid_api_key)
    from_email = Email("no-reply@notifications.com")
    subject = "S3 Audit Files Script Error from: %s on %s" % (instance_hostname, today)
    to_email = Email("xxxxxx@symphony.com")
    content = Content("text/plain", message)
    mail = Mail(from_email, subject, to_email, content)
    try:
        response = sg.client.mail.send.post(request_body=mail.get())
        print(response.status_code)
        print(response.body)
        print(response.headers)
    except urllib.HTTPError as e:
        print e.read()



def main():

    findFile()
    createBucket()
    listBucketObjects()
    checkLogExists()

    if not audit_logs_to_upload:
        print "No audit files to upload"
    else:
        uploadFile()


if __name__ == '__main__':
    main()
