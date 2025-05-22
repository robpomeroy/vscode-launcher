import ctypes
import dearpygui.dearpygui as dpg
import os
import json
import re
import subprocess
import sys
import logging
import win32gui
import win32con

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(
            os.path.dirname(os.path.abspath(__file__ if '__file__' in globals()
                                            else sys.executable)),
            'vscode_launcher.log'
        ), 'a')  # Changed from 'w' to 'a' for append mode
    ]
)
logger = logging.getLogger('VSCodeLauncher')

# Constants
VERSION = "v0.12.0"
WINDOW_TITLE = f"VSCodeLauncher {VERSION}"
DEFAULT_APP_HEIGHT = 300  # Default height if not specified in config
DEFAULT_APP_WIDTH = 500   # Default width if not specified in config
DEFAULT_BUTTON_WIDTH = DEFAULT_APP_WIDTH // 4 - 22
KEY_SHIFT = 16
KEY_TAB = 9
KEY_ENTER = 13
KEY_SPACE = 32
KEY_ESCAPE = 526
KEY_I = 554
KEY_N = 559
KEY_Q = 562
KEY_X = 569


def find_and_activate_window():
    """
    Find the VSCode Launcher window by title and bring it to the foreground.

    Returns:
        bool: True if window was found and activated, False otherwise
    """
    # Windows will receive the handles as a list
    found_windows = []

    def enum_window_callback(hwnd, _):
        # Get the window title
        try:
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                # Check if our application title is in the window title
                if WINDOW_TITLE in window_title:
                    found_windows.append(hwnd)
        except Exception:
            pass
        # Always return True to continue enumeration
        return True

    try:
        # Find all windows
        win32gui.EnumWindows(enum_window_callback, None)

        # Check if we found any matching windows
        if found_windows:
            hwnd = found_windows[0]

            # If window is minimized, restore it
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                # Ensure window is not hidden
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

            # Bring window to front using SetForegroundWindow
            win32gui.SetForegroundWindow(hwnd)

            # Extra steps to ensure window gets focus
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetActiveWindow(hwnd)

            logger.info(f"Found existing window with handle {hwnd}, bringing "
                        "to foreground")
            return True

        logger.info("No existing window found")
        return False

    except Exception as e:
        logger.error(f"Error finding window: {str(e)}")
        return False


# Global mutex handle to prevent it being garbage collected
mutex_handle = None


def is_already_running():
    """
    Check if another instance of the application is already running.

    Returns:
        bool: True if another instance is running, False otherwise
    """
    global mutex_handle

    try:
        # Use a unique mutex name with a UUID to ensure uniqueness
        mutex_name = "VSCodeLauncherMutex_3A47D619-B548-4F2B-A2DE-84B55C897881"

        # Create mutex with explicit initial ownership set to False (0)
        mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, 0, mutex_name)

        # GetLastError returns ERROR_ALREADY_EXISTS (183) if the mutex exists
        last_error = ctypes.windll.kernel32.GetLastError()

        # If mutex already exists, try to find the existing window
        if last_error == 183:  # ERROR_ALREADY_EXISTS
            logger.info("Mutex already exists, another instance is running")

            # Try to find and activate the existing window
            if find_and_activate_window():
                # Release our handle to the mutex since we're exiting
                if mutex_handle:
                    ctypes.windll.kernel32.CloseHandle(mutex_handle)
                    mutex_handle = None

                logger.info("Found and activated existing window")
                return True

            # If we couldn't find the window, previous instance may have
            # crashed
            logger.warning("Another instance detected but window not found. "
                           "Previous instance may have crashed. Starting new "
                           "instance.")

            # Don't release mutex handle - we'll become the active instance
        else:
            logger.info(
                "No existing instance detected, this is the first instance")

        # Keep mutex handle alive for the duration of the program
        return False

    except Exception as e:
        logger.error(f"Error checking for existing instance: {e}")
        # If there's an error, allow the application to run
        return False


def get_buttons_list(left_list, right_list):
    """Combine left and right button lists into a single list.
    This is a utility function used by several parts of the UI code.

    Args:
        left_list: List of buttons in the left column
        right_list: List of buttons in the right column

    Returns:
        Combined list of all buttons
    """
    return left_list + right_list


