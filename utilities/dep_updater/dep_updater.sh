#!/bin/bash

log_path="/home/will/logs/dep_updater/$(date +20\%y-\%m-\%d).log"

# gets current branch
branch=$(git branch | sed -n -e 's/^\* \(.*\)/\1/p')

# git ... : lists all files changed on the remote
# sed ... : formats output to get just file names (based on strings followed by a pipe)
# tr ...  : replaces the spaces in the output of sed with newlines so we can iterate through
changed_files=$(git diff --stat "${branch}" origin/"${branch}" | sed -n -e 's/\([A-Za-z0-9_\-\.]*\) \| .*$/\1/p' | tr " " "\n")

echo "Changed files: ${changed_files}" >> "$log_path"

if [[ $changed_files == '' ]]; then
  # no files
  pipfiles_only=false
else
  # some files
  pipfiles_only=true
  # iterate through all changed files
  for file in $changed_files
  do
      # if the file doesn't match the regex then set the flag to false
      ! [[ "$file" =~  ^Pipfile(.lock)?$ ]] && pipfiles_only=false
  done
fi

mkdir -p ~/logs/dep_updater || :

#if only pipfiles have changed, then pull and install
if $pipfiles_only; then
  git pull >> "$log_path" 2>&1
  pipenv install --skip-lock >> "$log_path" 2>&1
else
  echo "Not running updates" >> "$log_path"
fi
