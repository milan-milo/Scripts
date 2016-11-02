#!/usr/bin/env python

__author__ = 'Milan Marcic'
__email__ = 'milan.marcic@symphony.com'
__copyright__ = 'Copyright 2016, Symphony'
__version__ = '0.1.0'

# -----------------------------------------------------------------------
# Purpose:
#     - Find logs (.gz and .txt) older than n number of days in selected directories,
#       creates vault, encrypts them and uploads to Amazon Glacier in. After upload,
#       removes encrypted file.
#
# Usage:
#     - archive_age = xxxxxxx (in hours) - Logs older than this amount will be archived and removed.
#     - aws_access_key_id = 'xxxxxxxxxx'
#     - aws_secret_access_key = 'xxxxxxxxxx'
#     - region_name = "xxxxxxxxxx"
#     - encryption_password = 'xxxxxxxxxxx'
#
# -----------------------------------------------------------------------


import os
import time
import boto3
import socket
import sys
import datetime
import re
import traceback
import pymongo
from hashlib import md5
from Crypto.Cipher import AES
from Crypto import Random
from pymongo import MongoClient
from math import log
from boto.glacier.concurrent import ConcurrentUploader
from boto.glacier.layer1 import Layer1

#boto3.set_stream_logger(name='botocore')

class StoreLogs(object):

    scheduled_for_vault = 0
    not_scheduled_for_vault = 0
    uploaded_to_vault = 0
    uploaded_size_in_mb = 0
    failed_upload_to_vault = 0


    def __init__(self, archive_age, aws_access_key_id,
                 aws_secret_access_key, region_name,
                 client, mongodb_host
                 ):

        self.archive_age = archive_age
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.client = client
        self.hostname = socket.gethostname()
        self.current_date = datetime.datetime.today().strftime("%d/%m/%Y")
        self.mongodb_host = mongodb_host
        self.OKBLUE = '\033[94m'
        self.OKGREEN = '\033[92m'
        self.WARNING = '\033[93m'
        self.FAIL = '\033[91m'
        self.ENDC = '\033[0m'


    def find_logs(self, directory):
        """ Find logs (.gz or .txt) older than n days and returns as a list """

        seconds_since_epoch = int(time.time())
        hours_since_epoch_now = seconds_since_epoch / 3600

        list_of_archives = []

        if os.path.isdir(directory):
            for root, dirs, files in os.walk(directory, topdown=True):
                for name in files:
                    if os.path.isfile((os.path.join(root, name))):
                        absolute_filename = (os.path.join(root, name))
                        filetime_since_epoch = int(os.path.getmtime(absolute_filename))
                        hours_since_epoch_file = filetime_since_epoch / 3600
                        remaining_time = hours_since_epoch_now - hours_since_epoch_file

                        if remaining_time > self.archive_age:
                            print 'This file will be archived: {0}'.format(absolute_filename)
                            StoreLogs.scheduled_for_vault += 1
                            list_of_archives.append(absolute_filename)
                        else:
                            print 'Won\'t archive: {0}'.format(absolute_filename)
                            StoreLogs.not_scheduled_for_vault += 1
                break       # breaks after first iteration so there's no recursive search of dirs
        else:
            sys.exit("Directory {0} doesn't exist. Exiting".format(directory))

        return list_of_archives




    def create_vault(self):
        """ Checks if Glacier Vault(Storage Container) already exists,
        if not creates it """

        if len(self.hostname) == 0:
            sys.exit('Missing hostname, vault can\'t be created')

        list_vaults_output = self.client.list_vaults()

        vault_list = [list_vaults_output['VaultList'][n]['VaultName'] for n in range(len(list_vaults_output['VaultList']))]

        if self.hostname in vault_list:
            print 'vault \"{0}\" Already exists and won\'t be created'.format(self.hostname)
        else:
            create_vault_output = self.client.create_vault(
                vaultName=self.hostname
            )
            print 'Vault Created:\n {0}'.format(create_vault_output)



    def create_directory(self, directory):
        """ Creates archived directory to move uploaded files to """

        archived_directory = directory + '/archived'

        try:
            os.makedirs(archived_directory)
            print self.OKGREEN + 'Created "Archived" directory' + self.ENDC
        except OSError:
            if not os.path.isdir(archived_directory):
                raise



    def upload_archives(self, archive_list, encryption_password, directory):
        """ If logs are greather than 0 bytes and older than n amount of days,
         send them in chunks and reassemble at AWS Glacier. Only if transferred successfully,
         remove from the instance """

        destination_directory = directory + '/archived/'

        #upload an archive (file)
        for archive in archive_list:

            in_filename = archive
            out_filename = archive + '.enc'
            split_move_file = re.split('/', in_filename)
            split_term = re.split('/', out_filename)
            description = '{0}'.format(split_term[-1])

            for i in range(5):
                try:
                    if os.path.getsize(archive) > 0:
                        print self.OKBLUE + 'Encrypting file {0}'.format(archive) + self.ENDC
                        with open(in_filename, 'rb') as in_file, open(out_filename, 'wb') as out_file:
                            self.encrypt(in_file, out_file, encryption_password)

                        print self.OKBLUE + 'Started upload for %s to %s at %s.' % (out_filename, self.hostname, datetime.datetime.utcnow()) + self.ENDC
                        glacier_layer = Layer1(
                            aws_access_key_id=self.aws_access_key_id,
                            aws_secret_access_key=self.aws_secret_access_key,
                            region_name = self.region_name
                        )
                        uploader = ConcurrentUploader(glacier_layer, self.hostname, part_size=128*1024*1024, num_threads=4)
                        archive_id = uploader.upload(out_filename, description)
                        print self.OKGREEN + '{0} was uploaded to {1} (archive ID: {2})'.format(out_filename, self.hostname, archive_id) + self.ENDC

                        StoreLogs.uploaded_size_in_mb += os.path.getsize(archive)
                        StoreLogs.uploaded_to_vault += 1

                        os.remove(out_filename)
                        print self.FAIL + 'Removed encrypted file: {0}'.format(out_filename) + self.ENDC

                        os.rename(archive, destination_directory + split_move_file[-1])
                        print self.OKGREEN + 'Moved {0} to "Archived" directory'.format(in_filename) + self.ENDC
                    else:
                        print 'File {0} is 0 bytes and won\'t be uploaded'.format(archive)
                        StoreLogs.uploaded_to_vault += 1

                except Exception:
                    num_of_tries = i + 1
                    if i == 4:
                        StoreLogs.failed_upload_to_vault += 1
                        print self.FAIL + 'Upload failed!!! Exhausted all retries'.format(out_filename) + self.ENDC
                    else:
                        print self.FAIL + 'Upload failed!!! Retry #{0} for {0}'.format(num_of_tries, out_filename) + self.ENDC
                        print self.FAIL + traceback.print_exc() + self.ENDC
                else:
                    break


    def store_stats(self):
        """ Stores jobs statistics inside MongoDB """

        try:
            client = MongoClient(self.mongodb_host, 27017)
        except pymongo.errors.ConnectionFailure:
            print self.FAIL + 'Unable to establish connection to MongoDB, stats won\'t be sent.' + self.ENDC
        else:
            date = datetime.datetime.now()
            today_date = '{0}-{1}-{2}'.format(date.day, date.month, date.year)


            upload_stats = {"Host": self.hostname,
                            "Upload_Date": today_date,
                            "Scheduled_For_Vault": StoreLogs.scheduled_for_vault,
                            "Not_Scheduled_For_Vault": StoreLogs.not_scheduled_for_vault,
                            "Uploaded_Successfully_And_Removed": StoreLogs.uploaded_to_vault,
                            "Uploaded_Size_In_MB": StoreLogs.uploaded_size_in_mb,
                            "Failed_Upload_To_Vault": StoreLogs.failed_upload_to_vault}

            db = client.vault_stats_db
            inserted_document = db.vault_stats.insert_one(upload_stats).inserted_id
            print 'Inserted document output: {0}'.format(inserted_document)



    def calculate_size(self, n, pow=0,b=1024,u='B',pre=['']+[p+'i'for p in'KMGTPEZY']):
        """ Calculate size of transferred archives """

        pow, n = min(int(log(max(n*b**pow,1),b)),len(pre)-1),n*b**pow
        return "%%.%if %%s%%s"%abs(pow%(-pow-1))%(n/b**float(pow),pre[pow],u)



    def derive_key_and_iv(self, password, salt, key_length, iv_length):
        d = d_i = ''
        while len(d) < key_length + iv_length:
            d_i = md5(d_i + password + salt).digest()
            d += d_i
        return d[:key_length], d[key_length:key_length+iv_length]



    def encrypt(self, in_file, out_file, password, key_length=32):
        """ Encrypts file before uploading to glacier """

        bs = AES.block_size
        salt = Random.new().read(bs - len('Salted__'))
        key, iv = self.derive_key_and_iv(password, salt, key_length, bs)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        out_file.write('Salted__' + salt)
        finished = False
        while not finished:
            chunk = in_file.read(1024 * bs)
            if len(chunk) == 0 or len(chunk) % bs != 0:
                padding_length = (bs - len(chunk) % bs) or bs
                chunk += padding_length * chr(padding_length)
                finished = True
            out_file.write(cipher.encrypt(chunk))



    def decrypt(self, in_file, out_file, password, key_length=32):
        """ Decrypts encrypted filed stored in Glacier:
            with open(in_filename, 'rb') as in_file, open(out_filename, 'wb') as out_file:
                decrypt(in_file, out_file, password)"""

        bs = AES.block_size
        salt = in_file.read(bs)[len('Salted__'):]
        key, iv = self.derive_key_and_iv(password, salt, key_length, bs)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        next_chunk = ''
        finished = False
        while not finished:
            chunk, next_chunk = next_chunk, cipher.decrypt(in_file.read(1024 * bs))
            if len(next_chunk) == 0:
                padding_length = ord(chunk[-1])
                chunk = chunk[:-padding_length]
                finished = True
            out_file.write(chunk)


