#!/usr/bin/env python3

import serial.tools.list_ports
import json
from typing import List, Dict, Optional, Tuple
import sys
import os
import glob
import argparse
# Add project root to path to allow importing from lib
# Assumes script is run from project root or PYTHONPATH is set correctly
# If running script directly from util/menu, adjust path accordingly
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import configparser
import re


from textual.app import App, ComposeResult
from textual.widgets import ListView, ListItem, Label
from textual.binding import Binding
from textual.containers import Center
from textual.screen import Screen
from textual.widgets import Static, Button

# command line tool to get all data about usb ports: (raspberry pi)
# udevadm info -a -n /dev/ttyUSB0
# udevadm info -a -n /dev/ttyACM0

# get list of input source modules.
def get_available_inputs() -> List[str]:
    """
    Get a list of available input source modules from the lib/inputs directory.
    """
    input_names = []
    inputs_dir = os.path.join(project_root, 'lib', 'inputs')
    # --- Add Debug Logging ---
    print(f"DEBUG: Checking for inputs in: {inputs_dir}", file=sys.stderr)
    # --- End Debug Logging ---
    try:
        # Path relative to the project root determined earlier
        #inputs_dir = os.path.join(project_root, 'lib', 'inputs') # Defined above now
        if not os.path.isdir(inputs_dir):
             print(f"Warning: Input directory not found at {inputs_dir}", file=sys.stderr)
             return []
        lst = os.listdir(inputs_dir)
        # Compile regex outside the loop for efficiency
        serial_input_pattern = re.compile(r'.*inputtype\s*=\s*["\']serial["\'].*', re.IGNORECASE)

        for filename in lst:
            # Ignore subdirectories and files starting with _ or .
            item_path = os.path.join(inputs_dir, filename)
            if filename.endswith(".py") and not filename.startswith(("_", ".")) and os.path.isfile(item_path):
                module_name = filename[:-3]
                try:
                    with open(item_path, 'r') as f:
                        for line in f:
                            if serial_input_pattern.match(line):
                                input_names.append(module_name)
                                break # Found the line, no need to read further
                except IOError as e:
                     print(f"Warning: Could not read input file '{item_path}': {e}", file=sys.stderr)
                except Exception as e: # Catch other potential errors during file processing
                     print(f"Warning: Error processing input file '{item_path}': {e}", file=sys.stderr)

    except Exception as e:
        print(f"Warning: Error scanning input directory '{inputs_dir}': {e}", file=sys.stderr)
    # --- Add Debug Logging ---
    print(f"DEBUG: Found inputs supporting 'serial': {input_names}", file=sys.stderr)
    # --- End Debug Logging ---
    return sorted(input_names)


CONFIG_FILE = os.path.join(project_root, 'config.cfg') # Use absolute path

def load_config(config_file: str = CONFIG_FILE) -> Tuple[configparser.ConfigParser, Dict[str, str], bool, bool]:
    """Loads the configuration file.

    Returns:
        Tuple containing:
         - configparser.ConfigParser object
         - Dictionary of assigned ports {port_path: section_name}
         - Boolean indicating if the config file was found and read
         - Boolean indicating if an error occurred during parsing
    """
    config = configparser.ConfigParser(comment_prefixes=('#', ';'), inline_comment_prefixes=('#', ';'), allow_no_value=True)
    # Preserve case sensitivity for section names and keys if needed, though lower is common
    # config.optionxform = str
    assigned_ports = {}
    found = False
    error_occurred = False
    try:
        if os.path.exists(config_file):
            config.read(config_file)
            found = True # Mark as found
            for section in config.sections():
                if config.has_option(section, 'port'):
                    port = config.get(section, 'port', fallback=None) # Use fallback
                    # Check if port value exists and is not just whitespace
                    if port and port.strip():
                        assigned_ports[port.strip()] = section
        else:
            # File not found, but not necessarily an error yet
            print(f"Info: Config file '{config_file}' not found. Will create if needed.", file=sys.stderr)
    except configparser.Error as e:
        print(f"Error reading config file '{config_file}': {e}", file=sys.stderr)
        error_occurred = True
        # Return empty config on error to avoid crashing
        config = configparser.ConfigParser(comment_prefixes=('#', ';'), inline_comment_prefixes=('#', ';'), allow_no_value=True)
        assigned_ports = {}
        # config.optionxform = str
    return config, assigned_ports, found, error_occurred

