import sys
import xbmc
import xbmcgui
import xbmcaddon

# Retrieve information about your addon from the addon.xml
addon = xbmcaddon.Addon()
addon_name = addon.getAddonInfo('name')
addon_version = addon.getAddonInfo('version')

def main():
    # 1. Print a message to Kodi's background log (useful for debugging)
    xbmc.log(f"[{addon_name}] v{addon_version} is starting up...", xbmc.LOGINFO)
    
    # 2. Open a popup window on the screen to show the user it worked
    dialog = xbmcgui.Dialog()
    dialog.ok(addon_name, "Hello! RemoteTerm has successfully launched.")

if __name__ == '__main__':
    main()