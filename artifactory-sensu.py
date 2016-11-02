#!/usr/bin/env python

__author__ = 'Milan Marcic'
__email__ = 'milan.marcic@symphony.com'
__copyright__ = 'Copyright 2016, Symphony'
__version__ = '0.1.0'


import sys
import subprocess
import re

artifactory_path = '/opt/'

STATE_OK = 0
#STATE_WARNING = 1
STATE_CRITICAL = 2
#STATE_UNKNOWN = 3


def trackProcess(process_name):
    ps = subprocess.Popen("ps -ef | grep "+process_name, shell=True, stdout=subprocess.PIPE)
    output = ps.stdout.read()
    ps.stdout.close()
    ps.wait()

    return output


def processRunning(process_name):
    output = trackProcess(process_name)

    if re.search(artifactory_path+process_name, output) is None:
        return False
    else:
        return True


def main():
    if processRunning('artifactory') == False:
        print("Artifactory is not running")
        sys.exit(STATE_CRITICAL)
    else:
        print("Artifactory is running!")
        sys.exit(STATE_OK)

if __name__ == '__main__':
    main()