#!/usr/bin/env bash
# PORTABILITY: Plasma 6 scripting API and Debian/KDE launcher IDs, not GNOME.
# Run as the desktop user, either directly or once at login.
set -euo pipefail
case "${1:-}" in
    personal|work) profile=$1 ;;
    *) echo 'Usage: bash kde-panel.sh personal|work [qgis:0|1] [vscode:0|1] [spotify:0|1]' >&2; exit 2 ;;
esac
qgis=${2:-1}
vscode=${3:-1}
spotify=${4:-1}
for selected in "$qgis" "$vscode" "$spotify"; do
    [[ $selected == 0 || $selected == 1 ]] || { echo 'App selections must be 0 or 1.' >&2; exit 2; }
done
if [[ $profile == work ]]; then qgis=0; fi

qdbus_command=''
for candidate in qdbus6 /usr/lib/qt6/bin/qdbus qdbus; do
    if command -v "$candidate" >/dev/null 2>&1; then
        qdbus_command=$candidate
        break
    fi
done
if [[ -z "$qdbus_command" ]]; then
    echo 'KDE panel setup requires qdbus6 (or qdbus).' >&2
    exit 1
fi

# Debian calls Firefox's launcher firefox-esr; other distributions use firefox.
firefox=firefox-esr.desktop
for directory in "${XDG_DATA_HOME:-$HOME/.local/share}/applications" /usr/local/share/applications /usr/share/applications; do
    if [[ -f "$directory/firefox.desktop" ]]; then
        firefox=firefox.desktop
        break
    fi
done
launchers='preferred://filemanager,applications:org.kde.konsole.desktop'
if [[ "$qgis" == 1 ]]; then
    launchers+=',applications:org.qgis.qgis.desktop'
fi
launchers+=",applications:$firefox"
if [[ $vscode == 1 ]]; then launchers+=',applications:code.desktop'; fi
if [[ $spotify == 1 ]]; then launchers+=',applications:spotify.desktop'; fi

# Use Plasma's live scripting API so the running shell saves the change itself.
# A live config backup helps recover the previous panel layout.
config_file="${XDG_CONFIG_HOME:-$HOME/.config}/plasma-org.kde.plasma.desktop-appletsrc"
if [[ -f $config_file && ! -e $config_file.before-system-setup ]]; then
    cp -p -- "$config_file" "$config_file.before-system-setup"
fi
script=$(cat <<JS
var updated = 0;
var allPanels = panels();
for (var i = 0; i < allPanels.length; ++i) {
    var panel = allPanels[i];
    if (panel.location !== 'bottom') continue;
    var widgets = panel.widgets();
    for (var j = 0; j < widgets.length; ++j) {
        var widget = widgets[j];
        if (widget.type !== 'org.kde.plasma.icontasks' &&
            widget.type !== 'org.kde.plasma.taskmanager') continue;
        widget.currentConfigGroup = ['General'];
        widget.writeConfig('launchers', '$launchers');
        widget.reloadConfig();
        ++updated;
    }
}
print(updated > 0 ? 'setup-panel-ok' : 'setup-panel-no-task-manager');
JS
)
result=$("$qdbus_command" org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$script")
if [[ "$result" != *setup-panel-ok* ]]; then
    echo "Could not find a task manager on a bottom KDE panel: $result" >&2
    exit 1
fi
# Remove only our own one-time startup entry after successful configuration.
startup_file="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/setup-kde-panel.desktop"
if [[ -f "$startup_file" ]]; then
    rm -- "$startup_file"
fi
echo 'KDE panel pins configured.'
