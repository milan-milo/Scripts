#!/usr/bin/env bash



#############################################################################
#
# author: Milan Marcic
#
# Description: script checks for ES watcher and license plugins and removes if present
#
#############################################################################


esPath='/opt/elasticsearch/'
clusterHealth='http://localhost:9200/_cluster/health?pretty=true'
service='elasticsearch'
pluginDirs='/opt/elasticsearch/plugins'
binPlugin='/opt/elasticsearch/bin/plugin'


echo ${HOSTNAME}


# check current ES cluster health

#get_cluster_health()
#{
#   clusterHealth = $(curl -XGET ${clusterHealth})
#   echo "${clusterHealth}" | tee /tmp/clusterhealth.out
#}



# checks if plugins exist, if not stops ES service and removes them

remove_plugins()
{
    if [ -d "${pluginDirs}/watcher/" ] || [ -d "${pluginDirs}/license/" ]
    then
        if systemctl status ${service} | grep 'running' > /dev/null
        then
            echo "${service} service running, stopping Elasticsearch"
            systemctl stop ${service}
            sleep 5

            echo "Removing watcher and license"
            ${binPlugin} remove watcher
            rm -rf "${pluginDirs}/license"
            sleep 3

            echo "Starting service"
            systemctl start ${service}
            sleep 3

        else
            echo "${service} is not running"

            echo "Removing watcher and license"
            ${binPlugin} remove watcher

            rm -rf "${pluginDirs}/license"
        fi
    else
        echo "watcher not installed on this instance"
        exit 0
    fi
}




# checks ES service started, if not starts it
# if fails shows ES cluster health

service_checks()
{
    if systemctl status ${service} | grep 'running' > /dev/null
    then
        echo "Elasticsearch is running"
        exit 0
    else
        echo "Elasticsearch isn't running, starting Elasticsearch"
        systemctl start ${service}
        sleep 5

        if systemctl status ${service} | grep 'running' > /dev/null
        then
            echo "Service started successfully"
            exit 0
        else
            echo "ES SERVICE DID NOT START ON ${HOSTNAME} - INVESTIGATE FURTHER"
        fi
    fi
}


#get_cluster_health
remove_plugins
service_checks








