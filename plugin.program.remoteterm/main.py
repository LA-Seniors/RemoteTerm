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

    addon = xbmcaddon.Addon()
    addon_path = addon.getAddonInfo('path')

    window = RemoteTermWindow('script-remoteterm-main.xml', addon_path, 'Default', '1080i')
    try:
        window.doModal()
    except Exception as e:
        xbmc.log(f"[RemoteTerm] fatal error in main window: {e}", xbmc.LOGERROR)
    finally:
        del window


if __name__ == '__main__':
    main()