def save_config(config: configparser.ConfigParser, config_file: str = CONFIG_FILE):
    """Saves the configuration object back to the file, preserving comments and structure as much as possible."""
    comment_prefixes = ('#', ';')
    inline_comment_prefixes = ('#', ';')

    original_lines = []
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                original_lines = f.readlines()
        except IOError as e:
            print(f"Error reading existing config file '{config_file}' for saving: {e}", file=sys.stderr)
            # Decide if we should proceed with a blank slate or return
            # For now, let's try writing based on the config object even if reading failed
            pass # Allows creating the file if it was unreadable but config exists

    new_lines = []
    current_section = None
    # Track options written during the line-by-line pass
    processed_options_in_pass1 = set()
    # Track sections encountered in the original file
    sections_in_original_order = []

    # Pass 1: Process existing lines, update values, preserve comments/structure
    for line in original_lines:
        stripped_line = line.strip()

        # Preserve comments and blank lines
        if not stripped_line or stripped_line.startswith(comment_prefixes):
            new_lines.append(line)
            continue

        # Identify sections
        match = config.SECTCRE.match(stripped_line)
        if match:
            current_section = match.group('header')
            # Keep track of sections found in original file order
            if current_section not in sections_in_original_order:
                sections_in_original_order.append(current_section)

            # Write section header only if it still exists in the config object
            if config.has_section(current_section):
                new_lines.append(line)
            # Reset processed options for the new section if needed (though global set is okay)
            continue

        # Identify options (key-value pairs) within the current section
        if current_section and config.has_section(current_section) and ('=' in stripped_line or ':' in stripped_line):
            # More robust parsing for key/value/inline comment
            key = ''
            value_part = ''
            inline_comment = ''
            separator = '=' # Default
            if '=' in stripped_line:
                parts = stripped_line.split('=', 1)
                key = parts[0].strip()
                if len(parts) > 1: value_part = parts[1]
                separator = '='
            elif ':' in stripped_line:
                parts = stripped_line.split(':', 1)
                key = parts[0].strip()
                if len(parts) > 1: value_part = parts[1]
                separator = ':'
            else:
                # Malformed line, preserve it? For now, yes.
                new_lines.append(line)
                continue

            # Extract inline comment if present
            value_part = value_part.strip()
            for prefix in inline_comment_prefixes:
                if prefix in value_part:
                    # Ensure prefix is not part of the value itself (e.g., in a URL)
                    # A simple check: look for prefix preceded by space or at start
                    try:
                         # Find the first occurrence that's likely a comment start
                         comment_start_index = -1
                         potential_indices = [i for i, char in enumerate(value_part) if char == prefix]
                         for idx in potential_indices:
                             if idx == 0 or value_part[idx-1].isspace():
                                 comment_start_index = idx
                                 break

                         if comment_start_index != -1:
                            inline_comment_part = value_part[comment_start_index:]
                            value_part = value_part[:comment_start_index].strip() # Value before comment
                            # Check if the comment part itself starts with the prefix
                            if inline_comment_part.strip().startswith(prefix):
                                inline_comment = f" {inline_comment_part.strip()}" # Preserve leading space
                            else: # False positive, treat as part of value
                                inline_comment = ""
                                value_part = value_part + inline_comment_part # Put it back
                         else: # No valid comment prefix found
                            inline_comment = ""

                    except Exception: # Fallback if complex logic fails
                        inline_comment = ""
                        # value_part remains as is


            # Check if the option still exists in the config object for this section
            if config.has_option(current_section, key):
                new_value = config.get(current_section, key)
                # Use ' = ' or ' : ' consistently based on original separator found
                sep_str = f" {separator} "
                new_line_content = f"{key}{sep_str}{new_value}{inline_comment}"
                new_lines.append(new_line_content + '\n')
                processed_options_in_pass1.add((current_section, key))
            else:
                # Option was removed from config object, don't write this line
                # Or, optionally, write it as a comment:
                # new_lines.append(f"# {line.lstrip()}")
                pass
        else:
            # Preserve lines that are not comments, sections, or valid options
            # (e.g., could be continuations or just random text)
             if current_section and config.has_section(current_section):
                 # Only preserve if inside a known, still-existing section
                 new_lines.append(line)
             elif not current_section:
                 # Preserve lines before the first section
                 new_lines.append(line)


    # Pass 2: Add sections and options present in config object but not processed in Pass 1
    processed_sections_pass2 = set()

    # Use the order sections appeared in the original file first
    sections_to_process = sections_in_original_order + [s for s in config.sections() if s not in sections_in_original_order]

    for section in sections_to_process:
        if not config.has_section(section): continue # Should not happen, but safety check

        section_header = f"[{section}]"
        section_header_line = section_header + '\n'

        # Find where this section header is (or should be) in new_lines
        header_index = -1
        try:
            # Find the index based on exact match or regex match
            header_index = next(i for i, line in enumerate(new_lines) if config.SECTCRE.match(line.strip()) and config.SECTCRE.match(line.strip()).group('header') == section)
        except StopIteration:
            # Section doesn't exist in new_lines yet, add it at the end
            if new_lines and not new_lines[-1].isspace(): # Add a blank line if needed
                 new_lines.append('\n')
            new_lines.append(section_header_line)
            header_index = len(new_lines) - 1

        # Determine where to insert options for this section
        # Insert after the header, potentially after existing options processed in Pass 1
        insert_index = header_index + 1

        # Find the end of the current section (start of next section or end of file)
        # This helps place options correctly if Pass 1 already wrote some
        next_section_start = len(new_lines)
        for i in range(insert_index, len(new_lines)):
             if config.SECTCRE.match(new_lines[i].strip()):
                 next_section_start = i
                 break
        insert_index = next_section_start # Insert before the next section starts

        # Add options for this section that weren't processed in Pass 1
        options_added_this_section = 0
        for option in config.options(section):
            if (section, option) not in processed_options_in_pass1:
                value = config.get(section, option)
                option_line = f"{option} = {value}\n"
                new_lines.insert(insert_index + options_added_this_section, option_line)
                options_added_this_section += 1
                # Mark as processed overall (optional, mainly for clarity)
                # processed_options_in_pass1.add((section, option))

        processed_sections_pass2.add(section)


    # Write the modified content back to the file
    try:
        with open(config_file, 'w') as f:
            f.writelines(new_lines)
        #print(f"Configuration saved to {config_file} (structure preserved)")
    except IOError as e:
        print(f"Error writing config file '{config_file}': {e}", file=sys.stderr)

def get_serial_ports() -> List[Dict[str, str]]:
    """
    Get a list of available serial ports with their descriptions.
    Ports with missing or "n/a" descriptions are sorted to the bottom.

    On Linux, pyserial's comports() only returns ports with USB/PCI hardware
    IDs and skips platform UARTs (e.g. ttyAMA0 on Raspberry Pi). We supplement
    the list by scanning /dev/ttyAMA* and /dev/ttyS* directly.
    
    Returns:
        List[Dict[str, str]]: List of dictionaries containing port information
                             Each dict has 'port', 'description', and 'hwid' keys
    """
    ports = []
    seen = set()

    # Iterate through all available serial ports reported by pyserial
    for port in serial.tools.list_ports.comports():
        port_info = {
            'port': port.device,
            'description': port.description,
            'hwid': port.hwid,
            'serial_number': port.serial_number,
            'interface': port.interface,
            'location': port.location,
            'manufacturer': port.manufacturer,
            'product': port.product,
            'vid': port.vid,
            'pid': port.pid,
        }
        ports.append(port_info)
        seen.add(port.device)

    # On Linux, also scan platform UARTs that pyserial misses (ttyAMA*, ttyS*)
    for pattern in ['/dev/ttyAMA*', '/dev/ttyS*']:
        for dev in sorted(glob.glob(pattern)):
            if dev not in seen:
                ports.append({
                    'port': dev,
                    'description': 'n/a',
                    'hwid': 'n/A',
                    'serial_number': None,
                    'interface': None,
                    'location': None,
                    'manufacturer': None,
                    'product': None,
                    'vid': None,
                    'pid': None,
                })
                seen.add(dev)

    # Sort ports - putting ones with missing/n/a descriptions at the bottom
    def port_sort_key(port):
        desc = (port['description'] or '').lower()
        if not desc or desc == 'n/a':
            return (1, port['port'])  # Will sort after valid descriptions
        return (0, port['port'])      # Will sort before invalid descriptions
    
    return sorted(ports, key=port_sort_key)

