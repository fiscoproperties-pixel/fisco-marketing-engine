@echo off
python -m pip install -r requirements.txt
python -m playwright install chromium
echo Setup complete.
pause
