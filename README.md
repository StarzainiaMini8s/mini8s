# Mini8s (v0.3.99.1)
<img width="400" height="356" alt="mini8s_logo_verstring" src="https://github.com/user-attachments/assets/3d16631e-d475-4018-95b1-8326d7140232" />


# Why hello there! This is _Mini8s_, a weather application created by Starzainia (me) and HexagonMidis! Below is a rundown of what this application can do as of v0.3.99.1:

- Show radar data for ones zip code
- Show radar and sattelite data for ones zip code if under a tropical storm or hurricane alert.
- Show current conditions for ones zip code
- Show a 72 hour forecast for ones zip code
- Show any active alerts for ones zip code (Severe Thunderstorm Warning, Tornado Warning, Hurricane Warning, etc...)
- Read out multiple alerts one-by-one.
- Mini8s can do certain things based on what alert the user is under.
- Keep values for resolution and the users zip. 
- Show a dot of the users current location (via their ZIP code)
- Play alert tones for either watches or warnings issued for the users area.
- Show a users framerate
- Has a **setup screen** to allow the user to quickly get started using Mini8s!
- Save any ticked options from the setup screen!


****HOW TO INSTALL/RUN****

WINDOWS:
(Windows 7 to 11 are officially supported) 
- Go to the RELEASE page of this GitHub page, in there, you will find the Mini8s program binary (mini8s_windows-x64), download it, put it whereever (except for the .exe! it won't work if you take out the EXE from the main directory!)
- Simply just double-click to launch, and you will be brought up to the setup screen!

LINUX: 
(Any Linux distro supporting Python 3.9 or higher or any Linux distro that can support at least Pygame-ce 2.0!)
- Go to the RELEASE page of this GitHub page (like with Windows), you will find the Mini8s Linux binary there. (mini8s_linux-x64/mini8s_linux-arm64), download it, then, open a terminal window.
- Then, do "cd mini8s" (usually "cd Downloads/mini8s"), then, simply double-click Mini8s and enjoy!


SOURCE FILE:

Download the source file via clicking **Code** then **Download Zip**:

WINDOWS: 
- Install pip via their website (since Python is likely pre-installed)
- Then, run the following command: **pip install pygame-ce pyqt5 requests pillow bs4**
- Then, navigate to the mini8s directory, then, run this: **python mini8s.py**

LINUX:
- Run **python3 -m venv "myenv"** (you may name the myenv whatever you want)
- Going off of this, you created a venv in your home directory, so, run the following:
- **source myenv/bin/activate**
- Then, run the following command: **pip install pygame-ce pyqt5 requests pillow bs4**
- Then, naviagate to the mini8s directory, then run this: **python mini8s.py**
(Note: ARM64 Linux will require you to manually compile pygame-ce, for some reason it can't be installed normally through pip?)

-----------------------------------------------------------------------------
**Credits:**
https://github.com/pygame-community/pygame-ce
