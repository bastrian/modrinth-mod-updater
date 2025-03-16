#!/bin/bash
# Create a virtual environment in the "venv" folder
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install required packages from requirements.txt
pip install -r requirements.txt

echo "Setup complete. To run the updater, use:"
echo "python main.py"