def main():

    logs_dirs = {
        'tomcat' : '/data/tomcat/logs/'
  #      'hadoop' : '/data/hadoop/logs/',
  #      'hbase' : '/data/hbase/logs/',
  #      'kafka' : '/data/kafka/logs/',
  #      'solr' : '/data/solr/logs/',
  #      'zookeeper' : '/data/zookeeper/logs/',
  #      'nginx' : '/data/nginx/log/'
    }

    aws_access_key_id = 'xxxxxxxxxx'
    aws_secret_access_key = 'xxxxxxxxxx'
    region_name = "us-east-1"

    encryption_password = 'xxxxxxxxxxx'

    # one month in hours
    archive_age = 120
    mongodb_host = 'xxxxxxxxxxx'

    client = boto3.client('glacier',
                          aws_access_key_id=str(aws_access_key_id),
                          aws_secret_access_key=str(aws_secret_access_key),
                          region_name=str(region_name)
                          )

    store_logs_object = StoreLogs(
        archive_age, aws_access_key_id,
        aws_secret_access_key, region_name, client,
        mongodb_host
    )

    store_logs_object.create_vault()

    for service, dir in logs_dirs.items():
        store_logs_object.create_directory(dir)

        archive_list = store_logs_object.find_logs(dir)
        store_logs_object.upload_archives(archive_list, encryption_password, dir)

    StoreLogs.uploaded_size_in_mb = store_logs_object.calculate_size(StoreLogs.uploaded_size_in_mb)
    store_logs_object.store_stats()

    print "Number of files scheduled for Glacier upload: {0}".format(StoreLogs.scheduled_for_vault)
    print "Number of files not scheduled for Glacier upload: {0}".format(StoreLogs.not_scheduled_for_vault)
    print "Number of files uploaded to Glacier: {0}".format(StoreLogs.uploaded_to_vault)
    print "Size of all the uploaded files: {0}".format(StoreLogs.uploaded_size_in_mb)
    print "Number of files failed uploading to Glacier: {0}".format(StoreLogs.failed_upload_to_vault)


if __name__ == '__main__':
    main()
