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
import os
import time
import subprocess

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

WATCHED_DIRECTORY = "/opt/idp"
DOCKER_CERT_DIR = "/opt/gluu/docker/certs"
DATABASE_URI = "/var/lib/gluuengine/db/shared.json"

logger = logging.getLogger("fswatcher")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
fmt = logging.Formatter('[%(levelname)s] %(message)s')
ch.setFormatter(fmt)
logger.addHandler(ch)


def get_swarm_config():
    get_cert_path = lambda path: os.path.join(DOCKER_CERT_DIR, path)
    config = " ".join([
        "-H tcp://:3376",
        "--tlsverify",
        "--tlscacert={}".format(get_cert_path("ca.pem")),
        "--tlscert={}".format(get_cert_path("cert.pem")),
        "--tlskey={}".format(get_cert_path("key.pem")),
    ])
    return config


def safe_subprocess_exec(cmd):
    cmdlist = cmd.strip().split()
    ppn = subprocess.Popen(
        cmdlist,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = ppn.communicate()
    return out.strip(), err.strip(), ppn.returncode


class OxidpHandler(PatternMatchingEventHandler):
    patterns = ("*.xml", "*.config", "*.xsd", "*.dtd",)

    def on_any_event(self, event):
        logger.info("got {!r} event for {!r}".format(
            event.event_type, event.src_path,
        ))

    def on_modified(self, event):
        self.copy_path(event)

    def on_created(self, event):
        self.copy_path(event)

    def on_moved(self, event):
        self.copy_path(event)

    def copy_path(self, event):
        src = event.src_path
        dest = event.src_path

        if event.event_type == "moved":
            # source is the moved path
            src = event.dest_path
            dest = event.dest_path

        swarm_config = get_swarm_config()

        for container in get_oxidp_containers():
            logger.info(
                "found oxidp container with ID {}".format(container["cid"])
            )

            logger.info(
                "copying {} to {}:{}".format(src, container["cid"], dest)
            )
            _, err, returncode = safe_subprocess_exec(
                "docker {} cp {} {}:{}".format(
                    swarm_config, src, container["cid"], dest,
                )
            )

            if returncode != 0:
                logger.warn(
                    "error while copying {} to {}:{}; reason={}".format(
                        src, container["cid"], dest, err,
                    )
                )


def get_oxidp_containers(self):
    data = load_database()
    containers = [
        item for _, item in data["containers"].iteritems()
        if (item["type"] == "oxidp" and
            item["state"] in ("SUCCESS", "DISABLED",))
    ]
    return containers


def load_database():
    """Loads JSON-based database as Python object.
    """
    data = []

    try:
        with open(DATABASE_URI) as fp:
            data = json.loads(fp.read())
    except IOError:
        pass
    return data


if __name__ == "__main__":
    logger.info("running fswatcher on {}".format(WATCHED_DIRECTORY))

    if not os.path.exists(WATCHED_DIRECTORY):
        os.makedirs(WATCHED_DIRECTORY)

    try:
        observer = Observer()
        observer.schedule(
            OxidpHandler(),
            path=WATCHED_DIRECTORY,
            recursive=True,
        )
        observer.start()
    except OSError as exc:
        logger.error("unable to run fswatcher; reason={}".format(exc))
        observer.stop()
        logger.warn("fswatcher is stopped")
    else:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.warn("fswatcher is cancelled")
            observer.stop()
            logger.warn("fswatcher is stopped")
        observer.join()
