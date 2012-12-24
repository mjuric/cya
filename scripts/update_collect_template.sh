#!/bin/bash

test -d templates || { echo "Run this from root directory of the source package."; exit -1; }

cp /etc/cya/collect templates/collect.sample
