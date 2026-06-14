import os
import sys
import shutil
import subprocess
import json
from urllib.parse import urlparse

SERVICE_NAME = "tlgrm-daemon"
USER_SERVICE_DIR = os.path.expanduser("~/.config/systemd/user")
SERVICE_FILE_PATH = os.path.join(USER_SERVICE_DIR, f"{SERVICE_NAME}.service")


def validate_webhook_url(url):
    """Reject URLs that aren't plain http(s) or that could break/inject the
    systemd unit file (whitespace, newlines, control characters)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid webhook URL (must be http/https): {url!r}")
    if any(c.isspace() or ord(c) < 32 for c in url):
        raise ValueError("Webhook URL must not contain whitespace or control characters")


def validate_webhook_headers(headers):
    """Ensure each header is 'Name: Value' with no characters that could break
    the systemd ExecStart line."""
    for header_str in headers or []:
        if ":" not in header_str:
            raise ValueError(f"Invalid header (expected 'Name: Value'): {header_str!r}")
        if any(c in header_str for c in ("\n", "\r", '"')) or any(ord(c) < 32 for c in header_str):
            raise ValueError(f"Header contains illegal characters: {header_str!r}")

def check_systemctl():
    if not shutil.which("systemctl"):
        return False
    return True

def run_systemctl_cmd(args):
    try:
        result = subprocess.run(
            ["systemctl", "--user"] + args,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr

def daemon_install(webhook_url, webhook_headers=None, verbose=False):
    if not check_systemctl():
        print(json.dumps({"success": False, "error": "systemctl not found. Is systemd installed?"}, indent=2))
        return

    try:
        validate_webhook_url(webhook_url)
        validate_webhook_headers(webhook_headers)
    except ValueError as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))
        return

    # Find the absolute path to the tlgrm binary
    tlgrm_path = shutil.which("tlgrm")
    if not tlgrm_path:
        # Fallback to sys.argv[0] if not found in PATH
        tlgrm_path = os.path.abspath(sys.argv[0])
    
    verbose_flag = "--verbose" if verbose else ""
    
    # Process custom headers into command arguments
    header_args = []
    if webhook_headers:
        for header_str in webhook_headers:
            header_args.append(f'--webhook-header "{header_str}"')
    header_str = " ".join(header_args)
    
    # Construct service contents
    service_content = f"""[Unit]
Description=tlgrm webhook daemon
After=network.target

[Service]
ExecStart={tlgrm_path} listen --webhook-url {webhook_url} {header_str} {verbose_flag}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
    
    try:
        # The unit embeds webhook headers, which may carry secrets (e.g. a
        # bearer token), so keep the directory and file owner-only readable.
        os.makedirs(USER_SERVICE_DIR, mode=0o700, exist_ok=True)
        os.chmod(USER_SERVICE_DIR, 0o700)
        fd = os.open(SERVICE_FILE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(service_content)
        os.chmod(SERVICE_FILE_PATH, 0o600)
        
        # Reload daemon
        success, out, err = run_systemctl_cmd(["daemon-reload"])
        if not success:
            raise Exception(f"daemon-reload failed: {err}")
            
        # Enable and start service
        success, out, err = run_systemctl_cmd(["enable", f"{SERVICE_NAME}.service"])
        if not success:
            raise Exception(f"enable failed: {err}")
            
        success, out, err = run_systemctl_cmd(["start", f"{SERVICE_NAME}.service"])
        if not success:
            raise Exception(f"start failed: {err}")
            
        print(json.dumps({
            "success": True,
            "message": "tlgrm daemon installed and started successfully!",
            "service": SERVICE_NAME,
            "path": SERVICE_FILE_PATH,
            "webhook_url": webhook_url,
            "webhook_headers": webhook_headers or [],
            "executable": tlgrm_path
        }, indent=2))
        
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))

def daemon_uninstall():
    if not check_systemctl():
        print(json.dumps({"success": False, "error": "systemctl not found."}, indent=2))
        return
        
    try:
        # Stop service
        run_systemctl_cmd(["stop", f"{SERVICE_NAME}.service"])
        # Disable service
        run_systemctl_cmd(["disable", f"{SERVICE_NAME}.service"])
        
        # Remove file
        if os.path.exists(SERVICE_FILE_PATH):
            os.remove(SERVICE_FILE_PATH)
            
        # Reload daemon
        run_systemctl_cmd(["daemon-reload"])
        
        print(json.dumps({
            "success": True,
            "message": "tlgrm daemon uninstalled and removed successfully!"
        }, indent=2))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))

def daemon_status():
    if not check_systemctl():
        print(json.dumps({"success": False, "error": "systemctl not found."}, indent=2))
        return
        
    # Check if file exists
    if not os.path.exists(SERVICE_FILE_PATH):
        print(json.dumps({
            "success": True,
            "installed": False,
            "status": "not installed"
        }, indent=2))
        return
        
    # Run show and is-active
    success_active, out_active, _ = run_systemctl_cmd(["is-active", f"{SERVICE_NAME}.service"])
    success_enabled, out_enabled, _ = run_systemctl_cmd(["is-enabled", f"{SERVICE_NAME}.service"])
    
    # Read properties for details
    _, out_show, _ = run_systemctl_cmd(["show", f"{SERVICE_NAME}.service", "--property=ActiveState,SubState,LoadState,UnitFileState,MainPID"])
    
    props = {}
    for line in out_show.strip().split("\n"):
        if "=" in line:
            k, v = line.split("=", 1)
            props[k] = v
            
    print(json.dumps({
        "success": True,
        "installed": True,
        "service": SERVICE_NAME,
        "active_state": props.get("ActiveState", "unknown"),
        "sub_state": props.get("SubState", "unknown"),
        "enabled": out_enabled.strip() == "enabled",
        "load_state": props.get("LoadState", "unknown"),
        "main_pid": int(props.get("MainPID", "0")),
        "unit_file_path": SERVICE_FILE_PATH
    }, indent=2))

def daemon_logs():
    try:
        # Use journalctl to get recent daemon logs
        result = subprocess.run(
            ["journalctl", "--user", "-u", SERVICE_NAME, "-n", "30", "--no-pager"],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
    except Exception as e:
        print(f"Error reading daemon logs: {e}")
