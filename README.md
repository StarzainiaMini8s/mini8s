# Mini8s (v0.3.98.2)
<img width="400" height="356" alt="mini8s_revised_logo-nover" src="https://github.com/user-attachments/assets/9154b59d-c126-440a-9255-c345a322540e" />



**Why hello there! This is Mini8s, a weather application created by me (Starzainia) and HexagonMidis! Below is a rundown of what this application can do as of v0.3.98.2:**

- Show radar data for ones zip code
- Show current conditions for ones zip code
- Show a 72 hour forecast for ones zip code
- Show any active alerts for ones zip code (Severe Thunderstorm Warning, Tornado Warning, Hurricane Warning, etc...)
- Read out multiple alerts one-by-one.
- Mini8s can do certain things based on what alert the user is under.
- Keep values for resolution and the users zip. (The user can press enter to skip typing a value on the next start of Mini8s)
- Show a dot of the users current location (via their ZIP code)
- Play alert tones for either watches or warnings issued for the users area.


****HOW TO INSTALL/RUN****

WINDOWS:
(Windows 7 to 11 will run Mini8s fine, but I do not offically support running Mini8s on Windows 7!)
- Go to the RELEASE page of this GitHub page, in there, you will find the Mini8s program binary (mini8s_windows-x64), download it, put it whereever (except for the .exe! it won't work if you take out the EXE from the main directory!)
- Simply just double-click to launch, and you will be brought up to a terminal window as normal!

LINUX: 
(Any Linux distro supporting Python 3.9 or higher or any Linux distro that can support at least Pygame-ce 2.0!)
- Go to the RELEASE page of this GitHub page (like with Windows), you will find the Mini8s Linux binary there. (mini8s_linux-x64/mini8s_linux-arm64), download it, then, open a terminal window.
- Then, do "cd mini8s" (usually "cd Downloads/mini8s"), then, simply type "./mini8s" Mini8s will then run normally!


SOURCE FILE:

Download the source file via clicking **Code** then **Download Zip**:

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

---

# AS OF v0.3.98.2

Here will be the roadmap for Mini8s, going out with 1 patches and 1 major update into the future.
Shown here will be the planned features and patches for the next versions of Mini8s!

**v0.3.99**
- Add more LDL bars (for specific alerts)
- Give RedMode activation for Tornado Watches/Warnings.
- Completely revamp initial setup
- Add a "Radar + Wind (4 Hours)" for users under a Hurricane or Tropical Storm Warning (will give a wind and gust reading for the past 4 hours until present for areas within 200 km/125mi of the user)
- Re-add (from mini8s-legacy in v0.3.96/v0.3.97) the FPS counter (optional)
- Add changing temperature text for cold weather events.
- Add a BSOD/fatal exception screen for the main radar GIF.
- (?) Add a regional forecast for the users area.

**v0.3.99.1**
- Further build on and optimize the features added in v0.3.99
- Fix any bugfixes/regressions
- A lot of what you see here will generally gauge on what happens in v0.3.99!

---

# Mini8s FAQ:

> When will [VERSION] come out?
- Generally, patches and small QoL releases (v0.0.00.X) can be released within about a week or so of development.. I can generally get it out the door fast and can fix any known regressions found.
- On the other hand.. large updates (v0.0.0X.0) [v0.3.98.2 --> v0.3.99] will ALWAYS take usually a month or two to get ready, it almost always depends on the features that can be listed in the ROADMAP.md file.

> Will this be ported to Rust?
- Not until it is battle tested. NO. (plus, what kind of local FOSS weather app needs le heckin' chungus wholesome memory safety?)

> Will this be ported to [LANGUAGE OTHER THAN RUST]
- I'm uncertain on porting this to any other language at all, while yes, porting this to something near-ASM code (C or whatever) would provide a substantial performance uplift, I am not ready to undergo such an endeavor, nor am willing to spend months learning a new language right now. This is a project I do in my free time!

> Will Mini8s have theming?
- I'm hesitant on adding some sort of theming system for one good reason: Most of what you see with Mini8s is modular/pre-rendered vector images. If you feel the need to change the theme, it's right there in the binary or source code you've downloaded!

> Why CC0? (public domain)
- I personally do not believe in copyright/intellectual property on a moral and logical basis. This code can inherently be copied a million times, and is infinite. I refuse to coerce anyone if they choose to fork my code without my "offical permission", but asking me to fork would be great! (I could help!)

> What were the versions before the current one? 
- I have recently released a giant blob of source code .zip files containg every version from v0.3.21 to v0.3.97.1! 

> What is RedMode?
- RedMode is a feature that will activate in a Hurricane alert or Tornado Watch (soon!), as of v0.3.98.2 RedMode is limited, but this will change!

> How do I get the source code? 
- Download it straight from the green [<> Code ^] bubble!

> Can I fork this?
- Just ask, no copyright/license attatched!

-----------------------------------------------------------------------------
**Credits:**
https://github.com/pygame-community/pygame-ce
