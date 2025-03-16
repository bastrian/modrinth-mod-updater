@echo off
REM Create a virtual environment in the "venv" folder
python -m venv venv

REM Activate the virtual environment
call venv\Scripts\activate

REM Upgrade pip
pip install --upgrade pip

REM Install required packages from requirements.txt
pip install -r requirements.txt

echo.
echo Setup complete. To run the updater, use:
echo python main.py
pause