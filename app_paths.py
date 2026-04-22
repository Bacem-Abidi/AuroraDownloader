from pathlib import Path

def get_app_data_dir() -> Path:
    """Return the base directory for all application data (config, logs, history, etc.)"""
    data_dir = Path.home() / '.local/share/auroradownloader'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def get_config_dir() -> Path:
    return get_app_data_dir() / 'config'

def get_logs_dir() -> Path:
    return get_app_data_dir() / 'logs'

def get_history_dir() -> Path:
    return get_app_data_dir() / 'history'

def get_fail_dir() -> Path:
    return get_app_data_dir() / 'fail'

def get_migration_dir() -> Path:
    return get_app_data_dir() / 'migration'

def get_cache_dir() -> Path:
    return get_app_data_dir() / 'cache'
