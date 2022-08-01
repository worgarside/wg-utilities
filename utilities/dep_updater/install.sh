#!/bin/bash

repo_path=$(git rev-parse --show-toplevel)
sh_path=$(which sh)

#write out current crontab
crontab -l > tempcron
#echo new cron into cron file
echo "0 4 * * * ${sh_path} ${repo_path}/utilities/dep_updater/dep_updater.sh" >> tempcron
# install new cron file
crontab tempcron
rm tempcron
