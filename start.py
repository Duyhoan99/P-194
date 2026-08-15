import subprocess
import webbrowser
import time
import sys
import os

def main():
    print("Dang khoi dong Backend (cong 8000)...")
    # Đảm bảo sử dụng python trong thư mục .venv để tránh lỗi thiếu thư viện
    venv_python = os.path.join(".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = sys.executable
    
    # Khởi động Uvicorn
    try:
        backend = subprocess.Popen([venv_python, "-m", "uvicorn", "src.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"])
    except Exception as e:
        print("Lỗi khi khởi động backend:", e)
        sys.exit(1)
        
    # Check if backend crashed immediately
    time.sleep(2)
    if backend.poll() is not None:
        print("Backend đã thoát đột ngột! Hãy kiểm tra terminal.")
        
    print("Dang khoi dong Frontend (cong 3000)...")
    # Khởi động Next.js
    env = os.environ.copy()
    env["NEXT_PUBLIC_API_URL"] = "http://localhost:8000"
    frontend = subprocess.Popen("npm --prefix frontend run dev", shell=True, env=env)
    
    print("Doi 5 giay de may chu khoi dong xong...")
    time.sleep(5)
    
    print("Tu dong mo trinh duyet web...")
    webbrowser.open("http://localhost:3000")
    
    print("He thong dang chay! Nhan Ctrl+C o terminal nay de tat ca hai.")
    
    try:
        # Giữ script chạy và kiểm tra trạng thái của cả hai process
        while True:
            if backend.poll() is not None:
                print("\n[LỖI] Backend đã đột ngột thoát! Đang tắt hệ thống...")
                frontend.terminate()
                sys.exit(1)
            if frontend.poll() is not None:
                print("\n[LỖI] Frontend đã đột ngột thoát! Đang tắt hệ thống...")
                backend.terminate()
                sys.exit(1)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDang tat he thong...")
        backend.terminate()
        frontend.terminate()
        print("Da tat an toan!")

if __name__ == "__main__":
    main()
