#!/bin/bash
###############################################################################
# Copyright (c) 2019 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
###############################################################################

# This script will affine tasks to the platform cores of the host.
# This ensures that system processes are constrained to platform cores and will
# not run on cores with VMs/containers.

INITIAL_CONFIG_COMPLETE_FILE='/etc/platform/.initial_config_complete'
. /etc/init.d/task_affinity_functions.sh

log ()
{
    logger -p local1.info -t affine_tasks $@
    echo affine_tasks: "$@"
}

start ()
{
    log "Starting affine_tasks. Reaffining tasks to platform cores..."
    if [ ! -f ${INITIAL_CONFIG_COMPLETE_FILE} ]; then
        log "Initial Configuration incomplete. Skipping affining tasks."
        exit 0
    fi
    affine_tasks_to_platform_cores
    [[ $? -eq 0 ]] && log "Tasks re-affining done." || log "Tasks re-affining failed."
}

stop ()
{
    log "Stopping affine_tasks..."
}

status()
{
    :
}

reset()
{
    :
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart|force-reload|reload)
        stop
        start
        ;;
    status)
        status
        ;;
    reset)
        reset
        ;;
    *)
        echo "Usage: $0 {start|stop|force-reload|restart|reload|status|reset}"
        exit 1
        ;;
esac

exit 0