def save_ports_to_file(output_file: str = 'available_serial_ports.json'):
    """
    Save the list of available serial ports to a JSON file.
    
    Args:
        output_file (str): Name of the output file (default: 'available_serial_ports.json')
    """
    ports = get_serial_ports()
    
    with open(output_file, 'w') as f:
        json.dump(ports, f, indent=4)
    
    print(f"Found {len(ports)} serial ports:")

def print_out():
    ports = get_serial_ports()
    for port in ports:
        print(f"Port: {port['port']}")
        print(f"Description: {port['description']}")
        print(f"Hardware ID: {port['hwid']}")
        print(f"Serial Number: {port['serial_number']}")
        print(f"Interface: {port['interface']}")
        print(f"Location: {port['location']}")
        print(f"Manufacturer: {port['manufacturer']}")
        print(f"Product: {port['product']}")
        print(f"VID: {port['vid']}")
        print(f"PID: {port['pid']}")
        print("-" * 50)

########################################################################################
########################################################################################
########################################################################################

class PortSelectScreen(Screen):
    """A screen with a centered dialog for port selection."""
    title: str = None
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("enter", "select_port", "Select", show=True),
        Binding("s", "save_and_exit", "Save & Exit", show=True),
        Binding("escape", "quit", "Quit", show=False),
    ]

    # Update __init__ to accept config status flags
    def __init__(self, assigned_ports: Dict[str, str], title: str = None, debug: bool = False, config_found: bool = False, config_error: bool = False, **kwargs):
        super().__init__(**kwargs)
        self._assigned_ports = assigned_ports
        self.title = title
        self._debug_mode = debug # Pass debug mode from app
        self._config_found = config_found
        self._config_error = config_error

    def compose(self) -> ComposeResult:
        if self.title is None:
            self.title = "Select Serial Port"
        yield Static(self.load_ascii_art(), id="background")
        with Center():
            yield Label(self.title, id="title")
            yield Static("", id="config-status") # Add placeholder for status
            yield ListView(id="port-list", classes="port-list")
        if self.app._debug_mode:
            # Ensure debug log exists if debug mode is on, even if PortSelectScreen doesn't write directly
            yield Static("", id="debug-log")

    def load_ascii_art(self) -> str:
        """Load ASCII art from file."""
        try:
            # Use app's method to ensure correct relative pathing
            art_func = getattr(self.app, 'load_ascii_art', None)
            if art_func:
                return art_func()
            # Fallback if app method isn't found (though it should be)
            with open('docs/imgs/logo_txt_small.txt', 'r') as f:
                 return f.read()
        except Exception as e:
            print(f"Warning (PortSelectScreen): Could not load ASCII art logo: {e}", file=sys.stderr)
            return ""  # Return empty string if file not found

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        # Set config status message
        status_widget = self.query_one("#config-status")
        config_filename = os.path.basename(CONFIG_FILE)
        if self._config_error:
            status_widget.update(f"[bold red]Error reading {config_filename}[/]")
        elif self._config_found:
            status_widget.update(f"Config: [bold green]{config_filename}[/] loaded")
        else:
            status_widget.update(f"Config: [bold yellow]{config_filename}[/] not found")

        self.update_port_list()
        # Safely set index only if list is not empty
        port_list_widget = self.query_one("#port-list")
        if len(port_list_widget.children) > 0:
            port_list_widget.index = 0
        
        # Set up periodic refresh every 2 seconds
        self.set_interval(2, self.refresh_ports)

    # --- Add log_debug helper ---
    def log_debug(self, message: str) -> None:
        """Log debug messages if debug mode is enabled by calling the app's logger."""
        if hasattr(self.app, 'log_debug') and self.app._debug_mode:
            self.app.log_debug(f"DEBUG (PortSelectScreen): {message}")
        elif self._debug_mode: # Fallback print if app method not found but debug is on
            print(f"DEBUG (PortSelectScreen): {message}", file=sys.stderr)


    # --- Add on_screen_resume method ---
    def on_screen_resume(self) -> None:
        """Called when this screen is resumed after another screen is popped."""
        self.log_debug("Resumed. Forcing port list update.")
        # No need to reload config here, InputAssignScreen modifies app's state directly.
        # Just update the view based on the potentially changed app state.
        self.update_port_list()
        # Optional: Could try to restore selection or scroll position if needed,
        # but update_port_list rebuilds it, so might reset scroll.


    def update_port_list(self) -> None:
        """Update the port list display."""
        self.log_debug("update_port_list called.") # Add log here too
        list_view = self.query_one("#port-list")
        current_index = list_view.index # Store current index before clear
        # --- ADDED DEBUG LOG ---
        self.log_debug(f"Updating list using self.app.assigned_ports: {self.app.assigned_ports}")
        # -----------------------
        current_ports = get_serial_ports()

        # Update app.current_available_ports (raw list)
        self.app.current_available_ports = current_ports

        ports_changed = False # Initialize
        current_port_ids = {p['port'] for p in current_ports}
        known_port_ids = set(self.app.known_ports.keys())

        # --- Store previous assignments before any updates ---
        previous_assignments = {port_id: port_info.get('assigned_input')
                                for port_id, port_info in self.app.known_ports.items()}

        # Update known_ports status (new/removed/reappeared)
        # --- Start: Logic for new/removed/reappeared identification --- 
        # Identify new ports
        new_port_ids = current_port_ids - known_port_ids
        for port_id in new_port_ids:
            port_info = next((p for p in current_ports if p['port'] == port_id), None)
            if port_info:
                port_info['is_new'] = True
                port_info['is_removed'] = False
                # Don't set assigned_input here yet, wait for the check below
                self.app.known_ports[port_id] = port_info
                ports_changed = True
                self.log_debug(f"Detected new port: {port_id}")

        # Identify potentially removed ports
        potentially_removed_ids = known_port_ids - current_port_ids
        for port_id in potentially_removed_ids:
            if not self.app.known_ports[port_id].get('is_removed', False):
                 self.app.known_ports[port_id]['is_removed'] = True
                 self.app.known_ports[port_id]['is_new'] = False
                 # Keep assigned_input even if removed, might reappear
                 ports_changed = True
                 self.log_debug(f"Detected removed port: {port_id}")

        # Check for ports that reappeared or changed details (but not assignment yet)
        reappeared_ids = (known_port_ids & current_port_ids)
        for port_id in reappeared_ids:
            # Get current details from the OS scan
            current_port_info_from_scan = next((p for p in current_ports if p['port'] == port_id), None)
            if not current_port_info_from_scan: continue # Should not happen

            known_port_info = self.app.known_ports[port_id]
            was_removed = known_port_info.get('is_removed', False)
            was_new = known_port_info.get('is_new', False)
            # Preserve assignment from known_port_info for now
            previous_assignment_for_this_port = known_port_info.get('assigned_input')

            if was_removed:
                # Port reappeared - update details from scan, mark not removed/new
                self.app.known_ports[port_id] = current_port_info_from_scan
                self.app.known_ports[port_id]['is_removed'] = False
                self.app.known_ports[port_id]['is_new'] = False
                # Restore previous assignment if it existed
                self.app.known_ports[port_id]['assigned_input'] = previous_assignment_for_this_port
                ports_changed = True
                self.log_debug(f"Detected reappeared port: {port_id}")
            elif port_id not in new_port_ids:
                 # Port existed and wasn't removed - check if details changed (excluding assignment)
                 # Create copies for comparison, excluding 'assigned_input' initially
                 compare_current = {k: v for k, v in current_port_info_from_scan.items() if k != 'assigned_input'}
                 compare_known = {k: v for k, v in known_port_info.items() if k not in ['is_new', 'is_removed', 'assigned_input', 'position']}

                 if compare_current != compare_known:
                     # Details (like description) changed, update known_ports from scan
                     self.app.known_ports[port_id] = current_port_info_from_scan
                     # Restore flags and previous assignment
                     self.app.known_ports[port_id]['is_new'] = was_new
                     self.app.known_ports[port_id]['is_removed'] = was_removed
                     self.app.known_ports[port_id]['assigned_input'] = previous_assignment_for_this_port
                     ports_changed = True # Trigger redraw on detail change
                     self.log_debug(f"Detected detail change for port: {port_id}")

        # --- End: Logic for new/removed/reappeared identification --- 

        # --- New check for assignment changes --- 
        # Iterate through ports that are still known and not marked as removed
        for port_id, port_info in self.app.known_ports.items():
            if not port_info.get('is_removed', False):
                # Get the latest assignment from the app's config dictionary
                current_assignment = self.app.assigned_ports.get(port_id)
                # Get the assignment we had stored *before* this update cycle started
                previous_assignment = previous_assignments.get(port_id)

                # Check if assignment changed compared to previous state
                if current_assignment != previous_assignment:
                    ports_changed = True # Assignment added, removed, or changed
                    self.log_debug(f"Assignment change detected for {port_id}. From '{previous_assignment}' to '{current_assignment}'")
                
                # *** Store the *current* assignment back into known_ports ***
                # This is crucial so the *next* update cycle compares correctly
                port_info['assigned_input'] = current_assignment


        # Filter app.ports for active (non-removed) ports to be displayed
        # Use the freshly updated self.app.known_ports
        self.app.ports = [p for p_id, p in self.app.known_ports.items() if not p.get('is_removed', False)]

        # Force redraw on first run if there are ports and list is empty
        if not list_view.children and self.app.ports:
             ports_changed = True
             self.log_debug("List was empty, forcing redraw.")

        # --- Redraw ListView only if necessary (now includes assignment changes) --- 
        if ports_changed:
            self.log_debug("Ports or assignments changed, redrawing ListView.")
            list_view.clear()

            # Sort active ports from self.app.ports for consistent display order
            # self.app.ports was just updated above
            sorted_active_ports_for_display = sorted(self.app.ports, key=lambda p: p['port'])

            # Reset position counter for the visible list items
            position = 0
            # Iterate through sorted active ports to build the list view
            for port_info in sorted_active_ports_for_display:
                port_id = port_info['port']
                # --- Add active port to ListView --- 
                display_text = f"{port_info['port']} ({port_info['description']})" if port_info['description'] != 'n/a' else f"{port_info['port']}"
                # Get assignment directly from port_info (which was updated above)
                assigned_input = port_info.get('assigned_input')
                # --- Optional DEBUG LOG (already logged change detection earlier) ---
                # if assigned_input:
                #     self.log_debug(f"Port {port_id}: Displaying assignment '{assigned_input}'")
                # -----------------------
                item_classes = []

                if port_info.get('is_new', False):
                    item_classes.append("new-port")

                if assigned_input:
                    display_text += f" -> {assigned_input}"
                    item_classes.append("assigned-port")

                label = Label(display_text)
                list_item = ListItem(label)

                if item_classes:
                    list_item.set_classes(" ".join(item_classes))

                list_view.append(list_item)

                # --- Store the ListView index ('position') ONLY for this active port --- 
                # Note: 'position' here relates to the index in the *visible* list
                port_info['position'] = position 
                position += 1 # Increment position only for items added to the list
            
            # Restore index if possible and valid after redraw
            if current_index is not None and 0 <= current_index < len(list_view.children):
                 list_view.index = current_index
                 self.log_debug(f"Restored selection index to {current_index}")
            elif len(list_view.children) > 0:
                 list_view.index = 0 # Default to first item if previous index invalid
                 self.log_debug("Defaulted selection index to 0")
            else:
                list_view.index = None # No selection possible

            # # Final cleanup: Ensure any port still marked as removed definitely doesn't have a position
            # # This is handled implicitly now by iterating over active ports
            # for port_id, port_info in self.app.known_ports.items():
            #     if port_info.get('is_removed', False) and 'position' in port_info:
            #         del port_info['position']
        else:
            self.log_debug("No port or assignment changes detected, skipping ListView redraw.")

    def refresh_ports(self) -> None:
        """Refresh the port list while maintaining selection."""
        list_view = self.query_one("#port-list")
        
        # Store currently selected port ID if any based on *visible* items
        selected_port_id = None
        current_selection_index = list_view.index
        # Get the list of currently displayed (active) port details in the correct order
        sorted_active_ports = sorted(
            [p for p in self.app.known_ports.values() if not p.get('is_removed', False)],
            key=lambda p: p['port']
        )
        if current_selection_index is not None and 0 <= current_selection_index < len(sorted_active_ports):
            selected_port_id = sorted_active_ports[current_selection_index]['port']
            # self.log_debug(f"Refresh: Storing selected port ID: {selected_port_id} at index {current_selection_index}")
        
        # Update the port list data structures and redraw if needed
        self.update_port_list()
        
        # Restore selection based on port ID
        if selected_port_id:
            # Re-fetch the sorted list as update_port_list might have changed it
            new_sorted_active_ports = sorted(
                [p for p in self.app.known_ports.values() if not p.get('is_removed', False)],
                key=lambda p: p['port']
            )
            try:
                # Find the new index of the previously selected port ID
                new_index = next(i for i, p in enumerate(new_sorted_active_ports) if p['port'] == selected_port_id)
                if 0 <= new_index < len(list_view.children): # Check against actual list items
                    list_view.index = new_index
                    # self.log_debug(f"Refresh: Restored selection to port ID: {selected_port_id} at new index {new_index}")
                else:
                    # self.log_debug(f"Refresh: Port ID {selected_port_id} found but new index {new_index} out of bounds.")
                    if len(list_view.children) > 0: list_view.index = 0 # Default if out of bounds
            except StopIteration:
                 # self.log_debug(f"Refresh: Previously selected port ID {selected_port_id} not found after update.")
                 if len(list_view.children) > 0: list_view.index = 0 # Default if not found
        elif len(list_view.children) > 0:
             list_view.index = 0 # Default to first if nothing was selected
        else:
             list_view.index = None # No selection possible if list is empty

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def action_save_and_exit(self) -> None:
        """Save current config to disk and exit."""
        save_config(self.app.config, CONFIG_FILE)
        self.app.exit()

    def on_key(self, event) -> None:
        """Handle key press events."""
        # --- Add Debug Logging ---
        log_func = getattr(self.app, 'log_debug', None)
        if event.key == "enter":
            if log_func: log_func(f"Enter key pressed in PortSelectScreen.")
            # --- End Debug Logging ---

            list_view = self.query_one("#port-list")
            if list_view.index is not None:
                # --- Add Debug Logging ---
                if log_func: log_func(f"ListView index is {list_view.index}.")
                # --- End Debug Logging ---

                # --- MODIFICATION START ---
                # Get the details based on the *sorted* list of active ports,
                # matching the order shown in the ListView.
                selected_port_details = None
                # Reconstruct the sorted list of active ports
                sorted_active_ports = sorted(
                    [p for p in self.app.known_ports.values() if not p.get('is_removed', False)],
                    key=lambda p: p['port']
                )

                if 0 <= list_view.index < len(sorted_active_ports):
                    # Get the port details using the index on the sorted list
                    selected_port_details = sorted_active_ports[list_view.index]
                    # Optional: Log the port ID found using this method
                    if log_func: log_func(f"Selected port from sorted list: {selected_port_details.get('port', 'N/A')}")
                else:
                    if log_func: log_func(f"ListView index {list_view.index} is out of bounds for sorted_active_ports (len={len(sorted_active_ports)})")
                # --- MODIFICATION END ---

                if selected_port_details:
                    # --- Add Debug Logging ---
                    if log_func: log_func(f"Found valid port details: {selected_port_details['port']}")
                    # --- End Debug Logging ---

                    available_inputs = get_available_inputs()
                    # --- Add Debug Logging ---
                    if log_func: log_func(f"Found {len(available_inputs)} available inputs.")
                    # --- End Debug Logging ---

                    if not available_inputs:
                        if log_func: log_func("No input modules found in lib/inputs to assign.")
                        return

                    # --- Add Debug Logging ---
                    if log_func: log_func(f"Creating InputAssignScreen for {selected_port_details['port']}...")
                    # --- End Debug Logging ---
                    assignment_screen = InputAssignScreen(
                        input_names=available_inputs,
                        port_details=selected_port_details
                    )
                    # --- Add Debug Logging ---
                    if log_func: log_func(f"Pushing InputAssignScreen onto stack...")
                    # --- End Debug Logging ---
                    self.app.push_screen(assignment_screen)
                    # --- Add Debug Logging ---
                    if log_func: log_func(f"push_screen called.") # Log after the call too
                    # --- End Debug Logging ---
                else:
                    if log_func: log_func(f"No valid, active port found at selected index {list_view.index}")

        # --- Add Debug Logging for other keys if needed ---
        # elif log_func:
        #     log_func(f"Key pressed: {event.key}")
        # --- End Debug Logging ---

