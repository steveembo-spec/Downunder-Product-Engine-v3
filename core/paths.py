r"""
Shared path resolver for all runtime modes.

Handles:
- DEV MODE: Running from project root with python desktop/app.py
- PORTABLE EXE MODE: Packaged exe in dist/ folder, data in parent directories
- INSTALLED MODE: Exe in C:\Program Files\..., data in C:\ProgramData\...

Single source of truth for PROJECT_ROOT and data locations.
All modules should use get_project_root(__file__) instead of duplicating logic.
"""

import sys
from pathlib import Path


def is_running_from_pyinstaller() -> bool:
    """Detect if running from PyInstaller packaged exe."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_project_root(caller_file: str) -> Path:
    r"""
    Get the project root directory (where output/, config/, assets/ are located).
    
    Handles both development and packaged exe modes.
    
    Args:
        caller_file: The __file__ of the calling module
        
    Returns:
        Path to the project root directory
        
    Logic:
        DEV MODE (not sys.frozen):
            Walk up 3 levels from caller's __file__ to project root
            Both catalogue_page.py and master_product_service.py are 3 levels deep
            
        EXE MODE (sys.frozen, portable exe in dist/):
            sys.executable = C:\path\to\dist\Downunder Product Engine.exe
            Project root is one level above dist/ (where output/ folder is)
            Verify by checking for output/ directory
    """
    
    if is_running_from_pyinstaller():
        # Running from packaged exe in dist/ folder (portable mode)
        # Find the directory containing output/, config/, etc.
        exe_dir = Path(sys.executable).parent      # dist/
        potential_project_root = exe_dir.parent    # parent of dist/
        
        # Verify this is the correct location
        if (potential_project_root / "output").exists():
            return potential_project_root
        
        # Fallback (shouldn't occur in normal deployment)
        return potential_project_root
    
    # Development mode
    # caller_file is __file__ from calling module
    # desktop/pages/catalogue_page.py → 3 levels to project_root
    # core/product/master_product_service.py → 3 levels to project_root
    return Path(caller_file).resolve().parent.parent.parent


def get_data_root() -> Path:
    r"""
    Get the data root directory (where database, config, logs are stored).
    
    Returns:
        Path to data root directory
        
    Priority:
        1. Check C:\ProgramData\Downunder Product Engine (installed mode)
        2. Check exe parent's parent for output/ folder (portable exe)
        3. Fall back to project root (dev mode)
    """
    
    # Check for installed mode first
    programdata_root = Path("C:/ProgramData/Downunder Product Engine")
    if programdata_root.exists():
        return programdata_root
    
    # Check for portable exe mode
    if is_running_from_pyinstaller():
        exe_dir = Path(sys.executable).parent      # dist/ or Program Files/
        potential_project_root = exe_dir.parent    # parent of dist/
        
        # Check if this looks like a portable exe location
        if (potential_project_root / "output").exists():
            return potential_project_root
    
    # Fall back to project root (dev mode)
    # Get a module we know is in the project (e.g., this file)
    core_module = Path(__file__).resolve().parent.parent
    return core_module


def get_database_path() -> Path:
    """
    Get the full path to the SQLite database file.
    
    Returns:
        Path to dpe_catalogue.db
        
    Layout:
        DEV/PORTABLE: data_root/output/dpe_catalogue.db
        INSTALLED: data_root/data/dpe_catalogue.db
    """
    data_root = get_data_root()
    
    # Check if in installed mode
    programdata_root = Path("C:/ProgramData/Downunder Product Engine")
    if data_root == programdata_root:
        return data_root / "data" / "dpe_catalogue.db"
    
    # Dev or portable mode
    return data_root / "output" / "dpe_catalogue.db"


def get_config_path() -> Path:
    """
    Get the path to the config directory.
    
    Returns:
        Path to config folder
        
    Layout:
        All modes: data_root/config/
    """
    return get_data_root() / "config"


def get_assets_path(caller_file: str) -> Path:
    """
    Get the path to bundled assets.
    
    Args:
        caller_file: The __file__ of the calling module
        
    Returns:
        Path to assets folder
        
    In exe mode: PyInstaller extracts assets to sys._MEIPASS/assets
    In dev mode: assets are in project_root/assets
    """
    if is_running_from_pyinstaller():
        # PyInstaller bundles assets and extracts them to sys._MEIPASS
        return Path(sys._MEIPASS) / "assets"
    
    # Development mode
    return get_project_root(caller_file) / "assets"
