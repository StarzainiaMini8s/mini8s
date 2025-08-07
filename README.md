# Mini8s (v0.3.98)

Why hello there! This is Mini8s, a weather application created by me (Starzainia) and HexagonMidis! Below is a rundown of what this application can do as of v0.3.98:

- Show radar data for ones zip code
- Show current conditions for ones zip code
- Show a 72 hour forecast for ones zip code
- Show any active alerts for ones zip code (Severe Thunderstorm Warning, Tornado Warning, Hurricane Warning, etc...)
- Read out multiple alerts one-by-one.
- Mini8s can do certain things based on what alert the user is under.
- Keep values for resolution and the users zip. (The user can press enter to skip typing a value on the next start of Mini8s)


****HOW TO INSTALL/RUN****

WINDOWS:
(Windows 10/11 is offically supported by Mini8s, but I cannot rule out Mini8s working on Windows 7)
- Go to the RELEASE page of this GitHub page, in there, you will find the Mini8s program binary (mini8s_windows-x64), download it, put it whereever (except for the .exe! it won't work if you take out the EXE from the main directory!)
- Simply just double-click to launch, and you will be brought up to a terminal window as normal!

LINUX: 
(Any Linux distro supporting Python 3.9 or higher or any Linux distro that can support at least Pygame-ce 2.0!)
- Go to the RELEASE page of this GitHub page (like with Windows), you will find the Mini8s Linux binary there. (mini8s_linux-x64), download it, then, open a terminal window.
- Then, do "cd mini8s" (usually "cd Downloads/mini8s"), then, simply type "./mini8s" Mini8s will then run normally!


SOURCE FILE:

Download the source file via clicking <Code> then **Download Zip**:

WINDOWS: 
- Install pip via their website (since Python is likely pre-installed)
- Then, run the following command: **pip install pygame-ce requests pillow bs4**
- Then, navigate to the mini8s directory, then, run this: **python mini8s.py**

LINUX:
- Run **python3 -m venv "myenv"** (you may name the myenv whatever you want)
- Going off of this, you created a venv in your home directory, so, run the following:
- **source myenv/bin/activate**
- Then, run the following command: **pip install pygame-ce requests pillow bs4**
- Then, naviagate to the mini8s directory, then run this: **python mini8s.py**

