"""
API Configuration for Bridge LSP Backend.

Provides dynamic WebSocket URL configuration for different client environments.
"""

import os
import socket


def get_local_ipv4() -> str:
    """Get the local IPv4 address of the machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


def get_websocket_base_url() -> str:
    """
    Get the WebSocket base URL for client connections.
    
    Priority:
    1. BRIDGE_WS_IPV4 environment variable (for production/docker)
    2. Auto-detected local IPv4 (for development with mobile devices)
    3. Fallback to localhost
    
    Returns:
        WebSocket base URL (e.g., "ws://192.168.1.100:8000")
    """
    env_ip = os.environ.get("BRIDGE_WS_IPV4")
    if env_ip:
        return f"ws://{env_ip}:8000"
    
    local_ip = get_local_ipv4()
    return f"ws://{local_ip}:8000"


WS_BASE_URL = get_websocket_base_url()
