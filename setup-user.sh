# PORTABILITY: Linux/util-linux runuser, passwd/getent and systemd user-bus paths.
# Shell configuration targets Bash; other login shells need their own setup.
# Shared privilege boundary for setup.sh. Source this file; do not execute it.
init_setup_user() {
    setup_user=${SUDO_USER:-}
    if [[ -z "$setup_user" || "$setup_user" == root ]]; then
        echo 'Run setup through sudo from the account being configured.' >&2
        return 1
    fi
    local account
    account=$(getent passwd "$setup_user") || return 1
    IFS=: read -r setup_user _ setup_uid setup_gid _ setup_home _ <<< "$account"
    if [[ "$setup_uid" == 0 || "$setup_home" != /* || ! -d "$setup_home" ]]; then
        echo 'The sudo caller must be a non-root user with an existing home directory.' >&2
        return 1
    fi
    setup_group=$(id -gn "$setup_user") || return 1
}

as_user() {
    # Do not leak root's HOME, XDG paths, Python environment, or tool config.
    # Start in the user's home and supply a predictable PATH without sourcing
    # interactive shell startup files. Arguments retain their original quoting.
    runuser -u "$setup_user" -- env -i \
        HOME="$setup_home" USER="$setup_user" LOGNAME="$setup_user" SHELL=/bin/bash \
        LANG=C.UTF-8 TERM="${TERM:-dumb}" \
        XDG_CONFIG_HOME="$setup_home/.config" XDG_DATA_HOME="$setup_home/.local/share" \
        XDG_CACHE_HOME="$setup_home/.cache" XDG_RUNTIME_DIR="/run/user/$setup_uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$setup_uid/bus" \
        PATH="$setup_home/.local/bin:/usr/local/bin:/usr/bin:/bin" \
        /bin/bash --noprofile --norc -c 'cd -- "$HOME" && exec "$@"' bash "$@"
}
