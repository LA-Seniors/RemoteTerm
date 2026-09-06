import sys

import xbmc
import xbmcaddon
import xbmcgui
from resources.lib.gui import RemoteTermWindow


def main():
    # A "mapinfo" argument (see settings.xml's action-type setting) shows
    # a plain info dialog instead of launching the main window --
    # RunScript(addon_id, arg) is how a program-type addon like this one
    # is re-invoked with an argument. This replaces two earlier attempts
    # at showing the map-tile-provider explanation as static settings.xml
    # text (both a long single-line label and a pair of short lsep rows)
    # that a screenshot confirmed still weren't rendering at all -- a
    # plain Dialog().ok() popup is a mechanism already confirmed reliable
    # elsewhere in this exact addon (repeater "Full Details"), so it
    # doesn't depend on whatever is different about this Kodi version's
    # settings-dialog rendering of lsep/long labels.
    if len(sys.argv) > 1 and sys.argv[1] == "mapinfo":
        xbmcgui.Dialog().ok(
            "Map Tiles",
            "Works automatically via OpenStreetMap PNG tiles, no signup needed.\n\n"
            "Optional: add a free CARTO API key above for a darker map style "
            "instead. Get one instantly (no approval queue) at "
            "carto.com/basemaps/apikey. Leave the key blank to keep using "
            "OpenStreetMap's default style.")
        return

    # Confirmed real request: a skin's Program Addons widget (Arctic
    # Fuse 3 and others let a user pin individual RunScript shortcuts
    # to the Home screen, not just the addon as a single whole) needs a
    # way to launch straight into one specific tab instead of always
    # landing on Dashboard -- e.g. RunScript(plugin.program.remoteterm,
    # chats) to jump directly to Chats. Reuses the exact same
    # RunScript(addon_id, argument) mechanism as "mapinfo" above, just
    # recognizing a different, larger set of argument values. Anything
    # not in this set (including no argument at all, or "dashboard"
    # itself) is simply ignored, and the window starts on Dashboard
    # exactly as it always has.
    initial_tab = None
    if len(sys.argv) > 1 and sys.argv[1] in (
            "dashboard", "chats", "nodes", "repeaters", "map", "packets", "analytics"):
        initial_tab = sys.argv[1]

    addon = xbmcaddon.Addon()
    addon_path = addon.getAddonInfo('path')

    window = RemoteTermWindow('script-remoteterm-main.xml', addon_path, 'Default', '1080i')
    if initial_tab:
        window.initial_tab = initial_tab
    try:
        window.doModal()
    except Exception as e:
        xbmc.log(f"[RemoteTerm] fatal error in main window: {e}", xbmc.LOGERROR)
    finally:
        del window


if __name__ == '__main__':
    main()
