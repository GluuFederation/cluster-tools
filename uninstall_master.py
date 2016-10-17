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

logger = logging.getLogger("uninstallmaster")
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

def uninstall_master():
    logger.info("Start uninstalling master")
    run('apt-get purge -y gluu-master')
    run('apt-get purge -y gluu-flask')
    run('apt-get purge -y gluu-agent')
    run('apt-get purge -y gluu-cluster-webui')
    run('apt-get autoremove -y')

def main():
    uninstall_master()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print ""
        logger.info("Installation stopped by user")
