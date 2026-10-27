#!/usr/bin/env bash
# Debian 13 amd64 workstation setup. Run through sudo from your own account.
# PORTABILITY: This is intentionally not a generic Debian/Ubuntu installer.
# Search for PORTABILITY below before adapting the release/architecture guard.
# All apt-get/dpkg commands require a compatible apt-based host; third-party
# repositories, package names and desktop APIs must be checked independently.
set -Eeuo pipefail

usage() {
    cat <<'HELP'
Usage: sudo bash setup.sh (--personal | --work) [OPTIONS]

System packages/services run as root; personal tools/settings as the sudo caller.
Work excludes Signal, QGIS, Wine, cave tools, and Git identity setup.
Signal/QGIS cannot be enabled with --work. Disabling a component does not uninstall it.

  --with-NAME / --without-NAME   Override a profile default
  --only=NAME,NAME               Start with only these components enabled
  --yes                         Answer yes to apt prompts
  --dry-run                     Preview components and panel pins; make no changes
  -h, --help                    Show help

Components:
  base, graphics, latex, cave, uv, oomd, zram, folders, wine, keyd,
  shell-path, claude, codex, signal, qgis, git, git-identity, spotify,
  anaconda, python-packages, prince, vscode, date-locale, panel, shortcuts

Base includes shared build/Python tools, Chromium, Cheese, and GParted.
Each component installs its own runtime prerequisites even without base.
Panel pins are replaced in the requested order; disabled optional apps are omitted.
Anaconda is installed in ~/anaconda3. Scientific packages use ~/.venvs/base
with uv and activate automatically in new interactive Bash terminals.
HELP
}

components=(base graphics latex cave uv oomd zram folders wine keyd shell-path
            claude codex signal qgis git git-identity spotify anaconda
            python-packages prince vscode date-locale panel shortcuts)
declare -A enabled=() overrides=()
profile='' dry_run=false assume_yes=false only=''

fail() { echo "Error: $*" >&2; exit 1; }
has() { [[ ${enabled[$1]:-0} == 1 ]]; }
valid_component() {
    local component
    for component in "${components[@]}"; do
        if [[ $component == "$1" ]]; then return 0; fi
    done
    return 1
}
parse_args() {
    local arg selected name value component
    for arg in "$@"; do
        case "$arg" in
            --personal|--work)
                selected=${arg#--}
                [[ -z $profile || $profile == "$selected" ]] || fail 'Choose exactly one profile.'
                profile=$selected ;;
            --with-*|--without-*)
                name=${arg#--with-}; value=1
                if [[ $arg == --without-* ]]; then name=${arg#--without-}; value=0; fi
                valid_component "$name" || fail "Unknown component: $name"
                overrides[$name]=$value ;;
            --only=*)
                only=${arg#--only=}
                [[ -n $only && $only != ,* && $only != *, && $only != *,,* ]] || fail '--only needs comma-separated component names.' ;;
            --yes) assume_yes=true ;;
            --dry-run) dry_run=true ;;
            -h|--help) usage; exit 0 ;;
            *) fail "Unknown option: $arg" ;;
        esac
    done
    [[ -n $profile ]] || fail 'Choose --personal or --work (see --help).'
    for component in "${components[@]}"; do
        enabled[$component]=1
        [[ -z $only ]] || enabled[$component]=0
    done
    if [[ -n $only ]]; then
        local -a selected_components
        IFS=, read -r -a selected_components <<< "$only"
        for component in "${selected_components[@]}"; do
            valid_component "$component" || fail "Unknown component: $component"
            enabled[$component]=1
        done
    elif [[ $profile == work ]]; then
        for component in signal qgis wine cave git-identity; do enabled[$component]=0; done
    fi
    for component in "${!overrides[@]}"; do enabled[$component]=${overrides[$component]}; done
    if [[ $profile == work ]] && { has signal || has qgis; }; then
        fail 'Signal and QGIS are unavailable in the work profile.'
    fi
}