########################################################################################
########################################################################################
# SerialPortSelector
########################################################################################
class SerialPortSelector(App):
    """A Textual app to select a serial port."""
    
    CSS = """
    Screen {
        align: center middle;
        layers: base overlay;
    }

    #background {
        width: 100%;
        height: 100%;
        dock: top;
        content-align: center top;
        padding-top: 1;
        color: $primary-darken-2;
        layer: base;
    }

    Center {
        width: 65;
        height: auto;
        max-height: 90%; /* Prevent dialog exceeding screen height */
        border: solid green;
        background: $surface;
        padding: 1;
        layer: overlay;
        margin-top: 0;
    }

    #title {
        text-align: center;
        padding-bottom: 1; /* Add space below title */
        color: $text;
        width: 100%;
    }

    /* Add style for config status message */
    #config-status {
        width: 100%;
        text-align: center;
        padding-bottom: 1;
        color: $text-muted; /* Use a muted color */
    }

    .port-list {
        width: 100%;
        height: auto;
        max-height: 20;
        border: solid $accent;
        padding: 0 1;
        background: $surface;
    }

    .new-port {
        color: $success;
        /*background: $surface;*/
    }

    .removed-port {
        color: $primary-background;
        background: $surface;
    }

    /* Style for ports assigned in config */
    .assigned-port {
        color: $warning; /* Yellow */
        /* You could also add other styles like:
           text-style: italic;
        */
    }

    #debug-log {
        dock: bottom;
        width: 100%;
        height: 35;
        background: $surface;
        color: $warning;
        border-top: solid $primary;
        padding: 0 1;
        overflow-y: hidden;
    }

    #input-dialog { /* Style the new dialog */
        width: 65;
        height: auto;
        border: solid $accent; /* Different border? */
        background: $surface;
        padding: 1;
        layer: overlay; /* Ensure it's on top */
        /* margin-top: 0; */ /* Adjust position if needed */
    }

    #input-title {
        text-align: center;
        padding-bottom: 1;
        color: $text;
        width: 100%;
    }

    #input-subtitle {
        padding-bottom: 1;
        color: $text;
        width: 100%;
    }


    #input-list {
        width: 100%;
        height: auto;
        max-height: 15; /* Adjust max height */
        border: solid $primary; /* Different border? */
        padding: 0 1;
        background: $surface;
    }
    """
    
    def __init__(self, title: str = None, debug: bool = False):
        super().__init__()
        self._debug_mode = debug
        self.title = title
        self.selected_port = None # Final selected port after assignment (if needed)

        # Load configuration
        self.config, self.assigned_ports, self.config_found, self.config_error = load_config(CONFIG_FILE)
        # Get initial list of ports
        initial_ports = get_serial_ports()

        # Initialize known_ports based on initial scan
        self.known_ports = {}
        for port in initial_ports:
            port_info = port.copy()
            port_info['is_new'] = False # Assume not new initially
            port_info['is_removed'] = False
            self.known_ports[port['port']] = port_info

        self.current_available_ports = initial_ports # Store currently detected ports
        self.port_to_assign = None # Temp storage for port being assigned
        self.list_item_to_port_id = {} # Mapping from list index to port_id for selection restoration

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Pass assigned ports and config status to the screen
        portSelectScreen = PortSelectScreen(
            assigned_ports=self.assigned_ports,
            title=self.title,
            debug=self._debug_mode,
            config_found=self.config_found,
            config_error=self.config_error
        )
        self.push_screen(portSelectScreen)

    def load_ascii_art(self) -> str:
        """Load ASCII art from file."""
        try:
            # Adjust path relative to project root
            logo_path = os.path.join(project_root, 'docs/imgs/logo_txt_small.txt')
            with open(logo_path, 'r') as f:
                return f.read()
        except Exception as e:
             print(f"Warning: Could not load ASCII art logo: {e}", file=sys.stderr)
             return "" # Return empty string if file not found or error

    def log_debug(self, message: str) -> None:
        """Add message to debug log if debug mode is enabled."""
        # Check if debug mode is enabled AND the widget exists
        if self._debug_mode:
            try:
                # Query for the debug log across all screens
                debug_log = self.query_one("#debug-log")
                current_text = debug_log.render().plain
                # Keep last N lines (e.g., 10)
                lines = (current_text.split('\n')[-9:] if current_text else []) + [message]
                debug_log.update('\n'.join(lines))
            except Exception:
                # Log to stderr if debug widget isn't found (shouldn't happen often)
                # This prevents crashes if logging is called before the widget is mounted
                import sys
                print(f"DEBUG (stderr): {message}", file=sys.stderr)

