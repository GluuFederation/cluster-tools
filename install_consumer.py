# -*- coding: utf-8 -*-
# The MIT License (MIT)
#
# Copyright (c) 2015 Gluu
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

import logging
import subprocess
import sys

logger = logging.getLogger("installconsumer")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
fmt = logging.Formatter('[%(levelname)s] %(message)s')
ch.setFormatter(fmt)
logger.addHandler(ch)

def run(command):
    try:
        proc = subprocess.Popen(command, shell=True, bufsize=1)
        proc.communicate()
    except subprocess.CalledProcessError as exc:
        if exit_on_error:
            logger.error(exc)
            logger.error(exc.output)
            sys.exit(exc.returncode)

def install_prerequisites():
    logger.info("Prepareing machine")
    run('echo "deb http://repo.gluu.org/ubuntu/ trusty-devel main" > /etc/apt/sources.list.d/gluu-repo.list')
    run('curl http://repo.gluu.org/ubuntu/gluu-apt.key | apt-key add -')
    run('apt-get update')
    run('apt-get install -y linux-image-extra-$(uname -r)')
    run('apt-get install -y rng-tools')

def install_consumer():
    logger.info("Start installing consumer")
    run('apt-get install -y gluu-consumer')
    run('apt-get install -y gluu-agent')

def main():
    install_prerequisites()
    install_consumer()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print ""
        logger.info("Installation stopped by user")
