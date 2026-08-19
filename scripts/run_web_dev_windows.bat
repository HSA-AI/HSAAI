@echo off
cd /d %~dp0\apps\web
npm install
npm run dev
pause
