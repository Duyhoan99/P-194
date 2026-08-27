import subprocess
import webbrowser
import time
import sys
import os
import re
import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def start_cloudflared():
    cloudflared_bin = os.path.join("tools", "cloudflared.exe")
    if not os.path.exists(cloudflared_bin):
        return None, None
    
    print("\n[1/3] Dang khoi tao Cloudflare Tunnel cong khai...")
    try:
        proc = subprocess.Popen(
            [cloudflared_bin, "tunnel", "--url", "http://localhost:8000", "--no-autoupdate"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        url = None
        start_time = time.time()
        while time.time() - start_time < 12:
            line = proc.stderr.readline()
            if not line:
                time.sleep(0.1)
                continue
            m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if m:
                url = m.group(0)
                break
        
        if url:
            print(f"  -> Tunnel URL: {url}")
            # Update .env file automatically
            if os.path.exists(".env"):
                try:
                    with open(".env", "r", encoding="utf-8") as f:
                        env_content = f.read()
                    if "CARE_PLAN_PUBLIC_BASE_URL=" in env_content:
                        env_content = re.sub(
                            r"CARE_PLAN_PUBLIC_BASE_URL=.*",
                            f"CARE_PLAN_PUBLIC_BASE_URL={url}",
                            env_content,
                        )
                    else:
                        env_content += f"\nCARE_PLAN_PUBLIC_BASE_URL={url}\n"
                    with open(".env", "w", encoding="utf-8") as f:
                        f.write(env_content)
                except Exception as ex:
                    print("  (Luu .env khong thanh cong, van su dung bien moi truong truc tiep:", ex, ")")
        return proc, url
    except Exception as e:
        print("  Khong the khoi dong Cloudflare Tunnel:", e)
        return None, None

def main():
    lan_ip = get_local_ip()
    tunnel_proc, tunnel_url = start_cloudflared()
    
    backend_url = tunnel_url or f"http://{lan_ip}:8000"
    
    print("\n[2/3] Dang khoi dong Backend (cong 8000)...")
    venv_python = os.path.join(".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = sys.executable
    
    env = os.environ.copy()
    env["CARE_PLAN_PUBLIC_BASE_URL"] = backend_url
    
    try:
        backend = subprocess.Popen(
            [venv_python, "-m", "uvicorn", "src.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
            env=env,
        )
    except Exception as e:
        print("Lỗi khi khởi động backend:", e)
        if tunnel_proc:
            tunnel_proc.terminate()
        sys.exit(1)
        
    time.sleep(2)
    if backend.poll() is not None:
        print("Backend đã thoát đột ngột! Hãy kiểm tra terminal.")
        if tunnel_proc:
            tunnel_proc.terminate()
        sys.exit(1)
        
    print("\n[3/3] Dang khoi dong Frontend (cong 3000)...")
    frontend_env = env.copy()
    frontend_env["API_PROXY_TARGET"] = "http://127.0.0.1:8000"
    frontend = subprocess.Popen("npm --prefix frontend run dev", shell=True, env=frontend_env)
    
    print("\n" + "=" * 60)
    print("HE THONG DA SAN SANG!")
    print(f"Web App may tinh: http://localhost:3000")
    if tunnel_url:
        print(f"Link QR dien thoai: {tunnel_url}")
        print("   (Quet ma QR tren PDF se mo duoc tren moi mang 3G/4G/Wifi)")
    else:
        print(f"Link QR noi bo (cung Wifi): http://{lan_ip}:8000")
    print("=" * 60 + "\n")
    
    time.sleep(4)
    webbrowser.open("http://localhost:3000")
    print("Nhan Ctrl+C o terminal nay de dung toan bo he thong.\n")
    
    try:
        while True:
            if backend.poll() is not None:
                print("\n[LỖI] Backend đã đột ngột thoát! Đang tắt hệ thống...")
                frontend.terminate()
                if tunnel_proc:
                    tunnel_proc.terminate()
                sys.exit(1)
            if frontend.poll() is not None:
                print("\n[LỖI] Frontend đã đột ngột thoát! Đang tắt hệ thống...")
                backend.terminate()
                if tunnel_proc:
                    tunnel_proc.terminate()
                sys.exit(1)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDang tat he thong...")
        backend.terminate()
        frontend.terminate()
        if tunnel_proc:
            tunnel_proc.terminate()
        print("Da tat an toan!")

if __name__ == "__main__":
    main()