def load_config():
    """
    Load configuration from config.json file.

    Note: abspath() used to avoid path traversal issues.
    """
    try:
        if hasattr(sys, '_MEIPASS'):
            # Running from PyInstaller bundle; config should be in the same
            # directory as the executable.
            config_path = os.path.join(
                os.path.abspath(
                    os.path.dirname(sys.executable)), 'config.json')
        else:
            # Running in normal Python environment; config should be in the
            # same directory as this script.
            base_dir = os.path.abspath(os.path.dirname(__file__))
            config_path = os.path.abspath(
                os.path.join(base_dir, 'config.json'))

        # Create default config if it doesn't exist
        if not os.path.exists(config_path):
            # Extend the configuration to include VS Code Insiders commands
            default_config = {
                "windows_workspaces_path": "H:/Development/VS Code workspaces",
                "wsl_workspaces_path": "/mnt/h/Development/VS Code workspaces",
                "launch_options": {
                    "wsl_command": "wsl code",
                    "windows_command": "code.cmd",
                    "wsl_insiders_command": "wsl code-insiders",
                    "windows_insiders_command": "code-insiders.cmd"
                },
                "last_selected_option": "normal",  # Default to normal VS Code
                "window_size": {
                    "width": DEFAULT_APP_WIDTH,
                    "height": DEFAULT_APP_HEIGHT
                }
            }

            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(config_path)),
                        exist_ok=True)

            # Use secure file creation
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)

            # Set appropriate permissions on Windows
            if os.name == 'nt':
                import stat
                os.chmod(config_path, stat.S_IREAD | stat.S_IWRITE)

            return default_config
    except PermissionError as e:
        logger.error(f"Error: Cannot create configuration file: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating configuration: {e}")
        return None

    # Load existing config
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Error: Invalid JSON in {config_path}")
        return None


def get_data_file_path(filename):
    '''
    Get the path to a data file, either from the bundled application
    (PyInstaller) or from the current directory.
    '''
    if hasattr(sys, '_MEIPASS'):
        # Running from PyInstaller bundle
        return os.path.join(sys._MEIPASS, filename)
    else:
        # Running in normal Python environment
        return os.path.join(os.path.dirname(__file__), filename)


def validate_workspace_name(workspace):
    if not re.match(r'^[\w\s\[\]\-\.]+\.code-workspace$', workspace):
        logger.error(f"Invalid workspace name: {workspace}")
        return False
    return True


def get_workspaces(config):
    '''
    Get list of VS Code workspace files from the configured workspaces path
    and return as a dictionary of two lists:
    - files with "[WSL]" in the name
    - files with "[Win]" in the name

    Returns dictionary with:
    - "WSL": List of tuples (display_name, filename) for WSL workspaces
    - "Win": List of tuples (display_name, filename) for Windows workspaces
    '''
    windows_path = config.get("windows_workspaces_path",
                              "H:/Development/VS Code workspaces")

    workspaces = {
        "WSL": [],
        "Win": []
    }

    for root, dirs, files in os.walk(windows_path):
        for file in files:
            if file.endswith(".code-workspace"):
                # Create clean display name by removing [WSL]/[Win] and
                # extension
                if "[WSL]" in file:
                    display_name = file.split(" [WSL]")[0]
                    if validate_workspace_name(file):
                        workspaces["WSL"].append((display_name, file))
                elif "[Win]" in file:
                    display_name = file.split(" [Win]")[0]
                    if validate_workspace_name(file):
                        workspaces["Win"].append((display_name, file))

    return workspaces


