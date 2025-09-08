#!/bin/bash

# Basic cleanup script

echo -e "\e[33mStarting cleanup\e[0m"

# Just add whatever file to delete
FILES_TO_REMOVE=(
"dataforgeneralfuzzing.txt"
"data"
"scanning_paths"
"scanning_result"
"results_*"
"fuzzer_result"
"datafor403.txt"
)

for pattern in "${FILES_TO_REMOVE[@]}"; do
  for file in $pattern; do
    if [ -e "$file" ]; then
      rm -rf "$file"
      echo "Removed: $file"
    fi
  done
done

echo -e "\e[32mCleaning done\e[0m"
