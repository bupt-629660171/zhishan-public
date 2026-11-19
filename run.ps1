# 知源智膳 · 本地启动脚本
# 用法：.\run.ps1            默认密码 change-me
#       .\run.ps1 -Password '你的密码'
param(
    [string]$Password = 'change-me',
    [int]$Port = 8501
)
$env:ZY_ACCESS_PASSWORD = $Password
Write-Host "AI 功能密码：$Password （仅本次进程有效，不写入任何文件）" -ForegroundColor Cyan
streamlit run "$PSScriptRoot\app.py" --server.port $Port