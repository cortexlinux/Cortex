import subprocess

def setup_printer(name, connection):
    """Automates printer setup using lpadmin."""
    print(f"Adding printer {name} with connection {connection}...")
    try:
        subprocess.run(["sudo", "lpadmin", "-p", name, "-E", "-v", connection], check=True)
        print(f"SUCCESS: Printer {name} is ready.")
    except Exception as e:
        print(f"ERROR: Failed to setup printer. {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: printer_helper <name> <connection_url>")
        sys.exit(1)
    setup_printer(sys.argv[1], sys.argv[2])
