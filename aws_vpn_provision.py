#!/usr/bin/env python


__author__ = 'Milan Marcic'
__email__ = 'milan.marcic@symphony.com'
__copyright__ = 'Copyright 2016, Symphony'
__version__ = '0.1.0'

#==============================================================================
#
#
# description     : Builds out an entire AWS VPN stack
# notes           : the script only applies to newly built production pods
# usage           : ./vpn_provision.py --client test --group na --env prod --type chat --region glb --instanceIndex 1
#
# paramateres:     
#
# [client]        <client short name>  
# [group]         <pod group>          
# [env]           <environment>        
# [type]          <pod type>           
# [region]        <logical region>     
# [instanceIndex] <index of instance> 
#
#==============================================================================



import boto3
import yaml
import subprocess
import paramiko
import time
import argparse
import sys
from botocore.exceptions import ClientError
from fabric.api import *




class InputArgs(object):


    def __init__(self):

        self.args = self.getArgs()
        self.client_short_name = ''.join(self.args[0])                   # test
        self.group = ''.join(self.args[1])                               # na
        self.env = ''.join(self.args[2])                                 # prod
        self.type = ''.join(self.args[3])                                # chat
        self.logical_region = ''.join(self.args[4])                      # glb
        self.instanceIndex = ''.join(self.args[5])                       # 1

        #pod name
        self.pod_name = self.client_short_name + '-' + self.group + '-' + self.env + '-' + self.type + '-' + self.logical_region + '-' + self.instanceIndex
        print self.pod_name

        #pod name with extension
        self.pod_ext = self.pod_name + '.sls'
        print self.pod_ext

        #prod infra vpn
        self.infra_vpn = 'xxxxxxx'                                 # infra vpn name
        self.infra_vpn_pub = 'xxxxxxxx'                            # elastic ip for infra vpn
        self.infra_dest_cidr = 'xxxxxxxx'                          # destination route
        print 'Using %s from prod infra side with public ip: %s' % (self.infra_vpn, self.infra_vpn_pub)


    #command line arguments
    def getArgs(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--client', nargs=1, type=str, required=True)
        parser.add_argument('--group', nargs=1, type=str, required=True)
        parser.add_argument('--env', nargs=1, type=str, required=True)
        parser.add_argument('--type', nargs=1, type=str, required=True)
        parser.add_argument('--region', nargs=1, type=str, required=True)
        parser.add_argument('--instanceIndex', nargs=1, type=str, required=True)
        args = parser.parse_args()


        return [args.client,args.group,args.env,args.type,args.region,args.instanceIndex]



#extracts desired values from pillar file
class PillarFile():


    def __init__(self, pod_name, client_short_name, pod_ext, env):
        self.pod_name = pod_name
        self.podname_salt = pod_name + '-salt'
        self.clientname_salt = client_short_name + '-salt'
        self.pod_ext = pod_ext
        self.env = env

    #open pillar file
    def openPillar(self):
        with open('/srv/pillar/' + self.env + '/pods/' + self.pod_ext, 'r') as f:
            pillar_file = yaml.load(f)
        return pillar_file


    def getApiKey(self, pillar_file):

        if pillar_file[self.pod_name]['access_keys'][self.podname_salt]['access_key']:
            return pillar_file[self.pod_name]['access_keys'][self.podname_salt]['access_key']
        else:
            return pillar_file[self.pod_name]['access_keys'][self.clientname_salt]['access_key']


    def getApiSecret(self, pillar_file):

        if pillar_file[self.pod_name]['access_keys'][self.podname_salt]['secret_access_key']:
            return pillar_file[self.pod_name]['access_keys'][self.podname_salt]['secret_access_key']
        else:
            return pillar_file[self.pod_name]['access_keys'][self.clientname_salt]['secret_access_key']


    def getRegion(self, pillar_file):

        return pillar_file[self.pod_name]['region']


    def getAwsProfile(self, pillar_file):

        return pillar_file[self.pod_name]['AWS_PROFILE']


    def getCidr(self, pillar_file):

        return pillar_file[self.pod_name]['CIDR']


    def getKeyPair(self, pillar_file):

        return pillar_file[self.pod_name]['KEYPAIR']


    def getAz(self, pillar_file):

        return pillar_file[self.pod_name]['AVAILABILITY_ZONES'][0]


    def getSubnetId(self, pillar_file, aws_az):

        az = 'app-' + aws_az
        return pillar_file[self.pod_name]['SUBNETS'][az]['SUBNET_ID']


    def getSecGroup1(self, pillar_file):

        return pillar_file[self.pod_name]['SECURITY_GROUPS']['allow-all-inside_vpc']['SGRP_ID']


    def getSecGroup2(self, pillar_file):

        return pillar_file[self.pod_name]['SECURITY_GROUPS']['allow-all-symphony_office']['SGRP_ID']


    def getSecGroup3(self, pillar_file):

        return pillar_file[self.pod_name]['SECURITY_GROUPS']['allow-ssh-salt']['SGRP_ID']


    def getVpcId(self, pillar_file):

        return pillar_file[self.pod_name]['VPC_ID']






class Boto(object):

    regions = ['ap-southeast-1', 'eu-west-1', 'eu-central-1', 'us-east-1']
    region_ami = {'ap-southeast-1':'ami-aea582fc','eu-west-1':'ami-e4ff5c93','eu-central-1':'','us-east-1':'ami-96a818fe'}
    region_short = {'ap-southeast-1':'apse1','eu-west-1':'euw1','eu-central-1':'euc1','us-east-1':'ause1'}
    instance_type = 'm4.large'


    def __init__(self, api_key, api_secret, aws_region, aws_profile, aws_cidr, aws_keypair, aws_az1, aws_app_subnet1,
                 aws_secgroup1, aws_secgroup2, aws_secgroup3, aws_vpc_id, client_short_name, group, env, infra_vpn_pub,
                 infra_dest_cidr):


        self.api_key = api_key
        self.api_secret = api_secret
        self.aws_region = aws_region
        self.aws_profile = aws_profile
        self.aws_cidr = aws_cidr
        self.aws_keypair = aws_keypair
        self.aws_az1 = aws_az1
        self.aws_app_subnet1 = aws_app_subnet1
        self.aws_secgroup1 = aws_secgroup1
        self.aws_secgroup2 = aws_secgroup2
        self.aws_secgroup3 = aws_secgroup3
        self.aws_vpc_id = aws_vpc_id

        self.client_short_name = client_short_name
        self.group = group
        self.env = env

        self.infra_vpn_pub = infra_vpn_pub
        self.infra_dest_cidr = infra_dest_cidr

        self.image_id = self.findImageId()   # find image ID for region
        self.short_region_name = self.getRegionShortName()
        self.vpn_instance_name = self.client_short_name + '-' + self.group + '-' + self.env + '-' + self.short_region_name + '-' + 'vpn1'

        self.ec2 = self.botoClient()
        self.data = self.createInstance()
        self.iid = self.getInstanceId()
        self.instance = self.createInstanceObject()
        self.waitForInstance()
        self.createInstanceTag()
        self.client = self.createClientSession()
        self.elastic_ip = self.allocateElasticIp()
        self.elastic_ip_defined = self.elastic_ip['PublicIp']
        self.allocation_id = self.getAllocationId()
        self.associateElasticIp()
        self.route_table_id = self.getRouteTableId()
        self.route_id = self.storeRouteId()
        self.disableSourceDestCheck()
        self.createRouteToInfra()



    #find centos image ID based on region
    def findImageId(self):
        if self.aws_region == Boto.regions[0]:         #Singapore
            return Boto.region_ami['ap-southeast-1']
        elif self.aws_region == Boto.regions[1]:       #Ireland
            return Boto.region_ami['eu-west-1']
        elif self.aws_region == Boto.regions[2]:       #Frankfurt
            return Boto.region_ami['eu-central-1']
        else:                                          #N.Virginia
            return Boto.region_ami['us-east-1']


    #get region short name based on region
    def getRegionShortName(self):
        if self.aws_region == Boto.regions[0]:        #Singapore
            return Boto.region_short['ap-southeast-1']
        elif self.aws_region == Boto.regions[1]:      #Ireland
            return Boto.region_short['eu-west-1']
        elif self.aws_region == Boto.regions[1]:      #Frankfurt
            return Boto.region_short['eu-central-1']
        else:                                         #N.Virginia
            return Boto.region_short['us-east-1']


    #create boto session and resource
    def botoClient(self):
        s = boto3.Session(region_name=self.aws_region,
                          aws_access_key_id=self.api_key,
                          aws_secret_access_key=self.api_secret)
        print "Creating boto client session and resource"
        return s.resource('ec2')


    #create instance
    def createInstance(self):
        data = None
        print "Creating %s instance in %s" % (self.vpn_instance_name, self.aws_az1)
        try:
            data = self.ec2.create_instances(
                DryRun=False,
                ImageId=self.image_id,
                MinCount=1,
                MaxCount=1,
                KeyName=self.aws_keypair,
                SecurityGroupIds=[
                    self.aws_secgroup1,
                    self.aws_secgroup2,
                    self.aws_secgroup3
                ],
                InstanceType=Boto.instance_type,
                Placement={
                    'AvailabilityZone': self.aws_az1,      # first az to launch instance in
                },
                SubnetId=self.aws_app_subnet1,
                DisableApiTermination=False,
                InstanceInitiatedShutdownBehavior='stop',
                EbsOptimized=False
            )

        except ClientError as e:
            print e.message
        return data


    #get instance ID
    def getInstanceId(self):
        iid = self.data[0].id
        print "Generated instance id: " + iid
        return iid


    #create ec2 instance object using instanceID
    def createInstanceObject(self):
        instance = self.ec2.Instance(id=self.iid)
        print "Created instance object"
        return instance


    #wait for instance to reach running state
    def waitForInstance(self):
        print "Instance in the process of reaching running state"
        self.instance.wait_until_running()



    #add instance tag
    def createInstanceTag(self):
        tag_name = self.instance.create_tags(
            DryRun=False,
            Tags=[
                {
                    'Key': 'Name',
                    'Value': self.vpn_instance_name
                },
            ]
        )
        print "Adding tag to the instance"


    #create boto client session
    def createClientSession(self):
        client = boto3.client('ec2',
                              region_name=self.aws_region,
                              aws_access_key_id=self.api_key,
                              aws_secret_access_key=self.api_secret)

        print "Created boto client session"
        return client


    #create elastic IP in vpc
    def allocateElasticIp(self):
        elastic_ip = self.client.allocate_address(
            DryRun=False,
            Domain='vpc'
        )

        print "Generated elastic ip: " + elastic_ip['PublicIp']
        return elastic_ip



    #store elastic ip allocation id
    def getAllocationId(self):
        allocation_id = self.elastic_ip['AllocationId']
        print "Stored allocation id: " + allocation_id
        return allocation_id


    #associate elastic IP with instance
    def associateElasticIp(self):
        associate_ip = self.client.associate_address(
            DryRun=False,
            InstanceId=self.iid,
            AllocationId=self.allocation_id,
            AllowReassociation=False
        )

        print "Associated elastic IP with instance"
        print associate_ip


    #add security rules to allow infra vpn
    def addSecGroups(self):
        print "Adding security rules to group: " + self.aws_secgroup1
        try:
            sec_rules = self.client.authorize_security_group_ingress(
                DryRun=False,
                GroupId=self.aws_secgroup1,
                IpProtocol='-1',                       # all
                FromPort=0,
                ToPort=65535,
                CidrIp=self.infra_vpn_pub            # source ip
            )

        except ClientError as e:
            print e.message



    #get primary route table id based on vpc id
    def getRouteTableId(self):
        route_table_id = None
        try:
            route_table_id = self.ec2.route_tables.filter(
                Filters=[
                    {'Name': 'association.main',
                     'Values': ["false"]
                     },
                    {'Name': 'vpc-id',
                     'Values': [self.aws_vpc_id]
                     }
                ]
            )
        except ClientError as e:
            print e.message
        print "Extracting primary route table ID"
        return route_table_id


    #stores route id from route_table_id inside an empty list
    def storeRouteId(self):
        route_id = []
        for route in self.route_table_id:
            route_id.append(route.id)

        print "Storing route ID inside a list"
        return route_id


    #disables source/dest check otherwise otherwise can't add instance as gateway in route table
    def disableSourceDestCheck(self):
        response = self.client.modify_instance_attribute(
            DryRun=False,
            InstanceId=self.iid,
            Attribute='sourceDestCheck',
            Value='False'
        )

        print 'Disable source/destination check: %s' % response


    #add route to infra vpn
    def createRouteToInfra(self):
        print "Creating route to infra vpn"
        try:
            add_route = self.client.create_route(
                DryRun=False,
                RouteTableId=self.route_id[0],
                DestinationCidrBlock=self.infra_dest_cidr,
                InstanceId=self.iid
            )

        except ClientError as e:
            print e.message



class SaltMinion(object):


    user = 'centos'
    port = 22


    def __init__(self, aws_vpn_instance, aws_keypair, aws_elastic_ip):

        self.aws_vpn_instance = aws_vpn_instance
        self.aws_key_pair = 'xxxxxxxx' + aws_keypair + '.pem'
        self.vpn_host = aws_elastic_ip

        self.clean_cache = 'yum -y clean all'
        self.replace_hostname = 'sed -i "1s/.*/{0}/" /etc/hostname'.format(self.aws_vpn_instance)
        self.replace_hosts = 'sed -i "1s/.*/127.0.0.1   {0} localhost localhost.localdomain/" /etc/hosts'.format(self.aws_vpn_instance)
        self.replace_network = 'echo "HOSTNAME={0}" >> /etc/sysconfig/network'.format(self.aws_vpn_instance)
        self.preserve_hostname = 'echo "preserve_hostname: true" >> /etc/cloud/cloud.cfg'
        self.install_epel = 'yum -y install epel-release'
        self.install_minion = 'yum -y install salt-minion'
        self.minion_master = 'echo "master: xxxxxxxxx" >> /etc/salt/minion'
        self.enable_minion = 'systemctl enable salt-minion'
        self.reboot_instance = 'sudo reboot 0'

        self.commands = [self.clean_cache,
                         self.replace_hostname,
                         self.replace_network,
                         self.replace_hosts,
                         self.preserve_hostname,
                         self.install_epel,
                         self.install_minion,
                         self.minion_master,
                         self.enable_minion]


    #change hostnames and install salt-minion
    def configMinion(self):
        print "Executing hostname and salt-minion commands"
        time.sleep(120)
        with settings(host_string=self.vpn_host, user=SaltMinion.user, key_filename=self.aws_key_pair):
            paramiko.util.log_to_file("/tmp/vpn_commands.log")
            for command in self.commands:
                sudo(command, user='root')



    #reboot system
    def rebootSystem(self):

        #create an SSH client
        client = paramiko.SSHClient()

        #key for connection
        k = paramiko.RSAKey.from_private_key_file(self.aws_key_pair)

        #add the remote server's SSH key automatically
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        #connect to the client
        client.connect(self.vpn_host, port=SaltMinion.port, username=SaltMinion.user, pkey=k)

        print "Rebooting instance"
        try:
            stdin, stdout, stderr = client.exec_command(self.reboot_instance, get_pty=True, timeout=130)
            print stdout.read()
        except Exception as e:
            print e
        finally:
            client.close()



    # aceept minion key
    def acceptMinionKey(self):
        print "Accepting minion key for: %s" % self.aws_vpn_instance
        p = subprocess.Popen(["salt-key -y -a" + self.aws_vpn_instance], stdout=subprocess.PIPE, shell=True)
        (output, err) = p.communicate()
        if output:
            print output
        else:
            print err




def main():

    obj = InputArgs()
    obj.getArgs()
    pod_name = obj.pod_name
    client_short_name = obj.client_short_name
    env = obj.env
    group = obj.group
    pod_ext = obj.pod_ext
    infra_dest_cidr = obj.infra_dest_cidr
    infra_vpn_pub = obj.infra_vpn_pub


    obj1 = PillarFile(pod_name, client_short_name, pod_ext, env)
    contents = obj1.openPillar()
    api_key = obj1.getApiKey(contents)
    #print api_key

    api_secret = obj1.getApiSecret(contents)
    #print api_secret

    aws_region = obj1.getRegion(contents)
    #print aws_region

    aws_profile = obj1.getAwsProfile(contents)
    #print aws_profile

    aws_cidr = obj1.getCidr(contents)
    #print aws_cidr

    aws_keypair = obj1.getKeyPair(contents)
    #print aws_keypair

    aws_az1 = obj1.getAz(contents)
    #print aws_az1

    aws_app_subnet1 = obj1.getSubnetId(contents, aws_az1)
    #print aws_app_subnet1

    aws_secgroup1 = obj1.getSecGroup1(contents)
    #print aws_secgroup1

    aws_secgroup2 = obj1.getSecGroup2(contents)
    #print aws_secgroup2

    aws_secgroup3 = obj1.getSecGroup3(contents)
    #print aws_secgroup3

    aws_vpc_id = obj1.getVpcId(contents)
    #print aws_vpc_id



    obj2 = Boto(api_key, api_secret, aws_region, aws_profile, aws_cidr, aws_keypair, aws_az1, aws_app_subnet1,
                aws_secgroup1, aws_secgroup2, aws_secgroup3, aws_vpc_id, client_short_name, group, env, infra_vpn_pub,
                infra_dest_cidr)
    obj2.botoClient()
    aws_vpn_instance = obj2.vpn_instance_name
    aws_elastic_ip = obj2.elastic_ip_defined



    obj3 = SaltMinion(aws_vpn_instance, aws_keypair, aws_elastic_ip)
    obj3.configMinion()
    obj3.rebootSystem()
    obj3.acceptMinionKey()


if __name__ == "__main__":
    main()