# Download to fresh temporary files. Never execute a partially downloaded installer.
download() { curl --fail --show-error --location --retry 3 "$1" --output "$2"; }
apt_install() { apt-get install "${apt_options[@]}" -- "$@"; }
install_config() {
    local source=$1 target=$2
    install -d -m 0755 "$(dirname -- "$target")"
    if [[ -f $target ]] && cmp -s "$source" "$target"; then return; fi
    if [[ -f $target && ! -e $target.before-system-setup ]]; then
        cp -p -- "$target" "$target.before-system-setup"
    fi
    install -m 0644 "$source" "$target.system-setup.tmp"
    mv -f -- "$target.system-setup.tmp" "$target"
}
write_config() {
    cat > "$work_directory/config"
    install_config "$work_directory/config" "$1"
}
install_key() {
    download "$1" "$work_directory/key"
    if [[ ${3:-armored} == armored ]]; then
        gpg --batch --yes --dearmor --output "$work_directory/key.gpg" "$work_directory/key"
    else
        cp "$work_directory/key" "$work_directory/key.gpg"
    fi
    # Reject an HTML error page or other invalid key before touching apt config.
    gpg --batch --show-keys "$work_directory/key.gpg" >/dev/null
    install_config "$work_directory/key.gpg" "$2"
}

queue_desktop_task() {
    local name=$1 helper=$2
    shift 2
    as_user mkdir -p "$setup_home/.local/lib/system-setup" "$setup_home/.config/autostart"
    # Redirections happen after dropping privileges, including all parent dirs.
    as_user tee "$setup_home/.local/lib/system-setup/$helper" < "$script_directory/$helper" >/dev/null
    as_user chmod 0755 "$setup_home/.local/lib/system-setup/$helper"
    local program=/usr/bin/bash
    [[ $helper != *.py ]] || program=/usr/bin/python3
    as_user /usr/bin/python3 - "$name" "$program" "$setup_home/.local/lib/system-setup/$helper" "$@" <<'PY'
import os, pathlib, sys
name, *args = sys.argv[1:]
def quote(value):
    # Desktop Entry Exec quoting, including field-code and string escapes.
    value = value.replace('%', '%%')
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\' + char)
    return '"' + value + '"'
command = ' '.join(map(quote, args)).replace('\\', '\\\\')
path = pathlib.Path(os.environ['XDG_CONFIG_HOME']) / 'autostart' / f'setup-kde-{name}.desktop'
path.write_text('[Desktop Entry]\nType=Application\nName=Configure KDE ' + name +
                '\nExec=' + command + '\nOnlyShowIn=KDE;\nTerminal=false\n')
PY
    if [[ -S /run/user/$setup_uid/bus ]] && as_user "$program" "$setup_home/.local/lib/system-setup/$helper" "$@"; then
        echo "Applied KDE $name."
    else
        echo "KDE $name is queued for the next login (entry retained until successful)."
    fi
}