def launch_workspace(workspace, wsl, config):
    '''
    Launch the specified workspace in VS Code. If wsl is True, launch in WSL
    mode, otherwise launch in Windows mode.

    Args:
        workspace: Name of the workspace file
        wsl: Whether to launch in WSL mode
        config: Configuration dictionary
    '''
    # Get configuration values
    windows_path = config.get("windows_workspaces_path",
                              "H:/Development/VS Code workspaces")
    wsl_path = config.get("wsl_workspaces_path",
                          "/mnt/h/Development/VS Code workspaces")
    launch_options = config.get("launch_options", {})

    # Validate workspace filename to prevent command injection
    if not workspace or not isinstance(workspace, str):
        error_msg = "Invalid workspace filename"
        dpg.set_value("status_text", error_msg)
        logger.error(error_msg)
        return

    # Only allow code-workspace files
    if not workspace.endswith('.code-workspace'):
        error_msg = "Invalid workspace file type"
        dpg.set_value("status_text", error_msg)
        logger.error(error_msg)
        return

    # Determine the command based on the selected option
    selected_option = config.get("last_selected_option", "normal")
    if wsl:
        workspace_path = f"{wsl_path}/{workspace}"
        if selected_option == "insiders":
            command = launch_options.get(
                "wsl_insiders_command", "wsl code-insiders").split()
        else:
            command = launch_options.get(
                "wsl_command", "wsl code").split()
    else:
        workspace_path = os.path.join(windows_path, workspace)
        if selected_option == "insiders":
            command = launch_options.get(
                "windows_insiders_command", "code-insiders.cmd").split()
        else:
            command = launch_options.get(
                "windows_command", "code.cmd").split()

    # Ensure the workspace path doesn't contain any shell metacharacters
    if any(c in workspace_path for c in ';$&|<>(){}!#'):
        error_msg = "Invalid characters in workspace path"
        dpg.set_value("status_text", error_msg)
        logger.error(error_msg)
        return

    try:
        # Launch VS Code with the workspace
        logger.info(f"Launching: {' '.join(command)} {workspace_path}")
        subprocess.Popen(command + [workspace_path],
                         shell=False,  # Avoid shell for better security
                         start_new_session=True)  # Detach from parent process
    except Exception as e:
        error_msg = f"Error launching workspace: {str(e)}"
        dpg.set_value("status_text", error_msg)
        logger.error(error_msg)


def save_window_size(config, width, height):
    """
    Save the current window size to the configuration file.

    Args:
        config: The configuration dictionary
        width: The current window width
        height: The current window height
    """
    if not config:
        return

    # Update the configuration with the new window size
    if "window_size" not in config:
        config["window_size"] = {}

    config["window_size"]["width"] = width
    config["window_size"]["height"] = height

    # Save the updated configuration back to the file
    try:
        config_path = os.path.join(
            os.path.dirname(__file__), 'config.json')
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        logger.debug(f"Saved window size: {width}x{height}")
    except Exception as e:
        logger.error(f"Error saving window size: {str(e)}")


def save_window_on_close(sender, app_data, user_data):
    """
    Save window dimensions when the application is closed.

    Args:
        sender: The sender of the callback
        app_data: Application data
        user_data: User data
    """
    # Get current viewport dimensions
    window_width = dpg.get_viewport_width()
    window_height = dpg.get_viewport_height()

    # Save window size to config
    config = load_config()
    if config:
        save_window_size(config, window_width, window_height)
        logger.debug(
            f"Saved window size on close: {window_width}x{window_height}")


