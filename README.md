# NIR Tracker Server

This project includes startup scripts to automatically create a Python virtual environment, install the necessary dependencies, and start the server.

### Windows (Recommended)
Simply double-click `run.bat` or run it from the command line:
```cmd
run.bat
```
This will create a `venv` folder if it doesn't already exist, install all requirements from `requirements.txt`, and start the `server.py` application.

### Mac / Linux
Make the shell script executable and run it:
```bash
chmod +x run.sh
./run.sh
```
This script performs the same setup process using bash.

### Manual Setup
If you want to manually create the environment instead:
1. `python -m venv venv`
2. Activate it (`venv\Scripts\activate` on Windows or `source venv/bin/activate` on Linux)
3. `pip install -r requirements.txt`
4. `python server.py`
"# NIR_Tracker" 