main() {
    parse_args "$@"
    if "$dry_run"; then
        echo "Profile: $profile"
        local component
        for component in "${components[@]}"; do if has "$component"; then echo "  $component"; fi; done
        if has panel; then
            echo 'Panel: Dolphin -> Konsole'
            if has qgis; then echo '  -> QGIS'; fi
            echo '  -> Firefox (existing installation)'
            if has vscode; then echo '  -> VSCode'; fi
            if has spotify; then echo '  -> Spotify'; fi
        fi
        return
    fi
    (( EUID == 0 )) || fail 'Run through sudo from the account being configured.'
    export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    # sudo -E/-H must not redirect root-owned package-manager state into user files.
    HOME=$(getent passwd 0 | cut -d: -f6)
    export HOME
    export XDG_CONFIG_HOME="$HOME/.config" XDG_DATA_HOME="$HOME/.local/share" XDG_CACHE_HOME="$HOME/.cache"
    script_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
    source "$script_directory/setup-user.sh"
    init_setup_user
    source /etc/os-release
    # PORTABILITY: Deliberately rejects Ubuntu, newer Debian, and non-amd64 hosts.
    # Changing this guard alone does not make the repository/package pins valid.
    [[ $ID == debian && $VERSION_ID == 13 && $(dpkg --print-architecture) == amd64 ]] ||
        fail 'This script supports Debian 13 (trixie), amd64 only.'
    # PORTABILITY: Requires booted systemd; not a container/chroot or non-systemd derivative.
    [[ -d /run/systemd/system ]] || fail 'A booted systemd installation is required.'
    if has python-packages && ! has uv && [[ ! -x $setup_home/.local/bin/uv ]]; then
        fail 'python-packages needs uv enabled, or an existing ~/.local/bin/uv.'
    fi
    for component in setup-home.py kde-panel.sh kde-shortcuts.py keyd_default.conf qgis.sources; do
        [[ -r $script_directory/$component ]] || fail "Missing supporting file: $component"
    done
    apt_options=()
    if "$assume_yes"; then apt_options=(-y); fi
    work_directory=$(mktemp -d /tmp/system-setup.XXXXXXXX)
    chmod 0755 "$work_directory" # _apt needs to read downloaded .deb packages.
    trap 'rm -rf -- "$work_directory"' EXIT
    trap 'echo "Setup failed at line $LINENO; stopping before subsequent steps." >&2' ERR
    export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    # Common bootstrap tools; components install additional prerequisites below.
    apt-get update
    apt_install ca-certificates curl gnupg python3

    if has base; then
        # PORTABILITY: Package names are checked against Debian 13. Ubuntu's
        # chromium package may install a Snap; other releases may rename packages.
        apt_install trash-cli git python-is-python3 python3-pip python3-full python3-venv virtualenv \
            build-essential pkg-config libssl-dev openssl libffi-dev libbz2-dev libncurses-dev \
            libreadline-dev libsqlite3-dev tk-dev python3-tk liblzma-dev libgdal-dev cmake \
            chromium cheese gparted
    fi
    if has graphics; then apt_install gimp freecad klayout; fi
    if has latex; then apt_install latexmk texlive-full; fi
    if has cave; then apt_install therion survex; fi
    if has uv; then
        download https://astral.sh/uv/install.sh "$work_directory/uv.sh"
        as_user sh -s < "$work_directory/uv.sh"
    fi
    if has oomd; then
        # PORTABILITY: The effective OOM policy comes from Debian 13's vendor
        # unit drop-ins; another distro/release may ship a different or no policy.
        apt_install systemd-oomd
        # Debian supplies user@.service memory-pressure policy and oomd defaults.
        # Keep that distribution policy instead of inventing aggressive thresholds.
        systemctl enable --now systemd-oomd
    fi
    if has zram; then
        # PORTABILITY: This config/service belongs to zram-tools, not Ubuntu's
        # zram-config or systemd-zram-generator. Do not enable competing managers.
        apt_install zram-tools
        write_config /etc/default/zramswap <<'CONFIG'
# Managed by system-setup: compressed swap up to 50% of RAM; allocated on demand.
ALGO=lz4
PERCENT=50
PRIORITY=100
CONFIG
        systemctl enable --now zramswap.service
        # Do not swap off an in-use device on a rerun; new settings apply next boot.
    fi
    if has folders; then as_user /usr/bin/python3 "$script_directory/setup-home.py" folders; fi
    if has wine; then
        # PORTABILITY: amd64+i386 multiarch Wine packages must exist in the host
        # repositories; this step does not apply to ARM or an i386-free release.
        dpkg --add-architecture i386
        apt-get update
        apt_install wine wine32:i386
    fi
    if has keyd; then
        # PORTABILITY: keyd is packaged in Debian 13; availability differs in older
        # Debian/Ubuntu releases. The configuration assumes keyd's current syntax.
        apt_install keyd
        install_config "$script_directory/keyd_default.conf" /etc/keyd/default.conf
        systemctl enable keyd
        systemctl restart keyd
    fi
    if has shell-path; then as_user /usr/bin/python3 "$script_directory/setup-home.py" shell-path; fi
    if has claude; then
        download https://claude.ai/install.sh "$work_directory/claude.sh"
        as_user bash -s < "$work_directory/claude.sh"
    fi
    if has codex; then
        apt_install nodejs npm
        env -u NPM_CONFIG_PREFIX -u npm_config_prefix npm install --global --prefix /usr/local @openai/codex
    fi
    if has signal; then
        install_key https://updates.signal.org/desktop/apt/keys.asc /usr/share/keyrings/signal-desktop-keyring.gpg
        download https://updates.signal.org/static/desktop/apt/signal-desktop.sources "$work_directory/signal.sources"
        install_config "$work_directory/signal.sources" /etc/apt/sources.list.d/signal-desktop.sources
        apt-get update
        apt_install signal-desktop
    fi
    if has qgis; then
        # PORTABILITY: qgis.sources pins trixie/amd64. Ubuntu needs its own supported
        # suite/repository; never reuse the trixie suite on a newer Debian release.
        install_key https://download.qgis.org/downloads/qgis-archive-keyring.gpg /etc/apt/keyrings/qgis-archive-keyring.gpg binary
        install_config "$script_directory/qgis.sources" /etc/apt/sources.list.d/qgis.sources
        apt-get update
        apt_install qgis qgis-plugin-grass
    fi
    if has git || has git-identity; then apt_install git; fi
    if has git; then
        as_user git config --global init.defaultBranch master
        as_user git config --global pull.rebase false
    fi
    if has git-identity; then
        as_user git config --global user.name 'Alex Fischer'
        as_user git config --global user.email alexander.fischer3@gmail.com
    fi
    if has spotify; then
        # PORTABILITY: Spotify's upstream repository here is amd64-only; its
        # stable suite is a vendor label, not the Debian release codename.
        install_key https://download.spotify.com/debian/pubkey_5384CE82BA52C83A.asc /etc/apt/keyrings/spotify.gpg
        write_config /etc/apt/sources.list.d/spotify.sources <<'CONFIG'
Types: deb
URIs: https://repository.spotify.com
Suites: stable
Components: non-free
Architectures: amd64
Signed-By: /etc/apt/keyrings/spotify.gpg
CONFIG
        if [[ -f /etc/apt/sources.list.d/spotify.list ]] &&
           [[ $(cat /etc/apt/sources.list.d/spotify.list) == 'deb https://repository.spotify.com stable non-free' ]]; then
            if [[ ! -e /etc/apt/sources.list.d/spotify.list.before-system-setup ]]; then
                cp -p /etc/apt/sources.list.d/spotify.list /etc/apt/sources.list.d/spotify.list.before-system-setup
            fi
            rm -- /etc/apt/sources.list.d/spotify.list
        fi
        apt-get update
        apt_install spotify-client
    fi
    if has anaconda; then
        # PORTABILITY: This pinned Linux x86_64 installer and SHA256 are a pair.
        # ARM needs a different installer/checksum; verify OS support on new releases.
        as_user bash -seu <<'USER_SCRIPT'
if [[ ! -x $HOME/anaconda3/bin/conda ]]; then
    if [[ -e $HOME/anaconda3 ]]; then
        echo 'An incomplete ~/anaconda3 exists; inspect it before reinstalling.' >&2
        exit 1
    fi
    # Constructor installers require a .sh filename even when invoked with bash.
    installer=$(mktemp /tmp/anaconda-installer.XXXXXXXX.sh)
    trap 'rm -f -- "$installer"' EXIT
    curl -fSL --retry 3 https://repo.anaconda.com/archive/Anaconda3-2025.12-2-Linux-x86_64.sh -o "$installer"
    # SHA256 from https://repo.anaconda.com/archive/ (pinned installer version).
    echo "57b2b48cc5b8665e25fce7011f0389d47c1288288007844b3b1ba482d4f39029  $installer" | sha256sum --check
    bash "$installer" -b -p "$HOME/anaconda3"
fi
"$HOME/anaconda3/bin/conda" init bash
USER_SCRIPT
    fi
    if has python-packages; then
        # Install using uv's interpreter/environment, never the system's pip.
        as_user bash -seu <<'USER_SCRIPT'
uv="$HOME/.local/bin/uv"
environment="$HOME/.venvs/base"
if [[ ! -e $environment ]]; then
    "$uv" venv --python 3.12 "$environment"
elif [[ ! -x $environment/bin/python ]]; then
    echo 'An incomplete ~/.venvs/base exists; inspect it before retrying.' >&2
    exit 1
fi
"$uv" pip install --python "$environment/bin/python" numpy scipy matplotlib pandas ipympl gdsfactory
USER_SCRIPT
        # Conda remains available on demand; uv's base is the terminal default.
        if [[ -x $setup_home/anaconda3/bin/conda ]]; then
            as_user "$setup_home/anaconda3/bin/conda" config --set auto_activate_base false
        fi
        as_user /usr/bin/python3 "$script_directory/setup-home.py" base-env
        echo 'Scientific Python ready; new interactive Bash terminals activate ~/.venvs/base.'
    fi
    if has prince; then
        # PORTABILITY: This binary is explicitly built for Debian 13 amd64.
        # Select a vendor build for Ubuntu/new Debian instead of reusing this URL.
        download https://www.princexml.com/download/prince_16.2-1_debian13_amd64.deb "$work_directory/prince.deb"
        chmod 0644 "$work_directory/prince.deb"
        apt_install "$work_directory/prince.deb"
    fi
    if has vscode; then
        # PORTABILITY: Microsoft's stable suite supports multiple apt-based hosts,
        # but this entry selects amd64 only; check vendor support for a new host.
        install_key https://packages.microsoft.com/keys/microsoft.asc /usr/share/keyrings/microsoft.gpg
        write_config /etc/apt/sources.list.d/vscode.sources <<'CONFIG'
Types: deb
URIs: https://packages.microsoft.com/repos/code
Suites: stable
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/microsoft.gpg
CONFIG
        apt-get update
        apt_install code
    fi
    if has date-locale; then
        # PORTABILITY: Debian locale generation plus KDE Plasma 6 configuration.
        # Plasma 5 uses different tool/package names; GNOME ignores plasma-localerc.
        # Qt's locale date formats should be rechecked after a major Qt upgrade.
        apt_install locales libkf6config-bin
        # Build only the supported locale; don't run locale-gen on invalid en_SE entries.
        if ! grep -Eq '^en_CA\.UTF-8[[:space:]]+UTF-8[[:space:]]*$' /etc/locale.gen; then
            echo 'en_CA.UTF-8 UTF-8' >> /etc/locale.gen
        fi
        localedef -i en_CA -f UTF-8 en_CA.UTF-8
        as_user mkdir -p "$setup_home/.config"
        as_user bash -seu <<'USER_SCRIPT'
config="$HOME/.config/plasma-localerc"
if [[ -f $config && ! -e $config.before-system-setup ]]; then
    cp -p -- "$config" "$config.before-system-setup"
fi
USER_SCRIPT
        as_user kwriteconfig6 --file "$setup_home/.config/plasma-localerc" --group Formats --key LC_TIME en_CA.UTF-8
        echo 'Date locale configured. Log out and back in to apply.'
    fi
    if has panel; then
        # PORTABILITY: Plasma 6 + qdbus-qt6 package names and a bottom task manager
        # are assumed. GNOME/other desktops need a separate pinning implementation.
        apt_install qdbus-qt6
        queue_desktop_task panel kde-panel.sh "$profile" "${enabled[qgis]}" "${enabled[vscode]}" "${enabled[spotify]}"
    fi
    if has shortcuts; then
        # PORTABILITY: KDE KGlobalAccel/KWin action IDs and Qt 6 Python bindings.
        # Not GNOME shortcuts; validate API/action IDs on other Plasma versions.
        apt_install dolphin python3-dbus python3-pyqt6
        queue_desktop_task shortcuts kde-shortcuts.py
    fi
    echo 'Setup completed.'
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then main "$@"; fi