def main():
    """
    Main application entry point. Sets up the UI, loads workspaces,
    and handles user interaction.
    """
    # Check if another instance is already running
    if is_already_running():
        logger.info("Another instance is already running. Exiting.")
        # Exit immediately with success code
        sys.exit(0)

    # Clear marker in logs
    logger.info("====== APPLICATION STARTING ======")    # Load configuration
    config = load_config()
    if not config:
        logger.error(
            "Error loading configuration. Please check config.json file.")
        return

    # Get window size from configuration or use defaults
    window_size = config.get("window_size", {})
    app_width = window_size.get("width", DEFAULT_APP_WIDTH)
    app_height = window_size.get("height", DEFAULT_APP_HEIGHT)

    # Calculate default button width based on app width
    button_width = app_width // 4 - 22

    # Navigation instructions
    instructions = ("Q/X/Escape: exit        N/I: Normal/Insiders        "
                    "Tab: navigate        Enter/Space: select")

    # Initialise the DearPyGui context and get the list of workspaces
    dpg.create_context()
    workspaces = get_workspaces(config)

    # Custom fonts
    bold_font = get_data_file_path("Manrope-Bold.ttf")
    semibold_font = get_data_file_path("Manrope-SemiBold.ttf")
    with dpg.font_registry():
        # Small
        with dpg.font(semibold_font, 15) as small_font:
            dpg.bind_font(small_font)

        # Standard/default font
        with dpg.font(bold_font, 19) as default_font:
            dpg.bind_font(default_font)
    # Track previous viewport size for dynamic resizing
    previous_width = [0]
    previous_height = [0]

    # Button width calculation values to be adjusted dynamically
    button_width = DEFAULT_BUTTON_WIDTH
    # Track the currently selected button index
    selected_button_idx = [0]    # Button collections
    wsl_buttons_left = []
    wsl_buttons_right = []
    win_buttons_left = []
    win_buttons_right = []

    # Helper function to get all buttons

    def get_all_buttons():
        wsl_buttons = get_buttons_list(wsl_buttons_left, wsl_buttons_right)
        win_buttons = get_buttons_list(win_buttons_left, win_buttons_right)
        return wsl_buttons + win_buttons

    # Define function to adjust widths based on viewport
    def adjust_layout():
        """
        Dynamically adjust layout when window is resized.

        This function:
        1. Checks if viewport dimensions have changed
        2. Updates panel widths to fill the space
        3. Adjusts button widths for consistent layout
        4. Saves window size to config when dimensions change
        """
        # Get current viewport dimensions
        window_width = dpg.get_viewport_width()
        window_height = dpg.get_viewport_height()

        # Only update if dimensions have changed
        if (window_width != previous_width[0]
                or window_height != previous_height[0]):
            previous_width[0] = window_width
            previous_height[0] = window_height

            # Calculate width for panels and buttons
            total_spacing = 40
            col_width = (window_width - total_spacing) / 2

            # Set each panel to be 50% of available width
            dpg.configure_item("WSL Workspaces", width=col_width)
            dpg.configure_item("Win Workspaces", width=col_width)

            # Update button width to be approximately 1/4 of window width
            # Accounting for padding/margins to prevent overflows
            new_button_width = (col_width / 2) - 12  # 12px margin

            # Update all button widths
            for button in get_all_buttons():
                dpg.configure_item(button, width=new_button_width)

            # Save window size to config when user resizes and only save if
            # significantly different (to avoid constant writes).
            # The use of the "significant_size_changed" variable is to fix
            # linting issues (line length/indentation).
            significant_size_changed = (
                abs(window_width - app_width) > 10 or
                abs(window_height - app_height) > 10
            )
            if significant_size_changed:
                save_window_size(config, window_width, window_height)
                logger.debug(
                    f"Saved window size: {window_width}x{window_height}")

    # Function to update button highlighting when selection changes
    def update_button_selection():
        all_buttons = get_all_buttons()
        if not all_buttons:
            return

        # Get the current index (make sure it's within bounds)
        idx = selected_button_idx[0] % len(all_buttons)
        selected_button = all_buttons[idx]

        # Update all button colors
        for button in all_buttons:
            if button == selected_button:
                # Selected button - highlight it
                dpg.bind_item_theme(button, selected_theme)
            else:
                # Other buttons - normal theme
                dpg.bind_item_theme(button, button_theme)
        button_label = dpg.get_item_label(selected_button)
        dpg.set_value("status_text",
                      f"Selected: {button_label}\n{instructions}")

    # Handle Tab key to move selection
    def tab_handler(sender, key_data):
        all_buttons = get_all_buttons()
        if not all_buttons:
            return

        logger.debug(f"Tab pressed! sender={sender}, key_data={key_data}")

        # Check if Shift is held
        shift_held = dpg.is_key_down(KEY_SHIFT)
        direction = -1 if shift_held else 1

        # Update selected index
        selected_button_idx[0] = ((selected_button_idx[0] + direction)
                                  % len(all_buttons))

        # Update button highlighting
        update_button_selection()

        return True

    def activate_selected_button():
        """Activate the currently selected button."""
        all_buttons = get_all_buttons()
        if not all_buttons or selected_button_idx[0] >= len(all_buttons):
            return False

        # Get the currently selected button
        selected_button = all_buttons[selected_button_idx[0]]

        # Get the user data (filename) and determine if it's WSL
        filename = dpg.get_item_user_data(selected_button)
        is_wsl = "[WSL]" in filename if filename is not None else False

        # Launch the workspace
        launch_workspace(filename, wsl=is_wsl, config=config)

        return True

    def enter_handler(sender, key_data):
        """
        Handle Enter and Space key presses to activate the selected button.
        """
        logger.debug(f"Enter/Space pressed! sender={sender}, "
                     f"key_data={key_data}")
        return activate_selected_button()

    def key_handler(sender, key_data):
        """
        Handle key presses for exiting the application and selecting VS Code
        versions.
        """
        key_pressed = key_data
        # Log all key presses to help debug key codes
        logger.info(f"Key pressed: {key_pressed} (sender: {sender})")

        # Exit on 'q' or 'x'
        if (key_pressed == KEY_Q or key_pressed == KEY_X
                or key_pressed == KEY_ESCAPE):
            logger.info(
                f"Key press recognized as Q/X ({key_pressed}), exiting...")
            dpg.stop_dearpygui()
            return True
        elif key_pressed == KEY_N:
            logger.info(
                f"Key press recognized as N ({key_pressed}), selecting Normal")
            # Log current value before change
            if dpg.does_item_exist("code_version_selector"):
                current_value = dpg.get_value("code_version_selector")
                logger.info(f"Current radio button value: {current_value}")
                # Set new value
                dpg.set_value("code_version_selector", "Normal")
                # Log new value after change
                new_value = dpg.get_value("code_version_selector")
                logger.info(f"New radio button value: {new_value}")
                update_last_selected_option("normal")
                # Update status text to indicate current selection
                dpg.set_value(
                    "status_text",
                    f"VS Code version set to: Normal\n{instructions}")
                # Force UI refresh
                dpg.configure_item("code_version_selector",
                                   default_value="Normal")
            else:
                logger.error("Radio button with tag 'code_version_selector' "
                             "does not exist!")
            return True
        # Handle 'I' key to select Insiders VS Code version
        elif key_pressed == KEY_I:  # Dear PyGui key code for 'I'
            logger.info(f"Key press recognized as I ({key_pressed}), "
                        "selecting Insiders")
            # Log current value before change
            if dpg.does_item_exist("code_version_selector"):
                current_value = dpg.get_value("code_version_selector")
                logger.info(f"Current radio button value: {current_value}")
                # Set new value
                dpg.set_value("code_version_selector", "Insiders")
                # Log new value after change
                new_value = dpg.get_value("code_version_selector")
                logger.info(f"New radio button value: {new_value}")
                update_last_selected_option("insiders")
                # Update status text to indicate current selection
                dpg.set_value(
                    "status_text",
                    f"VS Code version set to: Insiders\n{instructions}")
                # Force UI refresh
                dpg.configure_item("code_version_selector",
                                   default_value="Insiders")
            else:
                logger.error("Radio button with tag 'code_version_selector' "
                             "does not exist!")
            return True

        return False

    def create_workspace_buttons(workspace_list, is_wsl, left_group,
                                 right_group):
        """Create buttons for either WSL or Windows workspaces

        Args:
            workspace_list: List of (display_name, filename) tuples
            is_wsl: Whether these are WSL workspaces
            left_group: DPG item for the left column group
            right_group: DPG item for the right column group

        Returns:
            Tuple of (left_buttons, right_buttons) lists
        """
        left_buttons = []
        right_buttons = []

        for i, (display_name, filename) in enumerate(workspace_list):
            # Determine if this button goes in the left or right column
            is_left = i % 2 == 0
            parent = left_group if is_left else right_group
            target_list = left_buttons if is_left else right_buttons

            # Set parent context to the appropriate column
            dpg.push_container_stack(parent)

            # Create the button
            button = dpg.add_button(
                label=display_name,
                callback=lambda s, a, u: launch_workspace(
                    u, wsl=is_wsl, config=config
                ),
                user_data=filename,
                width=button_width
            )
            dpg.bind_item_font(button, small_font)
            target_list.append(button)

            # Restore parent context
            dpg.pop_container_stack()

        return left_buttons, right_buttons

    # Workspace panel (WSL/Windows)
    def create_workspace_panel(panel_tag, title_text, workspace_list, is_wsl,
                               left_buttons, right_buttons):
        """Create a workspace panel with buttons

        Args:
            panel_tag: Tag to use for the child window
            title_text: Title text to display
            workspace_list: List of workspaces to display
            is_wsl: Whether these are WSL workspaces
            left_buttons: List to store left column buttons
            right_buttons: List to store right column buttons
        """
        with dpg.child_window(tag=panel_tag, width=app_width // 2 - 20,
                              height=-45, border=True):
            # Add title text
            title = dpg.add_text(title_text)
            dpg.bind_item_font(title, default_font)

            # Create two-column layout
            with dpg.group(horizontal=True):
                # Create left and right columns
                with dpg.group():
                    left_col = dpg.last_item()
                with dpg.group():
                    right_col = dpg.last_item()

            # Create buttons and add them to our left/right lists
            left, right = create_workspace_buttons(
                workspace_list, is_wsl, left_col, right_col)
            left_buttons.extend(left)
            right_buttons.extend(right)

    # Create WSL workspace panel
    def create_wsl_panel():
        """Create the WSL workspaces panel"""
        create_workspace_panel(
            "WSL Workspaces",
            "WSL Workspaces",
            workspaces["WSL"],
            True,
            wsl_buttons_left,
            wsl_buttons_right
        )

    # Create Windows workspace panel
    def create_windows_panel():
        """Create the Windows workspaces panel"""
        create_workspace_panel(
            "Win Workspaces",
            "Windows Workspaces",
            workspaces["Win"],
            False,            win_buttons_left,
            win_buttons_right
        )

    # Create status bar
    def create_status_bar():
        """Create the status bar at the bottom of the window"""
        dpg.add_separator()
        # Using vertical group instead of horizontal to allow text wrapping
        with dpg.group():
            status_text = dpg.add_text(instructions, tag="status_text",
                                       wrap=app_width-20)
            dpg.bind_item_font(status_text, small_font)

    def create_radio_control():
        """
        Create a horizontal radio control for selecting VS Code or VS Code
        Insiders.
        """
        with dpg.group(horizontal=True):
            dpg.add_text("Select VS Code Version:")
            # Ensure the default value matches the case and format of the radio
            # button items
            default_value = ("Normal" if
                             config.get("last_selected_option",
                                        "normal").lower() == "normal"
                             else "Insiders")
            logger.info(
                f"Creating radio button with default value: {default_value}")
            radio_button = dpg.add_radio_button(
                items=["Normal", "Insiders"],
                default_value=default_value,
                callback=lambda sender,
                app_data: update_last_selected_option(app_data),
                tag="code_version_selector",
                horizontal=True
            )
            logger.info(f"Radio button created with ID: {radio_button}")

    def update_last_selected_option(selected_option):
        """Update the last selected option in the configuration."""
        config["last_selected_option"] = selected_option.lower()
        # Save the updated configuration back to the file
        config_path = os.path.join(
            os.path.dirname(__file__), 'config.json')
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)

    # Main window
    with dpg.window(tag="Primary Window"):
        create_radio_control()
        with dpg.group():
            # Workspace area (horizontal layout for WSL and Windows)
            with dpg.group(horizontal=True):
                create_wsl_panel()
                create_windows_panel()

            # Status bar
            create_status_bar()

    # Create themes for normal and selected buttons
    with dpg.theme() as button_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 10)
            dpg.add_theme_color(dpg.mvThemeCol_Button, [70, 70, 70])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, [100, 100, 100])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, [50, 150, 50])

    # Theme for the currently selected button - bright green
    with dpg.theme() as selected_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 10)
            dpg.add_theme_color(dpg.mvThemeCol_Button, [0, 150, 50])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, [0, 180, 70])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, [0, 200, 100])
            dpg.add_theme_color(dpg.mvThemeCol_Text, [255, 255, 255])

    # Apply theme to all buttons
    for button in get_all_buttons():
        dpg.bind_item_theme(button, button_theme)
    # Register key handlers
    with dpg.handler_registry():
        # General key handler
        # Tab key - navigate between buttons
        dpg.add_key_press_handler(callback=key_handler)
        dpg.add_key_press_handler(KEY_TAB, callback=tab_handler)

        # Enter key - activate selected button
        dpg.add_key_press_handler(KEY_ENTER, callback=enter_handler)

        # Space key - also activate selected button
        dpg.add_key_press_handler(KEY_SPACE, callback=enter_handler)

    # Run the app
    icon_path = get_data_file_path("VSCL.ico")
    dpg.create_viewport(
        title=WINDOW_TITLE, width=app_width, height=app_height,
        resizable=True, min_width=(DEFAULT_APP_WIDTH - 40),
        min_height=DEFAULT_APP_HEIGHT,
        small_icon=icon_path, large_icon=icon_path)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("Primary Window", True)

    # Adjust layout initially
    adjust_layout()

    # Set initial button selection
    if get_all_buttons():
        # Main loop to continuously check forw indow size changes
        update_button_selection()
    while dpg.is_dearpygui_running():
        # Check if window size has changed and update layout accordingly
        adjust_layout()
        dpg.render_dearpygui_frame()

    # Save window size on close
    save_window_on_close(None, None, None)
    dpg.destroy_context()

    # Release mutex when closing the application
    global mutex_handle
    if mutex_handle:
        logger.info("Releasing mutex handle on exit")
        ctypes.windll.kernel32.CloseHandle(mutex_handle)
        mutex_handle = None


if __name__ == '__main__':
    main()
