@echo off
cd /d "%~dp0"
where streamlit >nul 2>nul
if errorlevel 1 (
  echo 未检测到 Streamlit，请先运行：pip install -r requirements.txt
  pause
  exit /b 1
)
echo 正在启动英语思维训练器...
rem 延迟 3 秒再开浏览器，避免页面比服务先到、白屏
start "" cmd /c "timeout /t 3 >nul & start http://localhost:8501"
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
