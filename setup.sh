#!/bin/sh

apt install git
apt install therion
apt install gimp
apt install texstudio
apt install libreoffice

cd ~
mkdir src

# install and configure KDE
apt install aptitude
aptitude install kde-standard

# install Vallpaper
cd ~/src
git clone https://github.com/lehklu/Vallpaper.git
cd Vallpaper/
./install.sh 

##### Install Signal
# NOTE: These instructions only work for 64 bit Debian-based
# Linux distributions such as Ubuntu, Mint etc.

# 1. Install our official public software signing key
wget -O- https://updates.signal.org/desktop/apt/keys.asc | gpg --dearmor > signal-desktop-keyring.gpg
cat signal-desktop-keyring.gpg | tee -a /usr/share/keyrings/signal-desktop-keyring.gpg > /dev/null

# 2. Add our repository to your list of repositories
echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/signal-desktop-keyring.gpg] https://updates.signal.org/desktop/apt xenial main' |\
  tee -a /etc/apt/sources.list.d/signal-xenial.list

# 3. Update your package database and install signal
apt update && apt install signal-desktop

#####

# texstudio custom spellcheck words. This file is normall found at ~/.config/texstudio/texstudioen_US.ign
mkdir -p ~/.config/texstudio/
cp texstudioen_US.ign ~/.config/texstudio/

# install spotify
curl -sS https://download.spotify.com/debian/pubkey_7A3A762FAFD4A51F.gpg | sudo gpg --dearmor --yes -o /etc/apt/trusted.gpg.d/spotify.gpg
echo "deb http://repository.spotify.com stable non-free" | sudo tee /etc/apt/sources.list.d/spotify.list
apt update && sudo apt install spotify-client
