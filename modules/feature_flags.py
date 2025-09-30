"""
Feature flags for toggling functionality on/off.

Simple boolean flags to control features without removing code.
"""

# Feature flags - set to True to enable, False to disable
FEATURES = {
    "backup_system": False,  # Automatic backups and backup UI controls
    "export_csv": True,  # CSV export functionality
}


def is_enabled(feature_name: str) -> bool:
    """
    Check if a feature is enabled.

    Args:
        feature_name: Name of the feature to check

    Returns:
        True if feature is enabled, False otherwise
    """
    return FEATURES.get(feature_name, False)
