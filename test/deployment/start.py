# -*- coding: utf-8 -*-
# Copyright (c) 2015 Gluu
#
# All rights reserved.

import os
from subprocess import call
from subprocess import check_output

#util
def run(str_cmd):
    cmd_token = str_cmd.strip().split()
    return call(cmd_token)

# install and run controler node services
def docker():
    return os.path.isfile('/usr/bin/docker')

def pull_image(str_type):
    cmd = 'docker images %s --format {{.Repository}}' % str_type
    found = check_output(cmd.strip().split()).strip()
    if found == str_type:
        print 'localy found {}'.format(found)
        return 0
    cmd = 'docker pull {}'.format(str_type)
    return run(cmd)

def run_mongo():
    cmd = 'docker run -d --name mongo -v /var/lib/gluuengine/db/mongo:/data/db mongo'
    run(cmd)

def run_gluuengine():
    cmd = 'docker run -d -p 127.0.0.1:8080:8080 --name gluuengine \
            -v /var/log/gluuengine:/var/log/gluuengine \
            -v /var/lib/gluuengine:/var/lib/gluuengine \
            -v /var/lib/gluuengine/machine:/root/.docker/machine \
            --link mongo:mongo \
            gluuengine'
    run(cmd)

def run_gluuwebui():
    cmd = 'docker run -d -p 127.0.0.1:8800:8800 --name gluuwebui \
            --link gluuengine:gluuengine gluuwebui'
    run(cmd)

def is_running(str_type):
    cmd = 'docker ps -f name=%s --format {{.Names}}' % str_type
    found = check_output(cmd.strip().split()).strip()
    return '{} running'.format(str_type) if found == str_type else '{} not running'.format(str_type)


# deploy a basic cluster (discovery+master+worker_1)
# create a cluster
# create a provider
# create discovery node
# create master node
# create worker node
# create LDAP on master
# create oxauth on master
# create oxtrust on master
# create nginx on master
# create ldap on worker
# create oxauth on worker
# create nginx on worker

# test besic oxtrust login

def main():
    if not docker():
        return
    con_list = ['mongo', 'gluuengine', 'gluuwebui']
    map(pull_image, con_list)
    run_mongo()
    run_gluuengine()
    run_gluuwebui()
    run_status_list = map(is_running, con_list)
    for status in run_status_list:
        print status

if __name__ == '__main__':
    main()