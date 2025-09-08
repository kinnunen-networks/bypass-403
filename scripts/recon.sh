#!/bin/bash

# Provide help function to the user if in trouble
show_help() {
  echo "Usage: $0 <domain> "
  echo
  echo "Arguments:"
  echo "domain:        String representation of target domain (example.com)"
  echo
  echo "Options:"
  echo "  -h, -help  Show this help message and exit"
}

check_parameter_usage() {
  if [ -z "$1" ]; then
    show_help
    exit 0
  fi
}

check_httpx() {
  if ! command -v httpx &> /dev/null; then
    echo "Error: httpx is not installed"
    echo "Install with: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest"
    exit 1
  fi
}

print_banner() { 
  figlet "Recon scanning initiated"
  echo "============================"
  echo "Starting the program"
  echo "============================"
  return 0
}

initialize_parameters() {
  target_file="datafor403.txt"
  fuzz_data="../fuzz-data/commonwords_fuzz.txt"
  fuzz_headers="fuzz-data/headers_fuzz.txt"
  fuzz_methods="fuzz-data/methods_fuzz.txt"
  path_file="fuzz-data/paths_to_bypass.txt"
  header_fuzz_result="headers_fuzz.txt"
  methods_fuzz_result="methods_fuzz.txt"
  combined_fuzz_result="combined_fuzz.txt"
  status_code=403
  ports="443,80,8080,8000"
}

create_dirs_and_files() {
  echo "Organizing results from: $(pwd)"

  mkdir -p scripts/scanning_result scripts/scanning_paths scripts/data scripts/fuzzer_result

  mv scripts/results_*.txt scripts/scanning_result/ 2>&1 || echo "No results files moved"
  mv scripts/paths_*.txt scripts/scanning_paths/ 2>&1 || echo "No paths files moved"
  mv scripts/*fuzz.txt scripts/fuzzer_result/ 2>&1 || echo "No fuzz files moved"
  mv scripts/datafor403.txt scripts/*.json scripts/data/ 2>&1 || echo "No json files moved"

  echo "Organization complete"
}

main() {
  check_parameter_usage "$1"
  check_httpx
  initialize_parameters
  print_banner

  echo -e "\e[33mPerforming scan on target: $1\e[0m"
  shodan domain -D "$1" -S

  if ls *json.gz 1> /dev/null 2>&1; then
    gzip -d *json.gz
    echo -e "\e[32mDecompressed JSON files successfully\e[0m"
  fi

  echo -e "\e[33mDone with fetching recon data from shodan\e[0m"

  echo -e "\e[33mFetching all IP-addresses and associated web applications running on the hosts\e[0m"

  jq -r '.ip_str' *hosts.json | uniq | httpx -mc $status_code -title -p $ports | awk '{print $1}' > "$target_file"
  echo -e "\e[32mDone with fetching all the ip-addresses associated with the host\e[0m"

  echo -e "\e[33mExtracting all hostnames and testing each URL using ffuff\e[0m"
  cat $target_file | while read url; do

  # Extract hostname
  host=$(echo "$url" | awk -F/ '{print $3}' | sed 's/:/_/g')
  outfile="results_${host}.txt"
  tmpfile=$(mktemp)
  echo -e "\e[33mTesting $url\e[0m" 

  ffuf -u "$url/FUZZ" -w "$fuzz_data" -t 50 -ac | tee -a "$tmpfile"
  # Make sure that the file exist and the file is > 0
  if [ -s "$tmpfile" ]; then
    cat "$tmpfile" >> "$outfile"
  fi

rm -f "$tmpfile"
done

echo -e "\e[32mDone with extracting all hostnames and testing each URL using ffuff\e[0m"

for file in results_*.txt; do
  if [ -e "$file" ]; then
    base=$(basename "$file" .txt)
    awk '{print $1}' "$file" > "paths_${base#results_}.txt"
  fi
done


script_dir="$(dirname "$0")"
  project_root="$(realpath "$script_dir/..")"
  cd "$project_root" || exit 1

echo -e "\e[33mStarting Python fuzzer from: $(pwd)\e[0m"
echo -e "\e[33mStarting fuzzing general headers\e[0m"

# Simple header fuzzing
python3 -m src.main -l "scripts/$target_file" -hf "$fuzz_headers" -o "scripts/$header_fuzz_result" -f "$path_file" -put 300 -dd 2 -th 4 -t 15
echo -e "\e[32mDone with fuzzing general headers\e[0m"

# Simple method fuzzing
echo -e "\e[33mStarting fuzzing general methods\e[0m"
python3 -m src.main -l "scripts/$target_file" -mf "$fuzz_methods" -o "scripts/$methods_fuzz_result" -f "$path_file" -put 300 -dd 2 -th 4 -t 15
echo -e "\e[33mDone with fuzzing general methods\e[0m"

# Combined header/method fuzzing
echo -e "\e[33mStarting fuzzing combined headers\e[0m"
python3 -m src.main -l "scripts/$target_file" -mf "$fuzz_methods" -hf "$fuzz_headers" -o "scripts/$combined_fuzz_result" -put 300 -dd 2 -f "$path_file" -th 4 -t 15
echo -e "\e[32mDone with fuzzing combined headers\e[0m"

# Change back to scripts directory
cd "$script_dir" || exit 1
create_dirs_and_files

echo -e "\e[32mDone with the scanning. Please see result in fuzzer_result/\e[0m"
}
main "$1"
