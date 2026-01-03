import subprocess
from rich.prompt import Prompt, Confirm
from cortex.branding import console, cx_print, cx_header

class PrinterWizard:
    """
    Interactive wizard for setting up printers using CUPS (lpadmin).
    """

    def setup(self, dry_run=False):
        cx_header("Printer Auto-Setup (CUPS)")
        
        console.print("[dim]This wizard helps you add a printer via CUPS (lpadmin).[/dim]\n")
        
        # 1. Printer Name
        name = Prompt.ask("[bold cyan]Printer Name (no spaces)[/bold cyan]", default="MyPrinter")
        # Sanitize name
        name = name.replace(" ", "_")

        # 2. Connection Type
        conn_type = Prompt.ask(
            "Connection Type", 
            choices=["network", "usb", "manual_uri"], 
            default="network"
        )
        
        uri = ""
        if conn_type == "network":
            ip = Prompt.ask("Printer IP Address", default="192.168.1.100")
            proto = Prompt.ask("Protocol", choices=["socket", "ipp", "lpd"], default="socket")
            
            if proto == "socket":
                uri = f"socket://{ip}:9100"
            elif proto == "ipp":
                uri = f"ipp://{ip}/ipp/print"
            else:
                uri = f"lpd://{ip}/queue"
                
        elif conn_type == "usb":
            console.print("[yellow]Ensure printer is connected via USB.[/yellow]")
            # In a real app, we would run `lpinfo -v` to find USB devices
            uri = Prompt.ask("USB URI (run 'lpinfo -v' to find)", default="usb://...")
        else:
            uri = Prompt.ask("Enter full Device URI")

        # 3. Method/Driver
        console.print("\n[dim]Driver Selection:[/dim]")
        # 'everywhere' is reliable for modern IPP printers (driverless)
        driver_mode = Prompt.ask(
            "Driver/Model", 
            choices=["driverless (everywhere)", "ppd_file"], 
            default="driverless (everywhere)"
        )
        
        model_flag = ""
        if "driverless" in driver_mode:
            model_flag = "-m everywhere"
        else:
            ppd_path = Prompt.ask("Path to PPD file")
            model_flag = f"-P {ppd_path}"

        # 4. Description & Location (Optional)
        desc = Prompt.ask("Description", default="Office Printer")
        location = Prompt.ask("Location", default="Local")

        # Build Command
        # lpadmin -p <name> -v <uri> -E <model> -D <desc> -L <loc>
        # -E enables the printer
        cmd_parts = [
            "sudo", "lpadmin",
            "-p", name,
            "-v", uri,
            "-E",
            model_flag,
            "-D", f'"{desc}"',
            "-L", f'"{location}"'
        ]
        
        cmd_str = " ".join(cmd_parts)
        
        print()
        cx_print(f"Generated Command: [bold]{cmd_str}[/bold]", "info")
        
        if dry_run:
            cx_print("[Dry Run] Skipping execution.", "warning")
            return

        if Confirm.ask("Execute this command now?"):
            self._run_command(cmd_str)

    def _run_command(self, cmd_str):
        try:
            # We use shell=True to handle the quoted strings in sudo command properly if needed
            subprocess.check_call(cmd_str, shell=True)
            cx_print(f"Printer added successfully.", "success")
            
            # Optional: Test page
            if Confirm.ask("Print a test page?"):
                subprocess.call(f"lp -d {cmd_str.split()[3]} /usr/share/cups/data/testprint", shell=True)

        except subprocess.CalledProcessError as e:
            cx_print(f"Failed to add printer: {e}", "error")
        except Exception as e:
            cx_print(f"Error: {e}", "error")
