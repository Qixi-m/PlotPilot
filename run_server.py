#!/usr/bin/env python3
"""
智能启动脚本：自动检测并清理占用端口的进程
"""
import subprocess
import sys
import os
import socket
import time
import signal
from pathlib import Path

def find_pid_by_port(port):
    """查找占用指定端口的进程PID"""
    try:
        # Windows
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True,
            encoding='gbk',
            errors='ignore'
        )
        for line in result.stdout.split('\n'):
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.strip().split()
                if len(parts) >= 5:
                    return int(parts[-1])
    except Exception as e:
        print(f"查找端口进程失败: {e}")
    return None

def kill_process(pid):
    """杀掉指定PID的进程"""
    try:
        # Windows
        subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                      capture_output=True, check=True)
        return True
    except Exception as e:
        print(f"杀掉进程失败: {e}")
        return False

def check_port_available(port, host='127.0.0.1'):
    """检查端口是否可用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result != 0  # 0表示端口被占用
    except:
        return False

def clean_port(port):
    """清理占用端口的进程"""
    pid = find_pid_by_port(port)
    if pid:
        print(f"发现端口 {port} 被进程 PID={pid} 占用，正在清理...")
        if kill_process(pid):
            time.sleep(1)
            print(f"[OK] 端口 {port} 已释放")
            return True
        else:
            print(f"[ERR] 无法释放端口 {port}")
            return False
    return True

def start_backend(port=8005):
    """启动后端服务"""
    print(f"正在启动后端服务...")

    # 检查并清理端口
    if not check_port_available(port):
        clean_port(port)

    # 再次检查
    if not check_port_available(port):
        print(f"端口 {port} 仍被占用，尝试使用 8006...")
        port = 8006
        if not check_port_available(port):
            clean_port(port)

    # 启动服务
    os.chdir('D:/CODE')
    import subprocess
    process = subprocess.Popen([
        sys.executable, '-m', 'aitext', 'serve',
        '--host', '127.0.0.1',
        '--port', str(port)
    ])

    print(f"[OK] 后端已启动: http://127.0.0.1:{port}")
    print(f"   PID: {process.pid}")
    if port != 8005:
        print(
            "[WARN] 后端未使用默认端口 8005，请把 web-app/vite.config.ts 里 proxy['/api'].target"
            f" 改为 http://127.0.0.1:{port}，否则前端 API 与实时日志会连错地址。",
            flush=True,
        )
    return process, port

def start_frontend(port=3001):
    """启动前端服务（Windows 下用 shell 调用 npm，避免 PATH 找不到）。"""
    print("正在启动前端服务...")
    web_app = Path(__file__).resolve().parent / "web-app"

    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "node.exe", "/FI", "WINDOWTITLE eq vite*"],
            capture_output=True,
        )
        time.sleep(1)
    except Exception:
        pass

    cwd = str(web_app)
    if sys.platform == "win32":
        cmd = f'npm run dev -- --port {port}'
        process = subprocess.Popen(cmd, shell=True, cwd=cwd)
    else:
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(port)],
            cwd=cwd,
        )

    print(f"[OK] 前端已启动: http://localhost:{port}")
    print(f"   PID: {process.pid}")
    return process, port

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='启动书稿工作台')
    parser.add_argument('--backend-port', type=int, default=8005, help='后端端口')
    parser.add_argument('--frontend-port', type=int, default=3001, help='前端端口')
    parser.add_argument('--backend-only', action='store_true', help='只启动后端')

    args = parser.parse_args()

    print("=" * 50)
    print("书稿工作台 - 启动脚本")
    print("=" * 50)

    backend_proc, backend_port = start_backend(args.backend_port)

    if not args.backend_only:
        frontend_proc, frontend_port = start_frontend(args.frontend_port)

        print("\n" + "=" * 50)
        print("[OK] 全部启动完成！")
        print(f"   前端: http://localhost:{frontend_port}")
        print(f"   后端: http://127.0.0.1:{backend_port}")
        print("=" * 50)
        print("\n按 Ctrl+C 停止服务")

        try:
            frontend_proc.wait()
        except KeyboardInterrupt:
            print("\n正在停止服务...")
            frontend_proc.terminate()
            backend_proc.terminate()
    else:
        print("\n按 Ctrl+C 停止后端服务")
        try:
            backend_proc.wait()
        except KeyboardInterrupt:
            print("\n正在停止后端服务...")
            backend_proc.terminate()
