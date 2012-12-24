#!/bin/bash

test -d templates || { echo "Run this from root directory of the source package."; exit -1; }

cat /etc/cya/backup | sed 's/BACKUP_ENCRYPTION_KEY='.*'/BACKUP_ENCRYPTION_KEY="XXXXXXXXX"/' > templates/backup.sample
