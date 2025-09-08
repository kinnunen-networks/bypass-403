# Exit immediately if an error is encountered
set -e 

# Hygiene
echo -e "\e[33mUpdating package lists...\e[0m"
apt-get update -y
apt-get upgrade -y
echo -e "\e[32mUpdated the system succesfully\e[0m"

# Standard python packages
echo -e "\e[33mInstalling Python packages...\e[0m"
pip3 install --upgrade pip  # Hygiene
pip3 install -r requirements.txt #Install necessary packets for python

# Go tools used in the script
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest

echo -e "\e[32mAll dependencies installed successfully!\e[0m"
