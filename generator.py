import os
import hashlib

def generate():
    addons_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
    
    # Scan subfolders for addon.xml files
    for folder in os.listdir('.'):
        if os.path.isdir(folder):
            xml_path = os.path.join(folder, 'addon.xml')
            if os.path.exists(xml_path):
                with open(xml_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # Add content, skipping the individual xml declaration lines
                    for line in lines:
                        if not line.strip().startswith('<?xml'):
                            addons_xml += line
                addons_xml += '\n'
                
    addons_xml += '</addons>\n'
    
    # Write the master addons.xml
    with open('addons.xml', 'w', encoding='utf-8') as f:
        f.write(addons_xml)
        
    # Generate and write the addons.xml.md5 checksum
    md5_hash = hashlib.md5(addons_xml.encode('utf-8')).hexdigest()
    with open('addons.xml.md5', 'w', encoding='utf-8') as f:
        f.write(md5_hash)
        
    print("Successfully generated addons.xml and addons.xml.md5!")

if __name__ == '__main__':
    generate()