def select_serial_port(title: str = None, debug: bool = False) -> Optional[Dict[str, str]]:
    """
    Show an interactive menu to select a serial port.
    
    Args:
        title (str, optional): Title for the selection window
        debug (bool, optional): Enable debug logging window
    
    Returns:
        Optional[Dict[str, str]]: Selected port information or None if no selection made
    """
    ports = get_serial_ports()
    if not ports:
        print("No serial ports found.")
        return None
        
    app = SerialPortSelector(title=title, debug=debug)
    app.run()
    return app.selected_port

########################################################################################
########################################################################################
# InputAssignScreen
########################################################################################
class InputAssignScreen(Screen):
    """A screen to select an input type to assign to the chosen serial port."""

    # Define the [NONE] option identifier
    NONE_OPTION = "[NONE]"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "assign_input", "Assign", show=True),
        Binding("q", "cancel", "Cancel", show=False), # Allow q to cancel too
    ]

    # Modify __init__ to accept port_details directly
    def __init__(self, input_names: List[str], port_details: Dict[str, str], **kwargs):
        super().__init__(**kwargs)
        # Prepend the [NONE] option to the list
        self._input_names = [self.NONE_OPTION] + input_names
        # Store the passed details directly
        self.selected_port_details = port_details
        if not self.selected_port_details or 'port' not in self.selected_port_details:
            # Handle error: Log and potentially prevent screen from loading
            print("ERROR: InputAssignScreen initialized without valid port_details.", file=sys.stderr)
            # You might want to raise an exception or call self.app.pop_screen() here
            # For now, set a default to avoid immediate crash, but this indicates a problem
            self.selected_port_id = "ERROR"
            self._input_names = [] # Prevent list rendering issues
        else:
            self.selected_port_id = self.selected_port_details['port']

    def compose(self) -> ComposeResult:
        try:
            background_art = self.app.load_ascii_art()
        except Exception as e:
             print(f"Error accessing self.app in InputAssignScreen.compose: {e}", file=sys.stderr)
             background_art = ""

        yield Static(background_art, id="background")
        with Center(id="input-dialog"):
            # --- Set the fixed title ---
            yield Static("Assign Serial to TronV Input Source", id="input-title")
            # --- Show port info in subtitle ---
            port_info_text = f"Port: {self.selected_port_id}"
            if self.selected_port_details.get('description', 'n/a') != 'n/a':
                port_info_text += f" ({self.selected_port_details['description']})"
            # --- Add instruction to subtitle ---
            yield Static(f"{port_info_text}\n(Esc to Cancel)", id="input-subtitle")
            yield ListView(id="input-list", classes="input-list") # Keep the list view
        # --- ADD debug log widget if debug mode is on ---
        if self.app._debug_mode:
            yield Static("", id="debug-log") # Add the placeholder

    def action_cancel(self) -> None:
        """Cancel assignment and return to port list."""
        # self.app.port_to_assign = None # Clear the temporary storage - handled by caller
        self.app.pop_screen()

    def action_assign_input(self) -> None:
        """Assigns the selected input type to the port or comments out the assignment."""
        log_func = getattr(self.app, 'log_debug', None)
        if log_func: log_func("ACTION: action_assign_input called.")

        input_list = self.query_one("#input-list")
        if input_list.index is None or not self._input_names:
            if log_func: log_func("DEBUG: No input type selected or input list empty.")
            if hasattr(self.app, 'log_debug'): self.app.log_debug("No input type selected.")
            return

        selected_index = input_list.index
        selected_option = self._input_names[selected_index]
        port_id_to_modify = self.selected_port_id

        config = self.app.config
        config_file_path = CONFIG_FILE # Use the globally defined path
        assigned_ports = self.app.assigned_ports # Get reference to app's dict

        # --- Handle [NONE] selection ---
        if selected_option == self.NONE_OPTION:
            current_assignment_section = assigned_ports.get(port_id_to_modify)
            if current_assignment_section:
                if log_func: log_func(f"Attempting to remove/comment assignment for {port_id_to_modify} from section {current_assignment_section}.")

                # 1. Modify the config file directly to comment out the line
                try:
                    with open(config_file_path, 'r') as f:
                        lines = f.readlines()

                    new_lines = []
                    in_target_section = False
                    modified = False
                    section_header_pattern = re.compile(r'^\s*\[(.*)\]\s*$')
                    port_line_pattern = re.compile(rf'^\s*port\s*[:=]\s*{re.escape(port_id_to_modify)}\s*(#.*)?$', re.IGNORECASE)
                    commented_port_line_pattern = re.compile(rf'^\s*#\s*port\s*[:=]\s*{re.escape(port_id_to_modify)}\s*(#.*)?$', re.IGNORECASE)


                    for line in lines:
                        section_match = section_header_pattern.match(line)
                        if section_match:
                            in_target_section = (section_match.group(1).strip() == current_assignment_section)
                            new_lines.append(line) # Always keep section headers
                        elif in_target_section and port_line_pattern.match(line):
                            # Comment out the specific port assignment line
                            new_lines.append(f"# {line.lstrip()}")
                            modified = True
                        elif in_target_section and commented_port_line_pattern.match(line):
                             # Keep already commented line as is
                             new_lines.append(line)
                        else:
                            new_lines.append(line) # Keep other lines

                    if modified:
                        with open(config_file_path, 'w') as f:
                            f.writelines(new_lines)
                        if log_func: log_func(f"Commented out 'port = {port_id_to_modify}' in section [{current_assignment_section}] in {config_file_path}")

                        # 2. Update the config object in memory (remove the option)
                        if config.has_option(current_assignment_section, 'port') and \
                           config.get(current_assignment_section, 'port') == port_id_to_modify:
                            config.remove_option(current_assignment_section, 'port')
                            if log_func: log_func(f"Removed 'port' option from section [{current_assignment_section}] in config object.")

                        # 3. Update internal tracking
                        if port_id_to_modify in assigned_ports:
                            del assigned_ports[port_id_to_modify]
                            if log_func: log_func(f"Removed {port_id_to_modify} from internal assigned_ports dict.")
                    else:
                        if log_func: log_func(f"Could not find uncommented 'port = {port_id_to_modify}' in section [{current_assignment_section}] to comment out.")
                        # Optionally still remove from config object and dict if needed
                        if config.has_option(current_assignment_section, 'port') and config.get(current_assignment_section, 'port') == port_id_to_modify:
                            config.remove_option(current_assignment_section, 'port')
                        if port_id_to_modify in assigned_ports:
                            del assigned_ports[port_id_to_modify]


                except IOError as e:
                    if log_func: log_func(f"ERROR: Failed to read/write config file {config_file_path}: {e}")
            else:
                 if log_func: log_func(f"Port {port_id_to_modify} was not assigned. No changes made.")

            # --- RELOAD CONFIG AFTER [NONE] ---
            # Optional: Reload config to ensure consistency after manual file edit
            # This might be overkill if the config object/dict update is reliable
            try:
                reloaded_config, reloaded_assigned_ports, reloaded_found, reloaded_error = load_config(config_file_path)
                if not reloaded_error:
                    self.app.config = reloaded_config
                    self.app.assigned_ports = reloaded_assigned_ports
                    self.app.config_found = reloaded_found
                    self.app.config_error = reloaded_error
                    if log_func: log_func("Config reloaded successfully after [NONE] action.")
                else:
                    if log_func: log_func("Error reloading config immediately after [NONE] action.")
            except Exception as e:
                 if log_func: log_func(f"Exception during config reload after [NONE]: {e}")


        # --- Handle regular input selection ---
        else:
            selected_input_name = selected_option
            port_id_to_assign = port_id_to_modify # Keep variable name consistent
            assigned = False

            # 1. Remove any existing assignment for this port_id from the config *object*
            # This ensures save_config doesn't write conflicting entries.
            # The actual commenting out (if needed) is handled by the [NONE] logic above.
            # The file might contain commented lines, but save_config works from the object.
            current_assignment_section = assigned_ports.get(port_id_to_assign)
            if current_assignment_section:
                if config.has_option(current_assignment_section, 'port') and \
                   config.get(current_assignment_section, 'port') == port_id_to_assign:
                    config.remove_option(current_assignment_section, 'port')
                    if log_func: log_func(f"Removed previous assignment of {port_id_to_assign} from section {current_assignment_section} in config object before new assignment.")
                # Also remove from internal dict before re-assigning
                if port_id_to_assign in assigned_ports:
                   del assigned_ports[port_id_to_assign]

            # 2. Assign the port to the selected input section in the config *object*
            if config.has_section(selected_input_name):
                config.set(selected_input_name, 'port', port_id_to_assign)
                assigned = True
                # Update internal tracking immediately
                assigned_ports[port_id_to_assign] = selected_input_name
            else:
                # Create section if needed (should be rare)
                config.add_section(selected_input_name)
                config.set(selected_input_name, 'port', port_id_to_assign)
                assigned = True
                # Update internal tracking
                assigned_ports[port_id_to_assign] = selected_input_name
                if hasattr(self.app, 'log_debug'): self.app.log_debug(f"Created section [{selected_input_name}] in config.")

            # --- Save Config using save_config ---
            if assigned:
                # save_config will write the current state of the config object
                save_config(config, config_file_path)
                if hasattr(self.app, 'log_debug'): self.app.log_debug(f"Assigned {port_id_to_assign} to {selected_input_name} in {config_file_path} via save_config")

                # --- RELOAD CONFIG AFTER REGULAR ASSIGN ---
                # Reload to ensure consistency
                try:
                    reloaded_config, reloaded_assigned_ports, reloaded_found, reloaded_error = load_config(config_file_path)
                    if not reloaded_error:
                        self.app.config = reloaded_config
                        self.app.assigned_ports = reloaded_assigned_ports
                        self.app.config_found = reloaded_found
                        self.app.config_error = reloaded_error
                        if log_func: log_func("Config reloaded successfully after assignment.")
                    else:
                        if log_func: log_func("Error reloading config immediately after assignment.")
                except Exception as e:
                    if log_func: log_func(f"Exception during config reload after assignment: {e}")
            else:
                 if hasattr(self.app, 'log_debug'): self.app.log_debug(f"Could not find section [{selected_input_name}] to assign port.")


        # --- Close screen ---
        self.app.pop_screen() # Return to the previous screen (PortSelectScreen)

        # Rely on periodic refresh in PortSelectScreen to show the update


    def on_mount(self) -> None:
        """Populate the list and pre-select the current assignment or [NONE]."""
        log_func = getattr(self.app, 'log_debug', None)
        if log_func:
            log_func(f"InputAssignScreen mounted for port: {self.selected_port_id}")
            log_func(f"Received {len(self._input_names)} total options (incl. [NONE]).")
            log_func(f"Options: {self._input_names[:6]}{'...' if len(self._input_names) > 6 else ''}")

        list_view = self.query_one("#input-list")
        list_view.clear()

        current_assignment = self.app.assigned_ports.get(self.selected_port_id)
        selected_index = 0 # Default to [NONE]

        # Create reverse mapping: input_name -> assigned_port_id
        input_to_assigned_port = {v: k for k, v in self.app.assigned_ports.items()}
        if log_func:
            log_func(f"Current assignment for {self.selected_port_id}: {current_assignment}")
            log_func(f"Reverse assignment map: {input_to_assigned_port}")


        if not self._input_names: # Should not happen due to [NONE] addition, but check anyway
            if log_func: log_func("Input list is empty. Cannot populate ListView.")
            return

        # Find the index of the current assignment *after* [NONE] was added
        if current_assignment:
            try:
                selected_index = self._input_names.index(current_assignment)
            except ValueError:
                 if log_func: log_func(f"WARN: Current assignment '{current_assignment}' not found in options list. Defaulting to [NONE].")
                 selected_index = 0 # Default to [NONE] if assignment is stale/invalid
        else:
            selected_index = 0 # Explicitly select [NONE] if port is not assigned

        for i, input_name in enumerate(self._input_names):
            assigned_port_id = input_to_assigned_port.get(input_name)
            # --- MODIFICATION START ---
            # Escape brackets in [NONE] so Rich renders it literally
            display_text = r"-- NONE --" if input_name == self.NONE_OPTION else input_name
            # --- MODIFICATION END ---

            # Add indicator if assigned to *another* port (skip for [NONE])
            if input_name != self.NONE_OPTION and assigned_port_id and assigned_port_id != self.selected_port_id:
                display_text += f"  [dim](uses: {assigned_port_id})[/]"

            label = Label(display_text)
            list_item = ListItem(label)
            list_view.append(list_item)

        # Pre-select the calculated index
        if 0 <= selected_index < len(self._input_names):
            if log_func:
                log_func(f"Pre-selecting index {selected_index} ('{self._input_names[selected_index]}')")
            list_view.index = selected_index
        elif self._input_names: # If list is not empty, select first item
             if log_func:
                 log_func(f"Calculated selected_index {selected_index} out of bounds. Selecting index 0 ('{self._input_names[0]}').")
             list_view.index = 0

    # --- Add on_key method for debugging ---
    def on_key(self, event) -> None:
        """Handle key press events for debugging."""
        log_func = getattr(self.app, 'log_debug', None)
        if log_func:
            log_func(f"KEY EVENT (InputAssignScreen): Key='{event.key}', Name='{event.name}', Character='{event.character}'")
            if event.key == "enter":
                log_func("KEY EVENT (InputAssignScreen): Enter key detected.")
                # --- ADDED: Explicitly call the action ---
                self.action_assign_input()
                # Prevent further default processing for enter key since we handled it
                event.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='List available serial ports and assign them to inputs in config.cfg')
    parser.add_argument('-o', '--output',
                       help='Output file path (default: available_serial_ports.json)')
    parser.add_argument('--select',
                       action='store_true',
                       help='Show interactive selection menu for port assignment')
    parser.add_argument('--input_sources',
                       action='store_true',
                       help='List available input source modules found in lib/inputs and exit')
    parser.add_argument('-d', '--debug',
                       action='store_true',
                       help='Enable debug logging in interactive mode')

    args = parser.parse_args()

    if args.input_sources:
        print("Scanning for available input sources...")
        available_inputs = get_available_inputs()
        if available_inputs:
            print("Found input sources:")
            for input_name in available_inputs:
                print(f" - {input_name}")
        else:
            # Provide more context on where it looked
            inputs_dir_path = os.path.join(project_root, 'lib', 'inputs')
            print(f"No input sources found in directory: {inputs_dir_path}")
            print("Ensure the directory exists and contains valid Python modules (e.g., 'module_name.py')")
        sys.exit(0) # Exit after listing sources

    if args.select:
        # The function now handles the interaction and config update.
        # The return value might not be needed unless we want to report the last assignment.
        select_serial_port(title="Assign Serial Port (Enter to Assign)", debug=args.debug)
        print("Interactive session finished. Check config.cfg for assignments.")

    # if output file is provided, save to file (Keep this functionality?)
    # This seems less relevant now the main goal is config assignment.
    if args.output:
        save_ports_to_file(args.output)

    # print out the ports if no other action was taken (or maybe always?)
    # Decide if this should run if --select was used. For now, let it run after select.
    if not args.select and not args.output and not args.input_sources: # Only print if no other action specified
        print("\nDetected Serial Ports:")
        print_out()
    elif args.select:
        print("\nDone")
         #print("\nFinal detected ports after interactive session:")
         #print_out() # Show final state after assignment