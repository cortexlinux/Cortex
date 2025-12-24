import platform
import sys
import os

def print_header():
    print("\n" + "="*50)
    print("   🧠 Cortex AI - Installation Assistant")
    print("="*50 + "\n")
    print("This tool will help you generate the correct installation commands")
    print("based on your hardware and operating system.\n")

def get_user_choice(question, options):
    print(f"❓ {question}")
    for i, opt in enumerate(options, 1):
        print(f"   {i}. {opt}")
    
    while True:
        try:
            choice = int(input("\n👉 Enter your choice (number): "))
            if 1 <= choice <= len(options):
                return options[choice-1]
            print("❌ Invalid choice. Please try again.")
        except ValueError:
            print("❌ Please enter a number.")

def generate_guide():
    print_header()
    
    # 1. Detect/Ask OS
    detected_os = platform.system()
    os_options = ["Windows", "Linux", "macOS"]
    
    print(f"💻 Detected System: {detected_os}")
    target_os = get_user_choice("Which OS are you installing on?", os_options)

    # 2. Ask about GPU
    gpu_options = ["NVIDIA (CUDA)", "AMD (ROCm)", "Apple Silicon (M1/M2/M3)", "CPU Only (No dedicated GPU)"]
    target_gpu = get_user_choice("What type of Accelerator/GPU do you have?", gpu_options)

    # 3. Ask about Interface preference
    ui_options = ["CLI (Command Line Only)", "Web UI (Browser-based)", "API Server"]
    target_ui = get_user_choice("How do you want to run Cortex?", ui_options)

    print("\n" + "-"*50)
    print("🛠️  RECOMMENDED INSTALLATION STEPS")
    print("-"*50 + "\n")

    # Logic to generate commands
    print("1️⃣  Prerequisites:")
    if target_os == "Windows":
        print("   - Ensure Python 3.10+ is installed (checking: python --version)")
        print("   - Install Visual Studio C++ Build Tools")
    elif target_os == "Linux":
        print("   - sudo apt update && sudo apt install build-essential python3-dev")
    elif target_os == "macOS":
        print("   - Install Xcode Command Line Tools: xcode-select --install")

    print("\n2️⃣  Virtual Environment (Highly Recommended):")
    if target_os == "Windows":
        print("   python -m venv venv")
        print("   .\\venv\\Scripts\\activate")
    else:
        print("   python3 -m venv venv")
        print("   source venv/bin/activate")

    print("\n3️⃣  Install Cortex Core:")
    install_cmd = "pip install cortex-ai"
    
    if target_gpu == "NVIDIA (CUDA)":
        install_cmd += " --extra-index-url https://download.pytorch.org/whl/cu118"
    elif target_gpu == "AMD (ROCm)" and target_os == "Linux":
        install_cmd += " --extra-index-url https://download.pytorch.org/whl/rocm5.4.2"
    
    print(f"   {install_cmd}")

    print("\n4️⃣  Run Cortex:")
    if target_ui == "Web UI":
        print("   cortex-server --web")
    elif target_ui == "API Server":
        print("   cortex-server --host 0.0.0.0 --port 8000")
    else:
        print("   cortex run")

    print("\n" + "="*50)
    print("✅ Copy and paste these commands into your terminal.")
    print("="*50 + "\n")

if __name__ == "__main__":
    generate_guide()