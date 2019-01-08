#!/bin/bash
set -x
TORQUE=/var/spool/torque

# Kill any existing servers
/etc/init.d/torque-mom stop
/etc/init.d/torque-scheduler stop
/etc/init.d/torque-server stop

# Create and shut down the TORQUE server in order to set up the directories
pbs_server -f -t create
killall pbs_server

## Start the TORQUE queue authentication daemon
#server=$(hostname -f)
server=localhost

# Do I need these?
#echo ${server} > /etc/torque/server_name
echo ${server} > ${TORQUE}/server_name
echo ${server} > ${TORQUE}/server_priv/acl_svr/acl_hosts
echo root@${server} > ${TORQUE}/server_priv/acl_svr/operators
echo root@${server} > ${TORQUE}/server_priv/acl_svr/managers

# Update hosts
#echo "127.0.0.1 ${server}" >> /etc/hosts

# Add host as a compute node
echo "${server}" > ${TORQUE}/server_priv/nodes

# Set up client configuration
echo ${server} > ${TORQUE}/mom_priv/config

# Restart server
/etc/init.d/torque-server start
/etc/init.d/torque-scheduler start
/etc/init.d/torque-mom start

# Server config
qmgr -c "set server scheduling = true"
qmgr -c "set server keep_completed = 300"
qmgr -c "set server mom_job_sync = true"

# Default queue
qmgr -c "create queue batch"
qmgr -c "set queue batch queue_type = execution"
qmgr -c "set queue batch started = true"
qmgr -c "set queue batch enabled = true"
qmgr -c "set queue batch resources_default.walltime = 3600"
qmgr -c "set queue batch resources_default.nodes = 1"
qmgr -c "set server default_queue = batch"

qmgr -c "set server submit_hosts = ${server}"
qmgr -c "set server allow_node_submit = true"

# Check the available nodes
pbsnodes
