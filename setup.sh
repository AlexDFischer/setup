apt install curl trash-cli qgis git python-is-python3 pip python3-full virtualenv \
    libssl-dev openssl libffi-dev bzip2-devel libncurses5-dev libncursesw5-dev libreadline-dev \
    libsqlite3-dev tk-dev python3-tk liblzma-dev \
    gimp therion survex keyd \
    libgdal-dev cmake

cat user-dirs.dirs > ~/.config/user-dirs.dirs

rm Videos
rm Templates
rm Public
rm Music
mv Documents documents
mv Downloads downloads
mv Desktop desktop

# old python version
curl https://pyenv.run | bash
cat pyenv > ~/.bashrc
source ~/.bashrc

# sinkholes
cd ~/src
git clone https://github.com/AlexDFischer/sinkholes.git
cd sinkholes

pyenv install 3.10.19
pyenv virtualenv 3.10.19 sinkholes
pyenv activate sinkholes
pip install -r requirements.txt

# keyd key mappings
cat keyd_default.conf | tee /etc/keyd/default.conf > /dev/null
systemctl enable --now keyd

echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc

# claude code
curl -fsSL https://claude.ai/install.sh | bash

## Signal
# NOTE: These instructions only work for 64-bit Debian-based
# Linux distributions such as Ubuntu, Mint etc.

# 1. Install our official public software signing key:
wget -O- https://updates.signal.org/desktop/apt/keys.asc | gpg --dearmor > signal-desktop-keyring.gpg;
cat signal-desktop-keyring.gpg | sudo tee /usr/share/keyrings/signal-desktop-keyring.gpg > /dev/null

# 2. Add our repository to your list of repositories:
wget -O signal-desktop.sources https://updates.signal.org/static/desktop/apt/signal-desktop.sources;
cat signal-desktop.sources | sudo tee /etc/apt/sources.list.d/signal-desktop.sources > /dev/null

# 3. Update your package database and install Signal:
sudo apt update && sudo apt install signal-desktop

## QGIS
mkdir -m755 -p /etc/apt/keyrings  # not needed since apt version 2.4.0 like Debian 12 and Ubuntu 22 or newer
wget -O /etc/apt/keyrings/qgis-archive-keyring.gpg https://download.qgis.org/downloads/qgis-archive-keyring.gpg

cat qgis.sources > /etc/apt/sources.list.d/qgis.sources

apt update
apt install qgis qgis-plugin-grass

git config --global init.defaultBranch master

cat .gitconfig > ~/.gitconfig