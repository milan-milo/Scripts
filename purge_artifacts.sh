#!/usr/bin/env bash

############################### USAGE ########################
# Execution: will execute once a month
# Location: 
# If executed with empty repo variable - fails check and nothing occurs
##############################################################

#------------------------------------------------------------
# this program cannot be running in mac os, due to shell command
# 'date -d' support variant 
#------------------------------------------------------------

# --------------------------------------------------------------------
# Error variable
# --------------------------------------------------------------------

if [ $# -gt 0 ];then
   re='^[0-9]+$'
   if ! [[ $1 =~ $re ]] ; then
      echo "usage: $0 [days of file ages for removal|14]"
      echo
      exit 1
   else
      cutoff_days=$1
   fi
else
   cutoff_days=14
fi

ERROR_MSG=''
workenv=''

OSTYPE=$(uname | awk '{print tolower($0)}')
# check if it is running mac
if [[ "$OSTYPE" == "darwin" ]]; then
    alias date='gdate'
    echo " it is running on mac"
fi

if [ -z ${ENV_SALT:+x} ]
then
   ERROR_MSG="ENV_SALT is unset"; 
   echo $ERROR_MSG
   exit 1
else 
   echo "ENV_SALT was set as $ENV_SALT"; 
   workenv=$ENV_SALT
fi

if [ ! -f /etc/salt/master ]; then
   ERROR_MSG=" the program is designed to run on salt-master where ENV_SALT needs to be set! "
   echo $ERROR_MSG
   exit 1
   echo 
fi

# --------------------------------------------------------------------
# Do not purge npm-local-dev
# --------------------------------------------------------------------
if [ $workenv == 'dev' ]; then
   REPO="xxxxxxx"
elif [ $workenv == 'qa' ]; then
   REPO='xxxxxxx'
else
   REPO=''
   ERROR_MSG="ENV_SALT was not set correctly: $workenv."
   echo $ERROR_MSG
   exit 1
fi

# --------------------------------------------------------------------
# Artifactory Repo crential info, only for this purge purpose
# --------------------------------------------------------------------
username='xxxxxxx'
password='xxxxxxx'

#------------------------------------------------------------------------
# Create a 'touch' file on the file system that indicates when a script
# has started and stopped
# Example:
# /var/log/notifications/purge_artifacts/2016_06_23_$time_start
# /var/log/notifications/purge_artifacts/2016_06_23_$time_stop
#------------------------------------------------------------------------

root_dir='/var/log/notifications/'

xpath=$0
xbase=${xpath##*/}
# Example: xbase = "/srv/bin/purge_artifacts.sh and then sub_dir=purge_artifacts
sub_dir=${xbase%.*}

tag_dir=$root_dir$sub_dir
if [ ! -d $tag_dir ]; then
    echo " making the directory: $tag_dir "
    mkdir -p $tag_dir
fi

# creat start tag
date_file=`date +"%Y_%m_%d_%H_%M_%S"`
process_tag="$tag_dir/$date_file"
start_tick='_start'
touch $process_tag$start_tick

# START_TIME for minimum creation time in milliseconds of artifacts
# END_TIME for maximum creation time in milliseconds of artifacts

START_TIME=0
CUT_DAYS=$((24 * $cutoff_days * 3600 * 1000))

EPOCH_TIME=`date +%s%N | cut -b1-13`       #current time in milliseconds since epoch time
if [[ "$OSTYPE" == "darwin" ]]; then
    EPOCH_TIME=`gdate +%s%N | cut -b1-13`   #for Mac, current time in milliseconds since epoch time
fi

END_TIME=`expr $EPOCH_TIME - $CUT_DAYS`   #current time - 2 weeks in milliseconds

# REPO list for the repositories requiring purge (e.g. test-repo)

# loops through repos and removes artifacts 2 weeks or older

TEXT=''
if [ ! -z "$REPO" ]; then
  for i in $REPO; do
    echo 
    counter=0
    STEP=" purging two-week older files from repo $i: "
    echo -e $STEP
    RESULTS=$(curl -v -s -X GET -u $username:$password "https://testhost.com/artifactory/api/search/creation?from=$START_TIME&to=$END_TIME&repos=$i" 2> /dev/null | grep uri | awk '{print $3}' | tr -d ',$' | tr -d '\"')
    for RESULT in $RESULTS; do
        # echo "- fetching path from $RESULT"
        URI=$RESULT
        MSG=`curl -s -X GET -u $username:$password $URI`
        echo $MSG | grep 'errors'
        if [ $? == 0 ]; then
            echo " failed to read file from the repo: $i, go to next repo ..."
            break
        fi
        PATH_TO_FILE=$(echo $MSG | jq . | grep downloadUri | awk '{print $2}' | tr -d ',$' | tr -d '\"')
        echo $PATH_TO_FILE
        # delete artifact
        if [ ! -z $PATH_TO_FILE ]; then
            echo $PATH_TO_FILE | grep 'errors' 
            if [ $? == 0 ]; then
                echo " failed to read file from the repo: $i, go to next repo ..."
                ERROR_MSG=$ERROR_MSG" failed to read file from the repo: $i, go to next repo ..."
                break
            else
               echo "  - deleting the file: $PATH_TO_FILE "
               curl -X DELETE -u $username:$password $PATH_TO_FILE
               counter=$[$counter+1]
            fi
        else
           echo " no return for the retrieving call from the repo: $i"
           ERROR_MSG=$ERROR_MSG"  no return for the retrieving call from the repo: $i"
           break 
        fi
    done
    echo "                                        $counter file(s) deleted."
    STEP="$STEP                                   $counter file(s) deleted."
    TEXT="$TEXT\n$STEP\n"
   done
fi













