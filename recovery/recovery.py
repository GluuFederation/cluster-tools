#!/usr/bin/env python
# -*- coding: utf-8 -*-
# The MIT License (MIT)
#
# Copyright (c) 2016 Gluu
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import json
import logging
import socket
import subprocess
import sys
import time


DATABASE_URI = "/var/lib/gluuengine/db/shared.json"
RECOVERY_PRIORITY_CHOICES = {
    "ldap": 1,
    "oxauth": 2,
    "oxtrust": 3,
    "oxidp": 4,
    "nginx": 5,
}

logger = logging.getLogger("recovery")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
fmt = logging.Formatter('[%(levelname)s] %(message)s')
ch.setFormatter(fmt)
logger.addHandler(ch)


def load_database():
    """Loads JSON-based database as Python object.
    """
    data = []

    try:
        with open(DATABASE_URI) as fp:
            data = json.loads(fp.read())
    except IOError:
        logger.warn("unable to read {}".format(DATABASE_URI))
        sys.exit(1)
    else:
        return data


def get_current_cluster():
    """Gets a cluster.
    """
    data = load_database()

    clusters = [item for _, item in data.get("clusters", {}).iteritems()]
    try:
        cluster = clusters[0]
    except IndexError:
        cluster = {}
    return cluster


def get_node(hostname=""):
    """Gets node based.

    :param hostname: Hostname; if omitted, will check for FQDN or hostname
                     from socket connection.
    """
    data = load_database()

    nodes = [
        item for _, item in data.get("nodes", {}).iteritems()
        if item["name"] in (hostname, socket.getfqdn(), socket.gethostname(),)
    ]

    try:
        node = nodes[0]
    except IndexError:
        node = {}
    return node


def get_containers(node_id):
    """Gets all containers belong to certain node.

    :param node_id: ID of the node.
    """
    data = load_database()
    containers = []

    for _, item in data.get("containers", {}).iteritems():
        if item["node_id"] == node_id and item["state"] == "SUCCESS":
            # adds recovery_priority
            item["recovery_priority"] = RECOVERY_PRIORITY_CHOICES.get(
                item["type"], 0
            )
            containers.append(item)
    return containers


def safe_subprocess_exec(cmd):
    """Runs shell command safely.

    :param cmd: String of command.
    """
    cmdlist = cmd.strip().split()
    ppn = subprocess.Popen(
        cmdlist,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = ppn.communicate()
    return out.strip(), err.strip(), ppn.returncode


def container_stopped(container_id):
    """Checks whether a container is stopped.

    :param container_id: ID of the container assigned by docker daemon.
    """
    out, _, _ = safe_subprocess_exec("docker inspect {}".format(container_id))
    data = json.loads(out)
    return data[0]["State"]["Running"] is False


def container_exists(container_id):
    """Checks whether a container exists.

    :param container_id: ID of the container assigned by docker daemon.
    """
    out, _, _ = safe_subprocess_exec("docker inspect {}".format(container_id))
    data = json.loads(out)
    return len(data) > 0


def restart_container(container_id):
    """Restarts a container regardless its state.

    :param container_id: ID of the container assigned by docker daemon.
    """
    return safe_subprocess_exec("docker restart {}".format(container_id))


def add_dns(container_id, hostname):
    """Adds DNS entry to weavedns.

    :param container_id: ID of the container assigned by docker daemon.
    :param hostname: Hostname that should be added into weavedns.
    """
    return safe_subprocess_exec("weave dns-add {} -h {}".format(
        container_id, hostname
    ))


def detach_ip(container_id):
    """Detaches container from weave network.

    :param container_id: ID of the container assigned by docker daemon.
    """
    safe_subprocess_exec("weave detach {}".format(container_id))


def weave_component_ready(name):
    delay = 10
    max_retry = 6
    retry_attempt = 0
    component_ready = False

    while retry_attempt < max_retry:
        if container_stopped(name):
            logger.warn("{} is not ready; retrying ...".format(name))
            time.sleep(delay)
            retry_attempt += 1
        else:
            component_ready = True
            break
    return component_ready


def recover_containers(node_id, ox_cluster_hostname):
    """Recovers all containers.

    :param node_id: ID of the node.
    :param ox_cluster_hostname: Name of IDP server.
    """
    containers = sorted(get_containers(node_id),
                        key=lambda x: x["recovery_priority"])

    for container in containers:
        if not container_exists(container["cid"]):
            continue

        if not container_stopped(container["cid"]):
            # no need to restart already running container
            logger.info("{} container {} already running; skipping ...".format(
                container["type"], container["name"],
            ))
            continue

        logger.info("restarting {} container {}".format(
            container["type"], container["name"]
        ))
        _, err, returncode = restart_container(container["cid"])
        if returncode != 0:
            # if restarting failed, continue to other containers
            # and let this specific container stopped so we can
            # retry the recovery process again
            logger.warn(
                "something is wrong while restarting "
                "{} container {}; reason={}".format(
                    container["type"], container["name"], err
                )
            )
            continue

        # DISABLED container must be detached from weave network
        if container["state"] == "DISABLED":
            detach_ip(container["cid"])
            continue

        # manually re-adding DNS entry
        logger.info("adding DNS entry {} for {} container {}".format(
            container["hostname"], container["type"], container["name"]
        ))
        add_dns(container["cid"], container["hostname"])

        if container["type"] in ("oxauth", "oxtrust", "oxeleven",):
            add_dns(container["cid"], "{}.weave.local".format(container["type"]))  # noqa

        # if cluster hostname contains `weave.local` suffix, this extra DNS
        # entry will be added into weavedns; pretty useful for setup which
        # doesn't have resolvable domain name
        if container["type"] == "nginx":
            add_dns(container["cid"], ox_cluster_hostname)


if __name__ == "__main__":
    try:
        logger.info("starting recovery process for current node; "
                    "this may take a while ...")

        cluster = get_current_cluster()
        if not cluster:
            logger.warn("unable to find any cluster")
            sys.exit(1)

        node = get_node()
        if not node:
            logger.warn("unable to find node matches existing hostname")
            sys.exit(1)

        if not weave_component_ready("weave"):
            logger.error("aborting recovery process due to weave being "
                         "not ready; please try again later ...")
            sys.exit(1)

        if not weave_component_ready("weaveproxy"):
            logger.error("aborting recovery process due to weaveproxy being "
                         "not ready; please try again later ...")
            sys.exit(1)

        if not weave_component_ready("weaveplugin"):
            logger.error("aborting recovery process due to weaveplugin being "
                         "not ready; please try again later ...")
            sys.exit(1)

        time.sleep(10)

        recover_containers(node.get("id"), cluster.get("ox_cluster_hostname"))
        logger.info("recovery process for current node is finished")
    except KeyboardInterrupt:
        logger.warn("recovery process aborted by user")
    sys.exit(0)
