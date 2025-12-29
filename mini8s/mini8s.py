import pygame # Community Edition as of v0.3.98!
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QLabel, QComboBox, QLineEdit, QPushButton, QMessageBox,
                           QMenu, QCheckBox)
from PyQt5.QtGui import QPixmap, QPalette, QFont, QImage, QBrush, QFontDatabase, QTransform
from PyQt5.QtCore import Qt, QSize, QPoint
from PyQt5.QtWidgets import QMenu, QCheckBox, QActionGroup
import sys
import traceback
import os
import requests
import json
import io
from PIL import Image, ImageSequence
import time
from datetime import datetime
import sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pygame.image
import threading
import queue
import pygame.freetype
import random
import math
import re

def log_fatal_error(error_message):
    # In case of a crash/failiure of the main radar GIF.
    try:
        # YMDHMS timestamp in the file name
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"log/mini8s-crash_{timestamp}.txt"
        log_content = (
            "Well crap, looks like Mini8s has crashed! DX\n"
            "\n"
            "Below is an output of the error that caused Mini8s to crash!\n"
            "\n"
            f"{error_message}"
        )

        # Write to file
        with open(log_filename, 'w') as log_file:
            log_file.write(log_content)
        print(f"Error log saved to: {log_filename}")
    except Exception as e:
        # Hopefully this doesn't have to be used!
        print(f"Failed to write error log: {e}")

VERSION = "v0.3.99.1 [BETA]"

try:
    with open('var/motd.json', 'r') as f:
        MOTD_CONFIG = json.load(f)
except Exception as e:
    print(f"Could not load motd.json: {e}")
    MOTD_CONFIG = {
        "normal_messages": ["Welcome to Mini8s!"],
        "tropical_messages": ["Tropical threat detected!"],
        "redmode_messages": ["Hurricane threat detected!"]
    }

def get_random_motd(is_tropical=False, is_redmode=False):
    if is_redmode:
        return random.choice(MOTD_CONFIG.get('redmode_messages', ["HURRICANE WARNING - !!!TAKE ACTION!!!"]))
    elif is_tropical:
        return random.choice(MOTD_CONFIG.get('tropical_messages', ["Tropical system detected!"]))
    else:
        return random.choice(MOTD_CONFIG.get('normal_messages', ["Welcome!"]))

with open('var/cond_names.json', 'r') as f:
    WEATHER_ICON_CONFIG = json.load(f)

def create_gradient_text_surface(text, font_path, font_size, color_top, color_bottom, outline_color=None, outline_width=0):
    try:
        font = pygame.font.Font(font_path, font_size)
    except:
        font = pygame.font.SysFont(None, font_size)
    # Create initial text surface to get dimensions
    text_surface = font.render(text, True, (255, 255, 255))
    padding = outline_width * 2
    full_width = text_surface.get_width() + padding
    full_height = text_surface.get_height() + padding
    final_surface = pygame.Surface((full_width, full_height), pygame.SRCALPHA)

    if outline_color and outline_width > 0:
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    outline_surface = font.render(text, True, outline_color)
                    final_surface.blit(outline_surface, (outline_width + dx, outline_width + dy))
    gradient_surface = pygame.Surface(text_surface.get_size(), pygame.SRCALPHA)
    for y in range(text_surface.get_height()):
        ratio = y / text_surface.get_height() if text_surface.get_height() > 0 else 0
        r = int(color_top[0] * (1 - ratio) + color_bottom[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bottom[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bottom[2] * ratio)

        for x in range(text_surface.get_width()):
            if text_surface.get_at((x, y))[3] > 0:
                gradient_surface.set_at((x, y), (r, g, b, 255))

    final_surface.blit(gradient_surface, (outline_width, outline_width))
    return final_surface

class WeatherDataWorker(threading.Thread):

    def __init__(self, zip_code, result_queue, stop_event):
        super().__init__(daemon=True)
        self.zip_code = zip_code
        self.result_queue = result_queue
        self.stop_event = stop_event
        self.last_refresh_time = 0
        self.first_run = True  # Track if this is the first background refresh

    def run(self):
        while not self.stop_event.is_set():
            current_time = time.time()
            if current_time - self.last_refresh_time >= WEATHER_REFRESH_INTERVAL:
                try:
                    print("Background thread: Starting weather data refresh...")
                    lat, lon, state, location_name = get_coordinates_from_zip(self.zip_code)

                    if lat and lon:
                        _, _, _, forecast_url, _ = get_forecast_grid_point(lat, lon)
                        current_conditions_data = fetch_current_conditions(lat, lon)
                        alert_list, _, alert_type_val, is_tropical = get_weather_alerts(zip_code=self.zip_code, state=state)
                        
                        # Handle first run and log initial alerts only
                        if self.first_run:
                            log_initial_alerts(alert_list)
                            self.first_run = False
                        else:
                            check_for_new_alerts(alert_list)
                        
                        forecast_text_val, forecast_periods_data = fetch_weather_forecast(forecast_url)
                        radar_data_tuple = fetch_radar_image(is_tropical=is_tropical, tropical_thread=None, tropical_results=None)

                        # List of vars used here
                        weather_data = {
                            'lat': lat,
                            'lon': lon,
                            'state': state,
                            'location_name': location_name,
                            'forecast_url': forecast_url,
                            'current_conditions': current_conditions_data,
                            'alert_list': alert_list,
                            'alert_type': alert_type_val,
                            'alert_type': alert_type_val,
                            'is_tropical': is_tropical,
                            'forecast_text': forecast_text_val,
                            'forecast_periods': forecast_periods_data,
                            'radar_data': radar_data_tuple,
                            'refresh_time': current_time
                        }
                        try:
                            self.result_queue.put_nowait(weather_data)
                            print("Weather data refresh completed successfully")
                        except queue.Full:
                            print("Queue is full, skipping this update.")
                    else:
                        print("Uhhh... Do you have an internet connection?")
                except Exception as e:
                    print(f"Error during data refresh {e}")
                    import traceback
                    traceback.print_exc()
                self.last_refresh_time = current_time
            time.sleep(1)

# This controls the size of what resolution PyGame renders at, shrinking this makes PyGame render everything BIG.
BASE_WIDTH = 1920
BASE_HEIGHT = 1080

def calculate_scale_factors(screen_width, screen_height):
    scale_x = screen_width / BASE_WIDTH
    scale_y = screen_height / BASE_HEIGHT
    return scale_x, scale_y

def scale_pos(pos, scale_x, scale_y):
    return (int(pos[0] * scale_x), int(pos[1] * scale_y))

def scale_size(size, scale_x, scale_y):
    return (int(size[0] * scale_x), int(size[1] * scale_y))

def scale_value(value, scale_factor):
    return int(value * scale_factor)

def scale_font_size(size, scale_factor):

    scaled_size = int(size * scale_factor)
    return max(8, scaled_size)

def check_for_new_alerts(alert_list):
    global previous_alerts, played_ticker_alerts
    
    if not alert_list:
        print("Alert check: No alerts present")
        return
    
    # Determine current alerts
    current_alerts = set()
    for alert in alert_list:
        alert_type = alert.get('event_upper', '')
        current_alerts.add(alert_type)
    
    print(f"CURRENT ALERT(S): {list(current_alerts)}")
    print(f"PREVIOUS ALERT(S): {list(previous_alerts)}")
    
    # Check for new alerts (alerts that weren't in the previous set)
    new_alerts = current_alerts - previous_alerts
    
    if new_alerts:
        print(f"NEW ALERT(S): {list(new_alerts)}")
        # Remove only the new alert types from played ticker alerts so they can play audio!
        for new_alert in new_alerts:
            played_ticker_alerts.discard(new_alert)
        print(f"Cleared ticker audio history for new alerts: {', '.join(new_alerts)}")
    else:
        print("Alert check: No new alerts detected")
    
    # Update the previous alerts set
    previous_alerts = current_alerts.copy()

class InitializationWorker(threading.Thread):
# A worker thread so the main loading screen doesn't freeze.
    def __init__(self, zip_code, result_queue, progress_queue, stop_event):
        super().__init__(daemon=True)
        self.zip_code = zip_code
        self.result_queue = result_queue
        self.progress_queue = progress_queue
        self.stop_event = stop_event
    
    def run(self):
        try:
            # Coordinates getter
            lat, lon, state, location_name = get_coordinates_from_zip(self.zip_code)
            forecast_url = None
            current_conditions_data = None
            forecast_periods_data = None
            
            if lat and lon:
                # Then, figure out where that is..
                _, _, _, forecast_url, _ = get_forecast_grid_point(lat, lon)
                current_conditions_data = fetch_current_conditions(lat, lon)
            
            # Alerts
            alert_list, _, alert_type_val, is_tropical = get_weather_alerts(zip_code=self.zip_code, state=state)
            log_initial_alerts(alert_list)
            
            # Forecast from NWS
            forecast_text_val = None
            if forecast_url:
                forecast_text_val, forecast_periods_data = fetch_weather_forecast(forecast_url)
            
            # Redmode/Is_tropical.
            is_redmode = False
            tropical_thread = None
            tropical_download_results = [None, None]
            
            if alert_type_val:
                alert_upper = alert_type_val.upper()
                if "HURRICANE WATCH" in alert_upper or "HURRICANE WARNING" in alert_upper:
                    is_redmode = True
            
            # Start tropical download in background if needed..
            if is_tropical:
                def download_tropical_gif():
                    try:
                        lat_val, lon_val = lat, lon
                        tropical_url = build_tropical_url(lat_val, lon_val, zip_code=self.zip_code)
                        
                        response = requests.get(tropical_url, stream=True, timeout=60)
                        response.raise_for_status()
                        html_buffer = b''
                        found_link = False
                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk:
                                html_buffer += chunk
                                if b'Download as Animated Gif' in html_buffer:
                                    found_link = True
                                    break
                        response.close()
                        if not found_link:
                            print("Could not find the tropical GIF download link on the page.")
                            return
                        html_content = html_buffer.decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(html_content, 'html.parser')
                        download_link_element = soup.find('a', string='Download as Animated Gif')
                        if download_link_element:
                            relative_gif_path = download_link_element.get('href')
                            if relative_gif_path:
                                base_site_url = "https://mesonet.agron.iastate.edu/GIS/apps/rview/"
                                full_gif_url = urljoin(base_site_url, relative_gif_path)
                                gif_response = requests.get(full_gif_url, stream=True, timeout=240)
                                gif_response.raise_for_status()
                                gif_bytes_in_memory = gif_response.content
                                gif_file_stream = io.BytesIO(gif_bytes_in_memory)
                                pil_gif = Image.open(gif_file_stream)
                                pygame_frames = []
                                frame_durations_ms = []
                                for i, frame in enumerate(ImageSequence.Iterator(pil_gif)):
                                    frame_rgba = frame.convert('RGBA')
                                    width, height = frame_rgba.size
                                    crop_top = int(height * 0.1)
                                    cropped_frame = frame_rgba.crop((0, crop_top, width, height))
                                    cropped_width, cropped_height = cropped_frame.size
                                    aspect_ratio = cropped_width / cropped_height
                                    screen_aspect = SCREEN_WIDTH / SCREEN_HEIGHT
                                    if aspect_ratio > screen_aspect:
                                        new_height = SCREEN_HEIGHT
                                        new_width = int(SCREEN_HEIGHT * aspect_ratio)
                                    else:
                                        new_width = SCREEN_WIDTH
                                        new_height = int(SCREEN_WIDTH / aspect_ratio)
                                    
                                    if QUALITY_FACTOR < 1.0:
                                        intermediate_width = int(new_width * QUALITY_FACTOR)
                                        intermediate_height = int(new_height * QUALITY_FACTOR)
                                        downscaled_frame = cropped_frame.resize((intermediate_width, intermediate_height), Image.Resampling.LANCZOS)
                                        scaled_frame = downscaled_frame.resize((new_width, new_height), Image.Resampling.LANCZOS)
                                    else:
                                        scaled_frame = cropped_frame.resize((new_width, new_height), Image.Resampling.LANCZOS)
                                    pygame_surface = pygame.image.frombytes(scaled_frame.tobytes(), scaled_frame.size, scaled_frame.mode).convert_alpha()
                                    offset_y = 40
                                    final_surface = pygame.Surface((pygame_surface.get_width(), pygame_surface.get_height()), pygame.SRCALPHA)
                                    final_surface.blit(pygame_surface, (0, offset_y))
                                    pygame_frames.append(final_surface)
                                    duration = frame.info.get('duration', 100)
                                    if not isinstance(duration, (int, float)) or duration <= 0:
                                        duration = 100
                                    frame_durations_ms.append(int(duration))
                                if pygame_frames and frame_durations_ms:
                                    frame_durations_ms[-1] += 1500
                                tropical_download_results[0] = pygame_frames
                                tropical_download_results[1] = frame_durations_ms
                    except Exception as e:
                        print(f"Error downloading tropical GIF: {e}")
                
                tropical_thread = threading.Thread(target=download_tropical_gif)
                tropical_thread.start()
            
            # Update loading screen (loadingradardata)
            try:
                self.progress_queue.put_nowait({'stage': 'loading_radar'})
            except:
                pass
            
            # Radar image.. (redmode, is_tropical, etc..)
            radar_data_tuple = fetch_radar_image(is_tropical=is_tropical, tropical_thread=tropical_thread, tropical_results=tropical_download_results)
            
            # Package all results
            init_data = {
                'lat': lat,
                'lon': lon,
                'state': state,
                'location_name': location_name,
                'forecast_url': forecast_url,
                'current_conditions': current_conditions_data,
                'forecast_text': forecast_text_val,
                'forecast_periods': forecast_periods_data,
                'alert_list': alert_list,
                'alert_type': alert_type_val,
                'is_tropical': is_tropical,
                'is_redmode': is_redmode,
                'radar_data': radar_data_tuple,
                'status': 'complete'
            }
            
            self.result_queue.put(init_data)
        except Exception as e:
            traceback.print_exc()
            error_data = {
                'status': 'error',
                'error': str(e),
                'lat': None, 'lon': None, 'state': None, 'location_name': None,
                'forecast_url': None, 'current_conditions': None, 'forecast_text': None,
                'forecast_periods': None, 'alert_list': [], 'alert_type': None,
                'is_tropical': False, 'is_redmode': False, 'radar_data': None
            }
            self.result_queue.put(error_data)

def log_initial_alerts(alert_list):
    global previous_alerts
    if alert_list:
        alert_types = {alert.get('event_upper', '') for alert in alert_list}
        previous_alerts = alert_types.copy()
        print(f"Initial alerts logged: {', '.join(alert_types) if alert_types else 'None'}")
    else:
        previous_alerts = set()
        print("No initial alerts found")

def play_initial_alert_audio(alert_list):
    if not alert_list:
        return
    
    # Get all current alert types
    current_alerts = {alert.get('event_upper', '') for alert in alert_list}
    
    # Check what type of audio to play based on alert priority
    warnings = {alert for alert in current_alerts if 'WARNING' in alert}
    watches = {alert for alert in current_alerts if any(keyword in alert for keyword in ['WATCH', 'ADVISORY', 'STATEMENT'])}
    
    print(f"Initial warnings: {warnings}")
    print(f"Initial watches/advisories: {watches}")
    
    # Warning > Watch
    if warnings:
        try:
            pygame.mixer.Sound('audio/3tone-warning.ogg').play()
        except Exception as e:
            print(f"Error playing initial warning audio: {e}")
    elif watches:
        try:
            pygame.mixer.Sound('audio/1tone-watch.ogg').play()
        except Exception as e:
            print(f"Error playing initial watch audio: {e}")
    else:
        print("Initial alerts detected but no audio played (alerts don't match warning/watch criteria)")

def play_ticker_audio(alert_type, is_new_alert=False, radar_loaded=True):
    global played_ticker_alerts
    if not is_new_alert and alert_type in played_ticker_alerts:
        return
    
    # Play audio for new alerts
    if 'WARNING' in alert_type:
        try:
            pygame.mixer.Sound('audio/3tone-warning.ogg').play()
            played_ticker_alerts.add(alert_type)
        except Exception as e:
            print(f"Error playing ticker warning audio: {e}")
    elif 'WATCH' in alert_type:
        try:
            pygame.mixer.Sound('audio/1tone-watch.ogg').play()
            played_ticker_alerts.add(alert_type)
        except Exception as e:
            print(f"Error playing ticker watch audio: {e}")

PANEL_CYCLE_INTERVAL = 20000
WEATHER_REFRESH_INTERVAL = 500
DEFAULT_TITLE_TEXT = "Local Radar"
WARNING_TEXT = " "
TICKER_TEXT = "Loading forecast data..."
BOTTOM_BAR_HEIGHT = 146

# Global variables for user inputs
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
ZIP_CODE = ""
SHOW_FPS = False
VSYNC_ENABLED = True  # VSync enabled by default (syncs to refresh rate..)
QUALITY_FACTOR = 1.0  # Full quality is the default (100% rendering quality)

# Global variables for alert audio system
previous_alerts = set()
played_ticker_alerts = set()
pending_alert_for_audio = None
fatal_error_logged = False  # Track if it's already logged a fatal error
# TITLE_CONFIG is for the current conditions panel.
TITLE_CONFIG = {"font_size": 62}
TKR_WARNING_TITLE_CONFIG = {"font_path": "fonts/Interstate_Bold.otf", "font_size": 32, "color": (255, 255, 255), "position": (10, SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT + 15)}
# TICKER_CONFIG: `position_offset` can be used to nudge the ticker further down (+) or up (-) relative to the base offset (50)
TICKER_CONFIG = {"font_path": "fonts/Interstate_Light.otf", "font_size": 72, "color": (255, 255, 255), "position_y": SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT + 100, "position_offset": 10, "scroll_threshold": 800, "scroll_speed": 300}
CURRENT_CONDITIONS_CONFIG = {
    "font_path": "fonts/Interstate_Bold.otf",
    "title_font_size": 40,
    "condition_desc_font_size": 40,
    "condition_desc_x_offset": -2,
    "data_font_size": 24,
    "list_font_size": 24,
    "color": (255, 255, 255),
    "title_color": (220, 220, 50),
    "position": (10, 120),
    "line_height": 40,
    "background_color": (0, 0, 0, 180),
    "width": 550,
    "padding": 20,
    "max_height": 770,
}

# Giant variable/path blob here! Perhaps I should move this before v0.4.0?
PANEL_TEXTURE_PATH = "textures/graphics/paneaero.png"
WATCH_BAR_TEXTURE_PATH = "textures/graphics/watch_LDL.png"
ALERT_BAR_TEXTURE_PATH = "textures/graphics/warning_LDL.png"
LOGO_CONFIG = {"path": "textures/graphics/mini8s_logo.png", "width": 175, "margin_right": 10, "margin_top": 10}
CURRENT_CONDITIONS_ICON_SIZE_RATIO = 0.16
FORECAST_ICON_SIZE_MULTIPLIER = 2.0
# VVV The speed of this is determined by the active framerate, it will quite literally play faster the more FPS there is.
PANEL_FLIP_ANIMATION_STEPS = 13
FLIP_SUB_STEP_DURATION_MS = 13
NUM_SUB_FRAMES_PER_SINGLE_FLIP_ANIMATION = (2 * PANEL_FLIP_ANIMATION_STEPS + 1)

pre_rendered_conditions_surface = None
pre_rendered_forecast_surface = None

base_common_frames_global = []
pre_rendered_frames_conditions = []
pre_rendered_frames_forecast = []

panel_shrink_cond_surfaces = []
panel_expand_cond_surfaces = []
panel_shrink_fcst_surfaces = []
panel_expand_fcst_surfaces = []

def get_coordinates_from_zip(zip_code):
    try:
        headers = {'User-Agent': 'Mini8sWeatherApp/1.0'}
        url = f"https://nominatim.openstreetmap.org/search?q={zip_code},USA&format=json&limit=1"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if not data: 
            get_coordinates_from_zip.last_error = f"No data found for ZIP {zip_code}"
            return None, None, None, f"ZIP {zip_code}"
        latitude = float(data[0]['lat'])
        longitude = float(data[0]['lon'])
        display_parts = data[0].get('display_name', '').split(',')
        place_name = display_parts[0].strip() if display_parts else ''
        address = data[0].get('address', {})

        county = address.get('county', '')
        if not county:

            for part in display_parts:
                part_clean = part.strip()
                if 'county' in part_clean.lower():
                    county = part_clean
                    break

        if county and county.lower().endswith(' county'):
            county = county[:-7]

        # Extract state name from display_name
        state_name = None
        state_acronym = None
        
        # Load state acronym mapping first
        state_mapping = {}
        try:
            with open('var/state-acros.json', 'r') as f:
                state_mapping = json.load(f)
        except Exception:
            pass
        for part in display_parts:
            part_clean = part.strip()
            # Skip empty parts and obvious non-state parts
            if not part_clean or part_clean.lower() in ['united states', 'usa']:
                continue
            # Check if this part matches a state name in our mapping
            if part_clean in state_mapping:
                state_name = part_clean
                state_acronym = state_mapping[state_name]
                break
        
        # If no state found in mapping, fall back to previous logic for backwards compatibility
        if not state_name and len(display_parts) >= 3:
            # Check if display_parts[2] contains the county name, if so look at [3] for state
            potential_state = display_parts[2].strip()
            if county and county.lower() in potential_state.lower():
                # County found in position 2, state should be at position 3
                if len(display_parts) >= 4:
                    state_name = display_parts[3].strip()
            else:
                state_name = potential_state
            state_acronym = state_mapping.get(state_name, state_name)

        if county and state_acronym:
            location_name = f"{county}, {state_acronym}"
        else:
            location_name = f"{county} County" if county else f"ZIP {zip_code}"
            
        return latitude, longitude, county, location_name
    except Exception as e:
        error_message = f"Error getting coordinates from ZIP: {e}"
        print(error_message)
        get_coordinates_from_zip.last_error = error_message
        return None, None, None, None

def get_forecast_grid_point(latitude, longitude):
    try:
        url = f"https://api.weather.gov/points/{latitude},{longitude}"
        response = requests.get(url, headers={'User-Agent': 'Mini8sWeatherApp/1.0'})
        response.raise_for_status()
        data = response.json()
        properties = data.get('properties', {})
        return properties.get('gridId'), properties.get('gridX'), properties.get('gridY'), properties.get('forecast'), properties.get('forecastHourly')
    except Exception as e:
        print(f"Error getting grid point: {e}")
        return None, None, None, None, None

def fetch_current_conditions(latitude, longitude):
    try:
        points_url = f"https://api.weather.gov/points/{latitude},{longitude}"
        points_response = requests.get(points_url, headers={'User-Agent': 'Mini8sWeatherApp/1.0'})
        points_response.raise_for_status()
        properties = points_response.json().get('properties', {})
        hourly_url = properties.get('forecastHourly')
        observation_stations_url = properties.get('observationStations')
        if not hourly_url:
            print("Could not get hourly forecast URL.")
            return None
        hourly_res = requests.get(hourly_url, headers={'User-Agent': 'Mini8sWeatherApp/1.0'})
        hourly_res.raise_for_status()
        current_period = hourly_res.json().get('properties', {}).get('periods', [{}])[0]
        # This dictionary is first created with the 'forecast' data as a fallback.
        conditions_data = {
            "temperature": current_period.get('temperature', 'N/A'),
            "temperatureUnit": current_period.get('temperatureUnit', 'F'),
            "conditions": current_period.get('shortForecast', 'N/A'),
            "isDaytime": current_period.get('isDaytime', True),
            "wind": f"{current_period.get('windSpeed', 'N/A')} {current_period.get('windDirection', '')}",
            "time": current_period.get('startTime', ''),
            "humidity": "N/A",
            "dewpoint": "N/A",
            "pressure": "N/A",
            "visibility": "N/A",
            "gusts": "N/A"
        }
        if not observation_stations_url:
            print("Could not get observation stations URL, returning partial data.")
            conditions_data['humidity'] = f"{current_period.get('relativeHumidity', {}).get('value', 'N/A')}%"
            conditions_text = conditions_data['conditions']
            if len(conditions_text) >= 25:
                conditions_data['conditions_desc_font_size'] = 28
            else:
                conditions_data['conditions_desc_font_size'] = 40
            return conditions_data
        stations_res = requests.get(observation_stations_url, headers={'User-Agent': 'Mini8sWeatherApp/1.0'})
        stations_res.raise_for_status()
        features = stations_res.json().get('features', [])
        if not features:
            print("No observation stations found, returning partial data.")
            conditions_data['humidity'] = f"{current_period.get('relativeHumidity', {}).get('value', 'N/A')}%"
            conditions_text = conditions_data['conditions']
            if len(conditions_text) >= 25:
                conditions_data['conditions_desc_font_size'] = 28
            else:
                conditions_data['conditions_desc_font_size'] = 40
            return conditions_data
        latest_obs_url = features[0].get('id') + "/observations/latest"
        station_id = features[0].get('id').split('/')[-1] if features[0].get('id') else "Unknown"
        obs_res = requests.get(latest_obs_url, headers={'User-Agent': 'Mini8sWeatherApp/1.0'})
        if obs_res.status_code == 200:
            obs_props = obs_res.json().get('properties', {})

        timestamp_str = obs_props.get('timestamp')
        if timestamp_str:
            from datetime import datetime, timezone
            obs_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            current_time = datetime.now(timezone.utc)
            time_diff = current_time - obs_time
            hours_old = time_diff.total_seconds() / 3600
            if hours_old > 2:
                print(f"Warning: Observation data is {hours_old:.1f} hours old, contact airport {station_id} and let them know there is an issue with their ASOS/AWOS observation data!")

            temp_data = obs_props.get('temperature', {})

            if obs_props.get('textDescription'):
                conditions_data['conditions'] = obs_props['textDescription']

            if temp_data.get('value') is not None:
                temp_value = temp_data['value']
                unit_code = temp_data.get('unitCode', '')
                if 'degC' in unit_code: # For those Europeans out there!
                    temp_fahrenheit = round(temp_value * 9/5 + 32)
                    conditions_data['temperature'] = temp_fahrenheit
                else:
                    conditions_data['temperature'] = temp_value

            def get_and_convert(data, key, conversion_func, unit_str):
                val = data.get(key, {}).get('value')
                return f"{conversion_func(val)}{unit_str}" if val is not None else "N/A"
            conditions_data['humidity'] = get_and_convert(obs_props, 'relativeHumidity', lambda x: round(x), "%")
            conditions_data['dewpoint'] = get_and_convert(obs_props, 'dewpoint', lambda c: round(c * 9/5 + 32), "°F")
            conditions_data['pressure'] = get_and_convert(obs_props, 'barometricPressure', lambda pa: f"{pa / 3386.389:.2f}", " inHg")
            conditions_data['visibility'] = get_and_convert(obs_props, 'visibility', lambda m: round(m / 1609.34, 1), " mi")
            gust_kmh = obs_props.get('windGust', {}).get('value')
            if gust_kmh is not None:
                conditions_data['gusts'] = f"{round(gust_kmh / 1.60934)} mph"
            else:
                # Check if we can infer gusts from wind speed or get from forecast period
                wind_speed_str = current_period.get('windSpeed', '')
                if 'gusting' in wind_speed_str.lower() or 'gust' in wind_speed_str.lower():
                    # Extract gust speed if mentioned in wind description
                    gust_match = re.search(r'gust(?:ing|s)?\s+(?:to\s+)?(\d+)', wind_speed_str.lower())
                    if gust_match:
                        gust_speed = int(gust_match.group(1))
                        conditions_data['gusts'] = f"{gust_speed} mph"
                    else:
                        conditions_data['gusts'] = "None"
                else:
                    conditions_data['gusts'] = "None"
        else:
            print(f"Unable to get data ({obs_res.status_code}), using partial data.")
            conditions_data['humidity'] = f"{current_period.get('relativeHumidity', {}).get('value', 'N/A')}%"
        conditions_text = conditions_data['conditions'].lower()
        
        # Define word groups for detection
        storm_words = {'thunderstorm', 'thunderstorms', 't-storm', 't-storms', 'thunder'}
        intensity_words = {'heavy', 'strong'}
        additional_conditions = {'fog', 'mist', 'squall', 'squalls'}
        rain_words = {'rain', 'showers'}
        words_in_condition = set(conditions_text.replace('/', ' ').replace('-', ' ').replace('and', '').split())
        if "chance" in words_in_condition and any(word in words_in_condition for word in storm_words):
            conditions_data['conditions'] = "Showers Nearby"
        
        # Check for storm combinations
        elif any(word in words_in_condition for word in storm_words):
            # Storm + Fog/Mist combination
            if any(word in words_in_condition for word in {'fog', 'mist'}):
                if any(word in words_in_condition for word in intensity_words):
                    conditions_data['conditions'] = "Heavy T-storms"
                else:
                    conditions_data['conditions'] = "T-storms"

            elif any(word in words_in_condition for word in {'squall', 'squalls'}):
                conditions_data['conditions'] = "Strong T-storm"
            
            # Heavy/Strong Storm
            elif any(word in words_in_condition for word in intensity_words):
                conditions_data['conditions'] = "Heavy T-storms"
            
            # Storm + Heavy Rain
            elif any(word in words_in_condition for word in rain_words) and \
                 any(word in words_in_condition for word in intensity_words):
                conditions_data['conditions'] = "Heavy T-storms"
                
            # Default storm case if no special combinations
            else:
                conditions_data['conditions'] = "T-storms"
        
        # Auto-shrink font size based on character count.. does this even work?
        conditions_text = conditions_data['conditions']
        if len(conditions_text) > 30:
            conditions_data['conditions_desc_font_size'] = 28
        elif len(conditions_text) >= 25:
            conditions_data['conditions_desc_font_size'] = 35
        else:
            conditions_data['conditions_desc_font_size'] = 40

        return conditions_data
    except Exception as e:
        print(f"An error occurred in fetch_current_conditions: {e}")
        return None

def fetch_weather_forecast(forecast_url=None):
    if not forecast_url:
        lat, lon, _, _ = get_coordinates_from_zip(ZIP_CODE)
        if lat and lon: _, _, _, forecast_url, _ = get_forecast_grid_point(lat, lon)
    if not forecast_url: return "Weather data unavailable", None
    try:
        response = requests.get(forecast_url, headers={'User-Agent': 'Mini8sWeatherApp/1.0'})
        response.raise_for_status()
        data = response.json()
        periods = data.get('properties', {}).get('periods', [])
        forecast_text = ""
        if periods:
            for period in periods[:2]:
                forecast_text += f"{period.get('name', '')}: {period.get('temperature', '')}°{period.get('temperatureUnit', '')} - {period.get('shortForecast', '')}. "
        return forecast_text.strip(), periods
    except Exception as e:
        print(f"Error fetching weather forecast: {e}")
        return "Weather data temporarily unavailable", None
def build_radar_url(lat, lon, zip_code=None):
    current_time = datetime.now()
    base_url = "https://mesonet.agron.iastate.edu/GIS/apps/rview/warnings.phtml"

    global current_alert_level, alert_type_val
    is_tropical = False
    try:
        alert_type = alert_type_val.upper() if alert_type_val else ""
        if ("TROPICAL" in alert_type) or ("HURRICANE" in alert_type):
            is_tropical = True
        elif alert_text_val and ("TROPICAL" in alert_text_val.upper() or "HURRICANE" in alert_text_val.upper()):
            is_tropical = True
    except Exception:
        pass

    # New(er) params chunk for adding PR AK and HI support, DEBUG MODE HERE!
    radar_layer, site_param = determine_radar_layer_and_site(zip_code)

    params = {
        'tzoff': '0',
        'lat0': f"{lat:.10f}",
        'lon0': f"{lon:.10f}",
        'layers[]': [radar_layer, 'warnings', 'uscounties', 'watches', 'blank'],
        'tz': 'EDT',
        'year': str(current_time.year),
        'month': str(current_time.month),
        'day': str(current_time.day),
        'hour': str(current_time.hour),
        'minute': str(current_time.minute),
        'warngeo': 'both',
        'zoom': '250',
        'imgsize': '1280x1024',
        'loop': '1',
        'frames': '49',
        'interval': '5',
        'filter': '0',
        'cu': '0',
        'sortcol': 'fcster',
        'sortdir': 'DESC',
        'lsrlook': '%2B',
        'lsrwindow': '0'
    }

    # Add site parameter for special regions
    if site_param:
        params['site'] = site_param

    if is_tropical:
        if 'layers[]' in params:
            if 'goes_ir' not in params['layers[]']:
                params['layers[]'].insert(0, 'goes_ir')
        else:
            params['layers[]'] = ['goes_ir']

    url_parts = [base_url + "?"]
    for key, value in params.items():
        if key == 'layers[]':
            for layer in value:
                url_parts.append(f"layers%5B%5D={layer}&")
        else:
            url_parts.append(f"{key}={value}&")
    return ''.join(url_parts).rstrip('&')

def determine_radar_layer_and_site(zip_code):
    radar_layer = 'nexrad'
    site_param = None
    if zip_code:
        zip_prefix = str(zip_code)[:3]
        if zip_prefix in ['006', '007', '009']:
            return 'prn0q', 'JSJ'
        elif zip_prefix in ['995', '996', '997', '998', '999']:
            return 'akn0q', 'AFC'
        elif zip_prefix in ['967', '968']:
            return 'hin0q', 'HFO'
    return radar_layer, site_param


def build_tropical_url(lat, lon, zip_code=None):
    current_time = datetime.now()
    base_url = "https://mesonet.agron.iastate.edu/GIS/apps/rview/warnings.phtml"

    # Determine radar layer/site for the region
    radar_layer, site_param = determine_radar_layer_and_site(zip_code)
    params = {
        'tzoff': '0',
        'lat0': f"{lat:.10f}",
        'lon0': f"{lon:.10f}",
        'layers[]': ['goes_ir', radar_layer, 'warnings', 'uscounties', 'watches', 'blank'],
        'tz': 'EDT',
        'year': str(current_time.year),
        'month': str(current_time.month),
        'day': str(current_time.day),
        'hour': str(current_time.hour),
        'minute': str(current_time.minute),
        'warngeo': 'both',
        'zoom': '500',
        'imgsize': '1280x1024',
        'loop': '1',
        'frames': '49',
        'interval': '5',
        'filter': '0',
        'cu': '0',
        'sortcol': 'fcster',
        'sortdir': 'DESC',
        'lsrlook': '%2B',
        'lsrwindow': '0'
    }

    # Add site parameter for special regions
    if site_param:
        params['site'] = site_param

    url_parts = [base_url + "?"]
    for key, value in params.items():
        if key == 'layers[]':
            for layer in value:
                url_parts.append(f"layers%5B%5D={layer}&")
        else:
            url_parts.append(f"{key}={value}&")
    return ''.join(url_parts).rstrip('&')

def fetch_radar_image(is_tropical=False, tropical_thread=None, tropical_results=None):
    try:
        lat, lon, _, _ = get_coordinates_from_zip(ZIP_CODE)
        if not lat or not lon:
            print("Could not get coordinates")
            # Capture the error from get_coordinates_from_zip if available
            if hasattr(get_coordinates_from_zip, 'last_error'):
                fetch_radar_image.last_error = get_coordinates_from_zip.last_error
            else:
                fetch_radar_image.last_error = "Could not get coordinates from ZIP code"
            return None

        radar_url = build_radar_url(lat, lon, zip_code=ZIP_CODE)
        def get_gif_frames_and_durations(radar_url):
            try:
                response = requests.get(radar_url, stream=True, timeout=60)
                response.raise_for_status()
                html_buffer = b''
                found_link = False
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        html_buffer += chunk
                        if b'Download as Animated Gif' in html_buffer:
                            found_link = True
                            break
                response.close()
                if not found_link:
                    fetch_radar_image.last_error = "Could not find radar image on the server"
                    return None, None
            except requests.exceptions.Timeout:
                fetch_radar_image.last_error = "Connection timed out"
                raise
            except requests.exceptions.ConnectionError as e:
                if "Errno -3" in str(e).lower():
                    fetch_radar_image.last_error = "Error: errno -3"
                else:
                    fetch_radar_image.last_error = f"Connection error: {e}"
                raise
            html_content = html_buffer.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html_content, 'html.parser')
            download_link_element = soup.find('a', string='Download as Animated Gif')
            if download_link_element:
                relative_gif_path = download_link_element.get('href')
                if relative_gif_path:
                    base_site_url = "https://mesonet.agron.iastate.edu/GIS/apps/rview/"
                    full_gif_url = urljoin(base_site_url, relative_gif_path)
                    gif_response = requests.get(full_gif_url, stream=True, timeout=240)
                    gif_response.raise_for_status()
                    gif_bytes_in_memory = gif_response.content
                    gif_file_stream = io.BytesIO(gif_bytes_in_memory)
                    pil_gif = Image.open(gif_file_stream)
                    pygame_frames = []
                    frame_durations_ms = []
                    for i, frame in enumerate(ImageSequence.Iterator(pil_gif)):
                        frame_rgba = frame.convert('RGBA')
                        width, height = frame_rgba.size
                        # Only crop for tropical GIFs, not for standard radar GIFs
                        if is_tropical:
                            crop_top = int(height * 0.1)
                            cropped_frame = frame_rgba.crop((0, crop_top, width, height))
                        else:
                            cropped_frame = frame_rgba
                        cropped_width, cropped_height = cropped_frame.size
                        aspect_ratio = cropped_width / cropped_height
                        screen_aspect = SCREEN_WIDTH / SCREEN_HEIGHT
                        if aspect_ratio > screen_aspect:
                            new_height = SCREEN_HEIGHT
                            new_width = int(SCREEN_HEIGHT * aspect_ratio)
                        else:
                            new_width = SCREEN_WIDTH
                            new_height = int(SCREEN_WIDTH / aspect_ratio)
                        
                        # Apply user-selected quality reduction
                        if QUALITY_FACTOR < 1.0:
                            # First downscale to reduce pixel count for performance
                            intermediate_width = int(new_width * QUALITY_FACTOR)
                            intermediate_height = int(new_height * QUALITY_FACTOR)
                            downscaled_frame = cropped_frame.resize((intermediate_width, intermediate_height), Image.Resampling.LANCZOS)
                            # Then scale back up to display size
                            scaled_frame = downscaled_frame.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        else:
                            # Full quality - direct resize
                            scaled_frame = cropped_frame.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        pygame_surface = pygame.image.frombytes(scaled_frame.tobytes(), scaled_frame.size, scaled_frame.mode).convert_alpha()
                        if is_tropical:
                            offset_y = 40
                            final_surface = pygame.Surface((pygame_surface.get_width(), pygame_surface.get_height()), pygame.SRCALPHA)
                            final_surface.blit(pygame_surface, (0, offset_y))
                        else:
                            offset_y = -75
                            final_surface = pygame.Surface((pygame_surface.get_width(), pygame_surface.get_height()), pygame.SRCALPHA)
                            final_surface.blit(pygame_surface, (0, offset_y))
                        pygame_frames.append(final_surface)
                        duration = frame.info.get('duration', 100)
                        if not isinstance(duration, (int, float)) or duration <= 0:
                            duration = 100
                        frame_durations_ms.append(int(duration))
                    # 1.5/1500ms sec on last frame.
                    if pygame_frames and frame_durations_ms:
                        frame_durations_ms[-1] += 1500
                    return pygame_frames, frame_durations_ms
            return None, None

        # Always get the standard radar GIF
        try:
            frames1, durations1 = get_gif_frames_and_durations(radar_url)
            if frames1 is None or durations1 is None:
                fetch_radar_image.last_error = "Failed to load radar GIF"
                return None
        except requests.exceptions.RequestException as req_err:
            fetch_radar_image.last_error = f"Error: {req_err}"
            return None
        except Exception as load_err:
            fetch_radar_image.last_error = f"Error: {load_err}"
            return None

        if is_tropical:
            # Use the already-started tropical download if available
            if tropical_thread and tropical_results:
                # Wait for the tropical download to complete
                tropical_thread.join()
                frames2, durations2 = tropical_results[0], tropical_results[1]
                if frames2 and durations2:
                    return [(frames1, durations1, 0), (frames2, durations2, 25000)]
            else:
                # Fallback to original sequential download if no thread was started

                tropical_url = build_tropical_url(lat, lon, zip_code=ZIP_CODE)
                frames2, durations2 = get_gif_frames_and_durations(tropical_url)
                if frames2 and durations2:
                    return [(frames1, durations1, 0), (frames2, durations2, 25000)]

        return [(frames1, durations1, 0)]
    except Exception as e:
        print(f"Error in fetch_radar_image: {e}")
        traceback.print_exc()
        # Store the error message for the BSOD display
        fetch_radar_image.last_error = str(e)
        return None

# ..I have no idea what a User-Agent is but I suppose I need it..
def get_weather_alerts(zip_code=None, state=None):
    try:
        if zip_code:
            lat, lon, state_from_zip, _ = get_coordinates_from_zip(zip_code)
            if not lat or not lon: return [], None, None, False
            alerts_url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
            if not state: state = state_from_zip
        elif state:
            alerts_url = f"https://api.weather.gov/alerts/active?area={state}"
        else:
            return [], None, None, False

        response = requests.get(alerts_url, headers={'User-Agent': 'Mini8s/v0.3.99family'})
        response.raise_for_status()
        data = response.json()
        features = data.get('features', [])
        if not features: return [], None, None, False
        all_alerts = []
        is_tropical = False

        # Process all alerts first to group them by type
        warnings = []
        watches = []
        advisories = []

        for feature in features:
            alert = feature.get('properties', {})
            event = alert.get('event', '')
            headline = alert.get('headline', '')
            description = alert.get('description', '')
            instruction = alert.get('instruction', '')

            # Check for tropical/hurricane
            event_upper = event.upper() if event else ""
            if ("TROPICAL" in event_upper or "HURRICANE" in event_upper):
                is_tropical = True

            event_upper_normalized = event.upper()

            # Create alert data
            alert_data = {
                'event': event,
                'event_upper': event.upper(),
                'headline': headline,
                'description': description,
                'ticker_text': (' ... '.join([headline, description] + ([instruction] if instruction and instruction.strip().upper() not in ['N/A', 'NA', ''] else [])).replace('\n', ' ').replace('\r', ' ').replace('  ', ' ').strip()),
                'alert_level': None,
                'priority': 0
            }

            # Categorize alert based on type
            if "WARNING" in event_upper_normalized:
                alert_data['alert_level'] = "ALERT"
                warnings.append(alert_data)
            elif "WATCH" in event_upper_normalized:
                alert_data['alert_level'] = "WATCH"
                watches.append(alert_data)
            else:  # STATEMENT/ADVISORY
                alert_data['alert_level'] = "STATEMENT"
                advisories.append(alert_data)

        # Combine all alerts in proper order: Warnings -> Watches -> Advisories
        all_alerts = warnings + watches + advisories

        # Get the highest priority alert type for redmode purposes.
        primary_alert_type = all_alerts[0]['event_upper'] if all_alerts else ""

        # Return list of alerts
        return all_alerts, None, primary_alert_type, is_tropical

    except Exception as e:
        print(f"Error getting weather alerts: {e}")
        return [], None, None, False

def draw_text(screen, text, pos, font_path, font_size, font_cache, color=(255, 255, 255), center_x=False):
    font_key = (font_path, font_size)
    if font_key in font_cache: font = font_cache[font_key]
    else:
        try: font = pygame.font.Font(font_path, font_size)
        except: font = pygame.font.SysFont(None, font_size, bold="bold" in font_path.lower())
        font_cache[font_key] = font
    rendered = font.render(text, True, color)
    text_rect = rendered.get_rect()
    if center_x: text_rect.midtop = (pos[0], pos[1])
    else: text_rect.topleft = pos
    screen.blit(rendered, text_rect)
    return rendered
# ...because an outline looks better!
def draw_outlined_text(screen, text, pos, font_path, font_size, text_color=(255, 255, 255), outline_color=(0, 0, 0), outline_width=10, center_x=False):
    x, y = pos
    if center_x:
        freetype_draw(text, center=(x, y), fontname=font_path, fontsize=font_size,
                      color=text_color, outline_color=outline_color, outline_width=outline_width, surf=screen)
    else:
        freetype_draw(text, (x, y), fontname=font_path, fontsize=font_size,
                      color=text_color, outline_color=outline_color, outline_width=outline_width, surf=screen)

# Font cache to avoid re-loading fonts
_font_cache = {}

def freetype_draw(text, pos=None, center=None, midtop=None, topleft=None, fontname=None, fontsize=12, 
                 color=(255, 255, 255), outline_color=None, outline_width=0, surf=None, italic=False):
    if surf is None:
        return
    font_key = (fontname, fontsize, italic)  # Add italic to cache key
    if font_key not in _font_cache:
        _font_cache[font_key] = pygame.freetype.Font(fontname, fontsize)
        if italic:
            _font_cache[font_key].oblique = True  # Use oblique instead of STYLE_ITALIC
    font = _font_cache[font_key]
    
    # freetype positioning
    text_rect = font.get_rect(text)
    
    # Render text with outline if specified
    if outline_width > 0 and outline_color is not None:
        # Create surface large enough for outline
        outline_size = outline_width * 2
        total_width = text_rect.width + outline_size
        total_height = text_rect.height + outline_size
        outline_surface = pygame.Surface((total_width, total_height), pygame.SRCALPHA)
        
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:  # Skip center position
                    font.render_to(outline_surface, (outline_width + dx, outline_width + dy), text, outline_color)
        
        # Render main text on top
        font.render_to(outline_surface, (outline_width, outline_width), text, color)
        
        # Position the outlined text with resolution-specific offsets
        final_rect = pygame.Rect(0, 0, total_width, total_height)
        
        # Resolution-specific positioning offsets for low-res displays
        pos_offset_x = 0
        pos_offset_y = 0
        if SCREEN_WIDTH < 1280 or SCREEN_HEIGHT < 720:
            if SCREEN_WIDTH <= 896:  # 896x504 and below
                pos_offset_x = 2
                pos_offset_y = 4
            elif SCREEN_WIDTH <= 960:  # 960x540
                pos_offset_x = 1
                pos_offset_y = 3
            elif SCREEN_WIDTH <= 1024:  # 1024x576, 1024x600
                pos_offset_x = 1
                pos_offset_y = 2
        
        if center is not None:
            final_rect.center = (center[0] + pos_offset_x, center[1] + pos_offset_y)
        elif midtop is not None:
            final_rect.midtop = (midtop[0] + pos_offset_x, midtop[1] + pos_offset_y)
        elif topleft is not None:
            # Adjust for outline offset and low-res positioning
            final_rect.topleft = (topleft[0] - outline_width + pos_offset_x, topleft[1] - outline_width + pos_offset_y)
        elif pos is not None:
            # Adjust for outline offset and low-res positioning
            final_rect.topleft = (pos[0] - outline_width + pos_offset_x, pos[1] - outline_width + pos_offset_y)
        
        surf.blit(outline_surface, final_rect)
    else:
        # No outline - direct rendering with resolution-specific positioning
        pos_offset_x = 0
        pos_offset_y = 0
        if SCREEN_WIDTH < 1280 or SCREEN_HEIGHT < 720:
            if SCREEN_WIDTH <= 896:  # 896x504 and below
                pos_offset_x = 2
                pos_offset_y = 3
            elif SCREEN_WIDTH <= 960:  # 960x540
                pos_offset_x = 1
                pos_offset_y = 2
            elif SCREEN_WIDTH <= 1024:  # 1024x576, 1024x600
                pos_offset_x = 1
                pos_offset_y = 1
        
        if center is not None:
            text_rect.center = (center[0] + pos_offset_x, center[1] + pos_offset_y)
            font.render_to(surf, text_rect.topleft, text, color)
        elif midtop is not None:
            text_rect.midtop = (midtop[0] + pos_offset_x, midtop[1] + pos_offset_y)
            font.render_to(surf, text_rect.topleft, text, color)
        elif topleft is not None:
            font.render_to(surf, (topleft[0] + pos_offset_x, topleft[1] + pos_offset_y), text, color)
        elif pos is not None:
            font.render_to(surf, (pos[0] + pos_offset_x, pos[1] + pos_offset_y), text, color)

def get_cached_warning_surface(text, fontname, fontsize, color, outline_color, outline_width, italic, cache_dict):

    # Create cache key from all rendering parameters including quality factor
    cache_key = (text, fontname, fontsize, tuple(color) if color else None,
                 tuple(outline_color) if outline_color else None, outline_width, italic, QUALITY_FACTOR)

    # Return cached surface if it exists
    if cache_key in cache_dict:
        return cache_dict[cache_key]

    # Create new surface with the text rendered
    font_key = (fontname, fontsize, italic)
    if font_key not in _font_cache:
        font = pygame.freetype.Font(fontname, fontsize)
        if italic:
            font.oblique = True  # Use oblique for italic style
        _font_cache[font_key] = font
    else:
        font = _font_cache[font_key]

    text_rect = font.get_rect(text)

    # Create surface with outline
    if outline_width > 0 and outline_color is not None:
        outline_size = outline_width * 2
        # Add extra padding for italic slant and anti-aliasing (especially on right/bottom)
        padding_x = max(outline_width, int(fontsize * 0.3)) if italic else outline_width  # Extra for italic slant
        # Use larger vertical padding to avoid outline being thinned/cut off at varied scales; also scale with fontsize
        padding_y = max(outline_width * 4, int(fontsize * 0.2))  # Extra vertical space that grows with text size
        total_width = text_rect.width + outline_size + padding_x
        total_height = text_rect.height + outline_size + padding_y
        surface = pygame.Surface((total_width, total_height), pygame.SRCALPHA)

        # Render outline
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    font.render_to(surface, (outline_width + dx, outline_width + dy), text, outline_color)

        # Render main text on top
        font.render_to(surface, (outline_width, outline_width), text, color)
    else:
        # No outline - simple rendering
        surface = pygame.Surface((text_rect.width, text_rect.height), pygame.SRCALPHA)
        font.render_to(surface, (0, 0), text, color)

    # Apply quality factor scaling (same pattern as panels)
    if QUALITY_FACTOR < 1.0:
        original_size = surface.get_size()
        intermediate_w = int(original_size[0] * QUALITY_FACTOR)
        intermediate_h = int(original_size[1] * QUALITY_FACTOR)
        # Scale down then back up for quality reduction
        intermediate = pygame.transform.smoothscale(surface, (intermediate_w, intermediate_h))
        surface = pygame.transform.smoothscale(intermediate, original_size)

    # Cache and return
    cache_dict[cache_key] = surface
    return surface

def draw_pre_rendered_text(screen, text, pos, char_cache):
    x, y = pos
    for char in text:
        if char in char_cache:
            char_surface = char_cache[char]
            screen.blit(char_surface, (x, y))
            x += char_surface.get_width()

def draw_gradient_text(screen, text, pos, font_path, font_size, color_top, color_bottom, outline_color=None, outline_width=0):
    try:
        font = pygame.font.Font(font_path, font_size)
    except:
        font = pygame.font.SysFont(None, font_size)

    # Create a surface large enough for text + outline
    text_surface = font.render(text, True, (255, 255, 255))
    padding = outline_width * 2
    full_width = text_surface.get_width() + padding
    full_height = text_surface.get_height() + padding

    # Create a surface to hold both outline and gradient
    final_surface = pygame.Surface((full_width, full_height), pygame.SRCALPHA)

    # Draw outline first if requested
    if outline_color and outline_width > 0:
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    outline_surface = font.render(text, True, outline_color)
                    final_surface.blit(outline_surface, (outline_width + dx, outline_width + dy))

    # Create gradient text
    gradient_surface = pygame.Surface(text_surface.get_size(), pygame.SRCALPHA)

    # Apply gradient to text pixels
    for y in range(text_surface.get_height()):
        ratio = y / text_surface.get_height() if text_surface.get_height() > 0 else 0
        r = int(color_top[0] * (1 - ratio) + color_bottom[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bottom[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bottom[2] * ratio)

        for x in range(text_surface.get_width()):
            if text_surface.get_at((x, y))[3] > 0:
                gradient_surface.set_at((x, y), (r, g, b, 255))

    final_surface.blit(gradient_surface, (outline_width, outline_width))

    screen.blit(final_surface, (pos[0] - outline_width, pos[1] - outline_width))

def get_weather_icon_filename(condition, is_night=False, wind_speed=0, gust_speed=0):
    condition = condition.lower().strip()
    time_suffix = "-night" if is_night else ""

    # Load the JSON config for condition names.
    with open('var/cond_names.json', 'r') as f:
        config = json.load(f)

    # Special handling for "then" conditions (changing weather)
    if "then" in condition:
        storm_words = config['special_cases']['then_conditions']['storm_words']
        if any(storm_word in condition for storm_word in storm_words):
            before_then = condition.split("then")[0]
            after_then = condition.split("then")[1]

            # For NIGHT periods, logic is reversed:
            if is_night:
                if any(storm_word in before_then for storm_word in storm_words):
                    return f"textures/icons/weather-storm-night-pm.png"
                elif any(storm_word in after_then for storm_word in storm_words):
                    return f"textures/icons/weather-storm-night-am.png"
            # For DAY periods:
            else:
                if any(storm_word in before_then for storm_word in storm_words) \
                or any(storm_word in after_then for storm_word in storm_words):
                    return "textures/icons/weather-storm-day-pm.png"


    # Check if windy is explicitly mentioned
    if "windy" in condition:
        for mapping in config['windy_mappings']:
            if any(cond in condition for cond in mapping['conditions']):
                icon = mapping['icon'].replace("{time_suffix}", time_suffix)
                return f"textures/icons/{icon}"
        # Default windy
        return f"textures/icons/weather-clear{time_suffix}-wind.png"

    # Find the base icon
    icon = None
    for mapping in config['icon_mappings']:
        if isinstance(mapping['conditions'], list):
            # Multiple conditions that must ALL be present
            if mapping.get('require_all', False):
                if all(word in condition for word in mapping['conditions']):
                    icon = mapping['icon']
                    break
        else:
            # Single condition
            if mapping['conditions'] in condition:
                icon = mapping['icon']
                break

    if icon is None and "clear" in condition:
        if any(mod in condition for mod in config['clear_modifiers']['conditions']):
            icon = config['clear_modifiers']['icon']

    # Use default if no match found
    if icon is None:
        icon = config['default_icon']

    # Replace placeholders
    icon = icon.replace("{time_suffix}", time_suffix)
    if "{day_night}" in icon:
        icon = icon.replace("{day_night}", "-day" if not is_night else "-night")

    # Check if we need wind variant due to high wind/gust speeds
    wind_threshold = config['special_cases']['wind_thresholds']
    if wind_speed >= wind_threshold['wind_speed'] or gust_speed >= wind_threshold['gust_speed']:
        # Check if this icon type can have a wind variant
        for compatible in config['special_cases']['wind_compatible_icons']:
            if compatible in icon and "-wind" not in icon:
                # Insert -wind before .png
                icon = icon.replace(".png", "-wind.png")
                break
    if not icon.startswith("textures/icons/"):
        icon = f"textures/icons/{icon}"

    return icon

def create_forecast_panel_surface(forecast_periods, scaled_config, screen_width, panel_texture_cache, weather_icon_cache, font_cache):
    if not forecast_periods: return None
    config = scaled_config["CURRENT_CONDITIONS_CONFIG"]
    padding = config["padding"]
    panel_width = config["width"]
    panel_height = config["max_height"]

    use_truncation = True

    def truncate_forecast_text(text):
        if not use_truncation:
            return text

        # Word too big, make word small.
        replacements = {
            "Slight": "Slgt",
            "Thunderstorms": "T-storms",
            "Thunderstorm": "T-storm",
            "And": "&",
            "and": "&",
            "Scattered": "Sct'd",
            "Isolated": "Isol",
            "Temperature": "Temp",
            "Precipitation": "Precip"
        }
        result = text
        for full, short in replacements.items():
            result = result.replace(full, short)
        return result

    try:
        def get_font(size_key, is_detail=False):
            size = int(config[size_key] * 0.85) if is_detail else config[size_key]
            key = (config["font_path"], size)
            if key not in font_cache: font_cache[key] = pygame.font.Font(key[0], key[1])
            return font_cache[key]
        title_font = get_font("title_font_size")
        period_font = get_font("data_font_size")
        detail_font = get_font("data_font_size", is_detail=True)
    except Exception as e:
        print(f"Error loading font for forecast panel: {e}"); return None

    panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
    try:
        # Cache the scaled panel texture to avoid disk I/O on every render
        cache_key = f"panel_bg_{panel_width}x{panel_height}_q{QUALITY_FACTOR}"
        if cache_key in panel_texture_cache:
            panel_bg_texture = panel_texture_cache[cache_key]
        else:
            loaded_tex = pygame.image.load(PANEL_TEXTURE_PATH).convert_alpha()
            if QUALITY_FACTOR < 1.0:
                intermediate_w = int(panel_width * QUALITY_FACTOR)
                intermediate_h = int(panel_height * QUALITY_FACTOR)
                temp_texture = pygame.transform.smoothscale(loaded_tex, (intermediate_w, intermediate_h))
                panel_bg_texture = pygame.transform.smoothscale(temp_texture, (panel_width, panel_height))
            else:
                panel_bg_texture = pygame.transform.smoothscale(loaded_tex, (panel_width, panel_height))
            panel_texture_cache[cache_key] = panel_bg_texture
        panel_surface.blit(panel_bg_texture, (0, 0))
    except:
        panel_surface.fill(config["background_color"])

    y_pos_draw = padding
    # Draw "72 Hour Forecast" with white text and black outline using ptext, this looks amazing!
    freetype_draw("72 Hour Forecast", (padding, y_pos_draw + 4), fontname=config["font_path"],
                  fontsize=config["title_font_size"], color=(255, 255, 255),
                  outline_color=(0, 0, 0), outline_width=scale_value(4, scaled_config["scale_y"]), surf=panel_surface, italic=True)
    y_pos_draw += title_font.get_height() + 10
    entries_to_draw = forecast_periods[:6]
    content_height = title_font.get_height() + 10
    for period in entries_to_draw:
        content_height += period_font.get_height() + 5
        # Apply truncation before calculating line heights
        truncated_forecast = truncate_forecast_text(period.get('shortForecast', ''))
        words = truncated_forecast.split(); lines = []; current_line = []
        text_width = panel_width - padding * 2 - 70
        for word in words:
            if detail_font.size(' '.join(current_line + [word]))[0] < text_width: current_line.append(word)
            else: lines.append(' '.join(current_line)); current_line = [word]
        lines.append(' '.join(current_line))
        content_height += len(lines) * int(config["line_height"] * 0.9)

    remaining_space = panel_height - (padding * 1) - content_height
    spacing_between_entries = 15
    if len(entries_to_draw) > 1 and remaining_space > 0:
        spacing_between_entries += remaining_space / (len(entries_to_draw) - 1)

    for i, period in enumerate(entries_to_draw):
        if y_pos_draw + config["line_height"] > panel_height - padding: break
        icon_size = int(config["line_height"] * FORECAST_ICON_SIZE_MULTIPLIER)

        day_name = period.get('name', '')
        freetype_draw(day_name + " - ",
                      (padding, y_pos_draw),
                      fontname=config["font_path"],
                      fontsize=config["data_font_size"],
                      color=(220, 221, 51),
                      outline_color=(0, 0, 0),
                      outline_width=scale_value(2, scaled_config["scale_y"]),
                      surf=panel_surface)
        day_text_width = period_font.size(day_name + " - ")[0]
        temp_x_start = padding + day_text_width

        # 72 Hour Forecast text.
        temp_text = f"{period.get('temperature', '')}°{period.get('temperatureUnit', '')}"
        freetype_draw(temp_text,
                      (temp_x_start, y_pos_draw),
                      fontname=config["font_path"],
                      fontsize=config["data_font_size"],
                      color=(255, 255, 255),
                      outline_color=(0, 0, 0),
                      outline_width=scale_value(3, scaled_config["scale_y"]),
                      surf=panel_surface)

        # Check for tropical storm/hurricane conditions and override icon
        forecast_text = period.get('shortForecast', '').lower()
        if "tropical storm" in forecast_text or "hurricane" in forecast_text:
            time_suffix = "night" if "night" in period.get('name', '').lower() else "day"
            icon_filename = f"textures/icons/weather-storm-{time_suffix}-wind.png"
        else:
            icon_filename = get_weather_icon_filename(period.get('shortForecast', ''), "night" in period.get('name', '').lower())
        loaded_icon = pygame.image.load(icon_filename).convert_alpha()
        if QUALITY_FACTOR < 1.0:
            intermediate_size = int(icon_size * QUALITY_FACTOR)
            temp_icon = pygame.transform.smoothscale(loaded_icon, (intermediate_size, intermediate_size))
            icon_image = pygame.transform.smoothscale(temp_icon, (icon_size, icon_size))
        else:
            icon_image = pygame.transform.smoothscale(loaded_icon, (icon_size, icon_size))
        panel_surface.blit(icon_image, (panel_width - padding - icon_size - 2, y_pos_draw))
        if SCREEN_WIDTH == 896 and SCREEN_HEIGHT == 504:
            y_pos_draw += period_font.get_height() + 1.75
        elif SCREEN_WIDTH == 960 and SCREEN_HEIGHT == 540:
            y_pos_draw += period_font.get_height() + 2
        else:
            y_pos_draw += period_font.get_height() + 5

        # Apply truncation to the forecast text
        original_forecast = period.get('shortForecast', '')
        truncated_forecast = truncate_forecast_text(original_forecast)

        words = truncated_forecast.split(); lines = []; current_line = []
        text_width = panel_width - padding * 2 - 70
        for word in words:
            if detail_font.size(' '.join(current_line + [word]))[0] < text_width: current_line.append(word)
            else: lines.append(' '.join(current_line)); current_line = [word]
        lines.append(' '.join(current_line))
        for line in lines:
            if y_pos_draw + detail_font.get_height() > panel_height - padding: break
            panel_surface.blit(detail_font.render(line, True, config["color"]), (padding + 10, y_pos_draw))
            y_pos_draw += int(config["line_height"] * 0.85)

        y_pos_draw += spacing_between_entries
        if i < len(entries_to_draw) - 1 and y_pos_draw < panel_height - padding:
             pygame.draw.line(panel_surface, (100, 100, 100), (padding, y_pos_draw - (spacing_between_entries / 2)), (panel_width - padding, y_pos_draw - (spacing_between_entries / 2)), 1)

    # Apply quality reduction to the entire composed panel
    if QUALITY_FACTOR < 1.0:
        intermediate_w = int(panel_width * QUALITY_FACTOR)
        intermediate_h = int(panel_height * QUALITY_FACTOR)
        temp_panel = pygame.transform.smoothscale(panel_surface, (intermediate_w, intermediate_h))
        panel_surface = pygame.transform.smoothscale(temp_panel, (panel_width, panel_height))

    return panel_surface

def create_current_conditions_surface(current, location_name, scaled_config, panel_texture_cache, weather_icon_cache, font_cache, primary_alert_type=None):
    if not current: return None
    config = scaled_config["CURRENT_CONDITIONS_CONFIG"]
    padding = config["padding"]
    panel_width = config["width"]
    panel_height = config["max_height"]

    # Alert type passed as parameter to avoid redundant API call

    try:
        def get_font(size_key=None, base_size=None):
            size = base_size if base_size is not None else config[size_key]
            key = (config["font_path"], size)
            if key not in font_cache: font_cache[key] = pygame.font.Font(key[0], key[1])
            return font_cache[key]
        title_font = get_font(size_key="title_font_size")
        temp_font = get_font(base_size=scale_font_size(80, scaled_config['scale_y']))
        desc_font = get_font(size_key="condition_desc_font_size")
        list_font = get_font(size_key="list_font_size")
    except Exception as e:
        print(f"Error loading font for conditions panel: {e}"); return None
    panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
    try:
        # Cache the scaled panel texture to avoid disk I/O on every render
        cache_key = f"panel_bg_{panel_width}x{panel_height}_q{QUALITY_FACTOR}"
        if cache_key in panel_texture_cache:
            panel_bg_texture = panel_texture_cache[cache_key]
        else:
            loaded_tex = pygame.image.load(PANEL_TEXTURE_PATH).convert_alpha()
            if QUALITY_FACTOR < 1.0:
                intermediate_w = int(panel_width * QUALITY_FACTOR)
                intermediate_h = int(panel_height * QUALITY_FACTOR)
                temp_texture = pygame.transform.smoothscale(loaded_tex, (intermediate_w, intermediate_h))
                panel_bg_texture = pygame.transform.smoothscale(temp_texture, (panel_width, panel_height))
            else:
                panel_bg_texture = pygame.transform.smoothscale(loaded_tex, (panel_width, panel_height))
            panel_texture_cache[cache_key] = panel_bg_texture
        panel_surface.blit(panel_bg_texture, (0, 0))
    except:
        panel_surface.fill(config["background_color"])
    y_pos = padding
    freetype_draw(location_name, midtop=((panel_width // 2), y_pos), fontname=config["font_path"],
                  fontsize=config["title_font_size"], color=(0, 0, 0),
                  outline_color=(255, 255, 255), outline_width=scale_value(3, scaled_config["scale_y"]), surf=panel_surface)
    y_pos += title_font.get_height() + 15

    icon_size_val = int(panel_height * CURRENT_CONDITIONS_ICON_SIZE_RATIO)
    is_night = not current.get("isDaytime", True)
    
    # Extract wind and gust speeds to determine if wind variant icon should be used
    wind_speed = 0
    gust_speed = 0
    try:
        wind_data = current.get('wind', 'N/A')
        if wind_data != 'N/A' and wind_data != 'None':
            wind_speed = int(wind_data.split()[0])
    except (ValueError, IndexError):
        pass
    
    try:
        gust_data = current.get('gusts', 'N/A')  
        if gust_data != 'N/A' and gust_data != 'None':
            gust_speed = int(gust_data.split()[0])
    except (ValueError, IndexError):
        pass
    
    icon_filename = get_weather_icon_filename(current.get('conditions', 'N/A'), is_night, wind_speed, gust_speed)
    loaded_icon = pygame.image.load(icon_filename).convert_alpha()
    if QUALITY_FACTOR < 1.0:
        intermediate_size = int(icon_size_val * QUALITY_FACTOR)
        temp_icon = pygame.transform.smoothscale(loaded_icon, (intermediate_size, intermediate_size))
        icon_image = pygame.transform.smoothscale(temp_icon, (icon_size_val, icon_size_val))
    else:
        icon_image = pygame.transform.smoothscale(loaded_icon, (icon_size_val, icon_size_val))
    panel_surface.blit(icon_image, ((panel_width - icon_size_val) // 2, y_pos)); y_pos += icon_size_val + 15

    is_heat_alert = primary_alert_type and ("HEAT" in primary_alert_type.upper())
    is_cold_alert = primary_alert_type and any(word in primary_alert_type.upper() for word in ["FREEZE", "FROST", "EXTREME COLD"])
    
    if is_heat_alert:
        temp_color = (200, 0, 25)  # Red for heat
    elif is_cold_alert:
        temp_color = (50, 150, 255)  # Light blue for cold
    else:
        temp_color = config["color"]

    freetype_draw(f"{current.get('temperature', 'N/A')}°F",
                  midtop=((panel_width // 2), y_pos + 5),
                  fontname=config["font_path"],
                  fontsize=scale_font_size(80, scaled_config['scale_y']),
                  color=temp_color,
                  outline_color=(0, 0, 0),
                  outline_width=scale_value(6, scaled_config["scale_y"]),
                  surf=panel_surface)
    y_pos += temp_font.get_height() + 15

    conditions_text = current.get('conditions', 'N/A')
    x_offset = config.get("condition_desc_x_offset", 0)
    freetype_draw(conditions_text,
                  midtop=((panel_width // 2) + x_offset, y_pos),
                  fontname=config["font_path"],
                  fontsize=config["condition_desc_font_size"],
                  color=config["color"],
                  outline_color=(0, 0, 0),
                  outline_width=scale_value(5, scaled_config["scale_y"]),
                  surf=panel_surface)
    y_pos += desc_font.get_height() + 20

    conditions_list = [("Humidity", current.get('humidity', 'N/A')), ("Dew Point", current.get('dewpoint', 'N/A')), ("Pressure", current.get('pressure', 'N/A')), ("Visibility", current.get('visibility', 'N/A')), ("Wind", current.get('wind', 'N/A')), ("Gusts", current.get('gusts', 'N/A'))]
    remaining_height = panel_height - y_pos - padding
    if conditions_list and remaining_height > 20:
        dynamic_line_height = remaining_height / len(conditions_list)
        max_label_width = max([list_font.size(f"{label}:")[0] for label, _ in conditions_list])
        list_start_x = padding
        for label, value in conditions_list:
            freetype_draw(f"{label}:",
                          (list_start_x, y_pos),
                          fontname=config["font_path"],
                          fontsize=config["list_font_size"],
                          color=config["title_color"],  # Yellow color
                          outline_color=(0, 0, 0),
                          outline_width=scale_value(2, scaled_config["scale_y"]),
                          surf=panel_surface)

            if label == "Wind" or label == "Gusts":
                try:
                    if value != "N/A" and value != "None":
                        # Extract number from strings like "7 mph NE" or "40 mph"
                        wind_speed = int(value.split()[0])

                        # Determine color based on speed
                        if (label == "Wind" and wind_speed >= 25) or (label == "Gusts" and wind_speed >= 40):
                            text_color = (175, 15, 5)
                        else:
                            text_color = config["color"]
                    else:
                        text_color = config["color"]
                except:
                    text_color = config["color"]

                # Draw with freetype for outline
                freetype_draw(str(value),
                             (list_start_x + max_label_width + 20, y_pos),
                             fontname=config["font_path"],
                             fontsize=config["list_font_size"],
                             color=text_color,
                             outline_color=(0, 0, 0),
                             outline_width=scale_value(3, scaled_config["scale_y"]),
                             surf=panel_surface)
            else:
                # Draw with freetype for outline
                freetype_draw(str(value),
                             (list_start_x + max_label_width + 20, y_pos),
                             fontname=config["font_path"],
                             fontsize=config["list_font_size"],
                             color=config["color"],
                             outline_color=(0, 0, 0),
                             outline_width=scale_value(3, scaled_config["scale_y"]),
                             surf=panel_surface)
            y_pos += dynamic_line_height

    # Apply quality reduction to the entire composed panel
    if QUALITY_FACTOR < 1.0:
        intermediate_w = int(panel_width * QUALITY_FACTOR)
        intermediate_h = int(panel_height * QUALITY_FACTOR)
        temp_panel = pygame.transform.smoothscale(panel_surface, (intermediate_w, intermediate_h))
        panel_surface = pygame.transform.smoothscale(temp_panel, (panel_width, panel_height))

    return panel_surface

# Panel flipping animation, I should probably change the names of these variables later!
def create_panel_partial_flip_surfaces(panel_surface_to_animate, original_panel_width, num_animation_steps):
    shrink_frames = []
    expand_frames = []

    if not panel_surface_to_animate or original_panel_width == 0:

        dummy_surface = pygame.Surface((1,1), pygame.SRCALPHA)
        for _ in range(num_animation_steps + 1):
            shrink_frames.append(dummy_surface)
            expand_frames.append(dummy_surface)
        return shrink_frames, expand_frames

    panel_height = panel_surface_to_animate.get_height()
    if panel_height == 0:
        dummy_surface = pygame.Surface((1,1), pygame.SRCALPHA)
        for _ in range(num_animation_steps + 1):
            shrink_frames.append(dummy_surface)
            expand_frames.append(dummy_surface)
        return shrink_frames, expand_frames

    for i in range(num_animation_steps + 1):

        scale_shrink = 1.0 - (i / num_animation_steps) if num_animation_steps > 0 else 0.0

        scaled_width_shrink = max(0, int(original_panel_width * scale_shrink))
        if scaled_width_shrink > 0 :
            if QUALITY_FACTOR < 1.0:
                intermediate_w = int(scaled_width_shrink * QUALITY_FACTOR)
                intermediate_h = int(panel_height * QUALITY_FACTOR)
                temp_frame = pygame.transform.smoothscale(panel_surface_to_animate, (intermediate_w, intermediate_h))
                shrink_frames.append(pygame.transform.smoothscale(temp_frame, (scaled_width_shrink, panel_height)))
            else:
                shrink_frames.append(pygame.transform.smoothscale(panel_surface_to_animate, (scaled_width_shrink, panel_height)))
        else:
            shrink_frames.append(pygame.Surface((0, panel_height), pygame.SRCALPHA))

        scale_expand = i / num_animation_steps if num_animation_steps > 0 else 1.0
        scaled_width_expand = max(0, int(original_panel_width * scale_expand))
        if scaled_width_expand > 0:
            if QUALITY_FACTOR < 1.0:
                intermediate_w = int(scaled_width_expand * QUALITY_FACTOR)
                intermediate_h = int(panel_height * QUALITY_FACTOR)
                temp_frame = pygame.transform.smoothscale(panel_surface_to_animate, (intermediate_w, intermediate_h))
                expand_frames.append(pygame.transform.smoothscale(temp_frame, (scaled_width_expand, panel_height)))
            else:
                expand_frames.append(pygame.transform.smoothscale(panel_surface_to_animate, (scaled_width_expand, panel_height)))
        else:
            expand_frames.append(pygame.Surface((0, panel_height), pygame.SRCALPHA))

    return shrink_frames, expand_frames

def create_all_pre_rendered_frames(radar_frames_list, conditions_panel_full, forecast_panel_full, title_text, mini8s_logo, logo_rect,
                                   current_bar_texture, warning_text, scaled_config, font_cache, panel_flip_anim_steps_config):

    global base_common_frames_global, pre_rendered_frames_conditions, pre_rendered_frames_forecast
    global panel_shrink_cond_surfaces, panel_expand_cond_surfaces, panel_shrink_fcst_surfaces, panel_expand_fcst_surfaces

    # Clear all old frames
    base_common_frames_global.clear()
    pre_rendered_frames_conditions.clear()
    pre_rendered_frames_forecast.clear()
    panel_shrink_cond_surfaces.clear()
    panel_expand_cond_surfaces.clear()
    panel_shrink_fcst_surfaces.clear()
    panel_expand_fcst_surfaces.clear()

    if radar_frames_list:
        # Uses the last frame and pauses with it for its set time..
        base_frame = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        base_frame.fill((0, 0, 0))

        # Only process the LAST radar frame!
        last_frame_img = radar_frames_list[-1]
        frame_rect = last_frame_img.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        base_frame.blit(last_frame_img, frame_rect)
        draw_text(base_frame, title_text, scaled_config["TITLE_CONFIG"]["position"], scaled_config["TITLE_CONFIG"]["font_path"], scaled_config["TITLE_CONFIG"]["font_size"], font_cache, scaled_config["TITLE_CONFIG"]["color"])
        if mini8s_logo:
            base_frame.blit(mini8s_logo, logo_rect)
        if current_bar_texture:
            bar_rect = current_bar_texture.get_rect()
            bar_rect.topleft = (0, SCREEN_HEIGHT - bar_rect.height)
            base_frame.blit(current_bar_texture, bar_rect)
        draw_text(base_frame, warning_text, scaled_config["TKR_WARNING_TITLE_CONFIG"]["position"], scaled_config["TKR_WARNING_TITLE_CONFIG"]["font_path"], scaled_config["TKR_WARNING_TITLE_CONFIG"]["font_size"], font_cache, scaled_config["TKR_WARNING_TITLE_CONFIG"]["color"])
        base_common_frames_global.append(base_frame)
    else:
        # Log the fatal error
        error_msg = getattr(fetch_radar_image, 'last_error', 'Unknown error - radar GIF failed to load')
        log_fatal_error(error_msg)
        return  # Exit early on error
        
    base_common_frames_global.append(base_frame)

    # Only process panels if we're not in BSOD mode
    panel_pos = scaled_config["CURRENT_CONDITIONS_CONFIG"]["position"]
    for base_common_frame_with_radar in base_common_frames_global:
        if conditions_panel_full:
            frame_cond = base_common_frame_with_radar.copy()
            frame_cond.blit(conditions_panel_full, panel_pos)
            pre_rendered_frames_conditions.append(frame_cond.convert())

        if forecast_panel_full:
            frame_fcst = base_common_frame_with_radar.copy()
            frame_fcst.blit(forecast_panel_full, panel_pos)
            pre_rendered_frames_forecast.append(frame_fcst.convert())

    panel_original_width = scaled_config["CURRENT_CONDITIONS_CONFIG"]["width"]
    if conditions_panel_full:
        panel_shrink_cond_surfaces, panel_expand_cond_surfaces = create_panel_partial_flip_surfaces(
            conditions_panel_full, panel_original_width, panel_flip_anim_steps_config)
    if forecast_panel_full:
        panel_shrink_fcst_surfaces, panel_expand_fcst_surfaces = create_panel_partial_flip_surfaces(
            forecast_panel_full, panel_original_width, panel_flip_anim_steps_config)

def draw_loading_screen(screen, message="Loading...", font_cache=None, motd_text=None, motd_y_position=None, scale_x=1.0, scale_y=1.0):
    display_width = screen.get_width()
    display_height = screen.get_height()

    # Load and draw background image, this may be replaced before v0.4.0 due to intellectual monopoly grant concerns.
    try:
        bg_image = pygame.image.load("textures/graphics/background.png").convert()
        # Scale background to fit screen
        if QUALITY_FACTOR < 1.0:
            intermediate_w = int(display_width * QUALITY_FACTOR)
            intermediate_h = int(display_height * QUALITY_FACTOR)
            temp_bg = pygame.transform.smoothscale(bg_image, (intermediate_w, intermediate_h))
            bg_image = pygame.transform.smoothscale(temp_bg, (display_width, display_height))
        else:
            bg_image = pygame.transform.smoothscale(bg_image, (display_width, display_height))
        screen.blit(bg_image, (0, 0))
    except Exception as e:
        screen.fill((0, 0, 0))
        print(f"Could not load background image: {e}")
    main_font_size = scale_font_size(80, scale_y)
    motd_font_size = scale_font_size(40, scale_y)
    version_font_size = scale_font_size(28, scale_y)

    # Load and draw the appropriate loading message image
    message_image_map = {
        "Grabbing Weather Data...": "textures/graphics/grabbingweatherdata.png",
        "Loading Radar Data...": "textures/graphics/loadingradardata.png",
        "Pre-Rendering...": "textures/graphics/prerendering.png"
    }
    
    if message in message_image_map:
        try:
            # Load and scale the message image
            message_img = pygame.image.load(message_image_map[message]).convert_alpha()
            # Scale height to match original text size (approximately 1.5x font size)
            target_height = int(main_font_size * 1.5)
            # Maintain aspect ratio
            aspect_ratio = message_img.get_width() / message_img.get_height()
            target_width = int(target_height * aspect_ratio)

            if QUALITY_FACTOR < 1.0:
                intermediate_w = int(target_width * QUALITY_FACTOR)
                intermediate_h = int(target_height * QUALITY_FACTOR)
                temp_msg = pygame.transform.smoothscale(message_img, (intermediate_w, intermediate_h))
                message_img = pygame.transform.smoothscale(temp_msg, (target_width, target_height))
            else:
                message_img = pygame.transform.smoothscale(message_img, (target_width, target_height))
            
            message_rect = message_img.get_rect(center=(display_width // 2, display_height // 2 - scale_value(80, scale_y)))
            screen.blit(message_img, message_rect)
        except Exception as e:
            # Fallback to text if image loading fails
            freetype_draw(message,
                        center=(display_width // 2, display_height // 2 - scale_value(80, scale_y)),
                        fontname="fonts/Interstate_Bold.otf",
                        fontsize=main_font_size,
                        color=(255, 255, 255),
                        outline_color=(0, 0, 0),
                        outline_width=scale_value(5, scale_y),
                        surf=screen)
    else:
        # For any other messages, use the original text rendering
        freetype_draw(message,
                    center=(display_width // 2, display_height // 2 - scale_value(80, scale_y)),
                    fontname="fonts/Interstate_Bold.otf",
                    fontsize=main_font_size,
                    color=(255, 255, 255),
                    outline_color=(0, 0, 0),
                    outline_width=scale_value(5, scale_y),
                    surf=screen)
    if motd_text:
        motd_y = motd_y_position if motd_y_position else display_height - scale_value(150, scale_y)

        # Determine color based on content (check for certain keywords)
        is_urgent = any(word in motd_text.upper() for word in ["HURRICANE", "TROPICAL", "REDMODE", "DANGEROUS"])
        motd_color = (255, 50, 50) if is_urgent else (200, 200, 200)

        freetype_draw(motd_text,
                      center=(display_width // 2, motd_y),
                      fontname="fonts/Interstate_Light.otf",
                      fontsize=motd_font_size,
                      color=motd_color,
                      outline_color=(0, 0, 0),
                      outline_width=scale_value(5, scale_y),
                      surf=screen)

    try:
        version_logo = pygame.image.load("textures/graphics/mini8s_logo_verstring.png").convert_alpha()
        logo_scale = min(scale_x, scale_y) * 0.65
        target_w = int(version_logo.get_width() * logo_scale)
        target_h = int(version_logo.get_height() * logo_scale)
        if QUALITY_FACTOR < 1.0:
            intermediate_w = int(target_w * QUALITY_FACTOR)
            intermediate_h = int(target_h * QUALITY_FACTOR)
            temp_logo = pygame.transform.smoothscale(version_logo, (intermediate_w, intermediate_h))
            version_logo = pygame.transform.smoothscale(temp_logo, (target_w, target_h))
        else:
            version_logo = pygame.transform.smoothscale(version_logo, (target_w, target_h))
        logo_rect = version_logo.get_rect(center=(display_width // 2,
                                                   display_height // 2 + scale_value(120, scale_y)))
        screen.blit(version_logo, logo_rect)
    except Exception as e:
        # Fallback to text if image not found
        freetype_draw(f"Mini8s {VERSION}",
                      center=(display_width // 2, display_height // 2 + scale_value(100, scale_y)),
                      fontname="fonts/Interstate_Light.otf",
                      fontsize=version_font_size,
                      color=(255, 255, 255),
                      outline_color=(0, 0, 0),
                      outline_width=scale_value(2, scale_y),
                      surf=screen)
        print(f"Could not load version logo: {e}")

    # Process events to keep window responsive during loading, big bug fix!
    pygame.event.pump()
    pygame.display.flip()

    # EVERYTHING HERE IS PYQT5 SETUP SCREEN LOGIC!

class HoverLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Create the hover text label
        self.hover_text = QLabel("Advanced Settings", parent)
        self.hover_text.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 180);
                padding: 4px 8px;
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)
        # Make sure it's sized properly
        self.hover_text.adjustSize()
        self.hover_text.hide()
        self.hover_timer = None
        
    def enterEvent(self, event):
        # Start timer when mouse enters
        self.hover_timer = self.startTimer(500)  # Show after 500ms
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        # Hide text and kill timer when mouse leaves
        if self.hover_timer:
            self.killTimer(self.hover_timer)
            self.hover_timer = None
        self.hover_text.hide()
        super().leaveEvent(event)
        
    def timerEvent(self, event):
        # When timer triggers, show the text
        if event.timerId() == self.hover_timer:
            self.killTimer(self.hover_timer)
            self.hover_timer = None
            # Calculate position relative to screen
            global_pos = self.mapToGlobal(QPoint(0, 0))
            text_x = global_pos.x() - self.hover_text.width() - 5  # Place to the left with 5px gap
            text_y = global_pos.y() + (self.height() - self.hover_text.height()) // 2
            # Convert back to parent coordinates
            parent_pos = self.parent().mapFromGlobal(QPoint(text_x, text_y))
            self.hover_text.move(parent_pos)
            self.hover_text.show()
            
    def mousePressEvent(self, event):
        # Hide the text when clicked
        self.hover_text.hide()
        if hasattr(self, '_mousePressEvent'):
            self._mousePressEvent(event)

class ImageButton(QLabel):
    """Custom button class that swaps between normal and hover images"""
    def __init__(self, image_path, hover_image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.hover_image_path = hover_image_path

        # Load and scale both images to 35% of original size
        original = QPixmap(image_path)
        self.normal_pixmap = original.scaled(
            int(original.width() * 0.40),
            int(original.height() * 0.40),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        hover_original = QPixmap(hover_image_path)
        self.hover_pixmap = hover_original.scaled(
            int(hover_original.width() * 0.40),
            int(hover_original.height() * 0.40),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.setPixmap(self.normal_pixmap)
        self.setFixedSize(self.normal_pixmap.size())
        self.setCursor(Qt.PointingHandCursor)
        self.click_callback = None

    def set_click_callback(self, callback):
        self.click_callback = callback

    def enterEvent(self, event):
        self.setPixmap(self.hover_pixmap)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setPixmap(self.normal_pixmap)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.click_callback:
            self.click_callback()
        super().mousePressEvent(event)

class Mini8sWelcome(QMainWindow):
    def __init__(self):
        super().__init__()
        self.should_start_mini8s = False  # Flag to track if Start button was pressed
        self.setWindowTitle(f"Welcome to Mini8s {VERSION}!")

        # Icon itself
        self.adv_settings_button = HoverLabel(self)
        self.adv_icon = QPixmap("textures/icons/adv-settings-icon.png")
        self.adv_icon = self.adv_icon.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.adv_settings_button.setPixmap(self.adv_icon)
        self.adv_settings_button.setFixedSize(48, 48)
        self.adv_settings_button.setCursor(Qt.PointingHandCursor)
        
        # Create advanced settings menu
        self.adv_menu = QMenu(self)
        self.fps_counter_action = self.adv_menu.addAction("Enable FPS Counter")
        self.fps_counter_action.setCheckable(True)

        self.disable_vsync_action = self.adv_menu.addAction("Disable VSync")
        self.disable_vsync_action.setCheckable(True)

        # Create Quality submenu
        self.quality_menu = self.adv_menu.addMenu("Quality")

        # Add quality options (Full is disabled/fake, others are selectable)
        self.quality_full_action = self.quality_menu.addAction("Full (100%, Default)")
        self.quality_full_action.setCheckable(False)
        self.quality_full_action.setEnabled(False)

        self.quality_menu.addSeparator()

        # Create action group for quality options (non-exclusive to allow unselecting)
        self.quality_action_group = QActionGroup(self)
        self.quality_action_group.setExclusive(False)  # Allow unchecking to return to Full

        self.quality_high_action = self.quality_menu.addAction("High (90%)")
        self.quality_high_action.setCheckable(True)
        self.quality_action_group.addAction(self.quality_high_action)

        self.quality_medium_action = self.quality_menu.addAction("Medium (85%)")
        self.quality_medium_action.setCheckable(True)
        self.quality_action_group.addAction(self.quality_medium_action)

        self.quality_low_action = self.quality_menu.addAction("Low (75%)")
        self.quality_low_action.setCheckable(True)
        self.quality_action_group.addAction(self.quality_low_action)

        self.quality_verylow_action = self.quality_menu.addAction("Very Low (65%)")
        self.quality_verylow_action.setCheckable(True)
        self.quality_action_group.addAction(self.quality_verylow_action)

        # Connect signals to maintain mutual exclusivity while allowing all to be unchecked
        self.quality_high_action.triggered.connect(lambda: self.handle_quality_selection(self.quality_high_action))
        self.quality_medium_action.triggered.connect(lambda: self.handle_quality_selection(self.quality_medium_action))
        self.quality_low_action.triggered.connect(lambda: self.handle_quality_selection(self.quality_low_action))
        self.quality_verylow_action.triggered.connect(lambda: self.handle_quality_selection(self.quality_verylow_action))

        # Connect FPS counter and VSync to save immediately when toggled
        self.fps_counter_action.triggered.connect(self.save_advanced_settings)
        self.disable_vsync_action.triggered.connect(self.save_advanced_settings)

        # Event handling
        self.adv_settings_button._mousePressEvent = self.show_adv_menu
        
        # Load configs
        try:
            with open('var/resolutions169.json', 'r') as f:
                self.resolution_config = json.load(f)
                self.allowed_resolutions = [(r['width'], r['height']) for r in self.resolution_config['allowed_resolutions']]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load resolutions169.json: {e}")
            self.allowed_resolutions = [(1920, 1080), (1280, 720)]  # Default fallback

        # Load saved configuration
        config_file = "config.json"
        default_config = {"last_width": 1280, "last_height": 720, "last_zip": "", "show_fps": False, "disable_vsync": False}
        try:
            with open(config_file, 'r') as f:
                self.saved_config = json.load(f)
                # Ensure all keys exist (add missing ones from default_config)
                for key, value in default_config.items():
                    if key not in self.saved_config:
                        self.saved_config[key] = value
        except (FileNotFoundError, json.JSONDecodeError):
            self.saved_config = default_config
            # Write default config on first boot
            try:
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
            except Exception as e:
                print(f"Warning: Could not create config file: {e}")

        # Set quality selection based on saved config
        quality = self.saved_config.get("quality", None)
        if quality == "high":
            self.quality_high_action.setChecked(True)
        elif quality == "medium":
            self.quality_medium_action.setChecked(True)
        elif quality == "low":
            self.quality_low_action.setChecked(True)
        elif quality == "verylow":
            self.quality_verylow_action.setChecked(True)
        # If quality key is missing, defaults to Full (all options unchecked)

        # Restore FPS counter and VSync settings
        self.fps_counter_action.setChecked(self.saved_config.get("show_fps", False))
        self.disable_vsync_action.setChecked(self.saved_config.get("disable_vsync", False))

        # Window size for setup
        window_width = 640
        window_height = 480
        
        # Load custom font
        font_id = QFontDatabase.addApplicationFont("fonts/Frutiger-Black.otf")
        if font_id < 0:
            print("Warning: Could not load Frutiger-Black font, falling back to Arial")
            self.font_family = "Arial"
        else:
            self.font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        
        # Center window
        screen = QApplication.desktop().screenGeometry()
        self.setFixedSize(window_width, window_height)
        self.move((screen.width() - window_width) // 2,
                 (screen.height() - window_height) // 2)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setAlignment(Qt.AlignCenter)

        # Set background
        try:
            bg_image = QPixmap("textures/graphics/background.png")
            bg_image = bg_image.scaled(window_width, window_height,
                                     Qt.IgnoreAspectRatio,
                                     Qt.SmoothTransformation)
            palette = QPalette()
            palette.setBrush(QPalette.Window, QBrush(bg_image))
            self.setPalette(palette)
            self.setAutoFillBackground(True)
        except Exception as e:
            print(f"Could not load background image: {e}")

        # Resolution section
        # Add some top spacing
        layout.addSpacing(100)  # Move everything down

        # Use image for 'Resolutions' label
        res_img = QPixmap("textures/graphics/resolutions.png")
        res_img = res_img.scaledToHeight(60, Qt.SmoothTransformation)
        resolution_label = QLabel()
        resolution_label.setPixmap(res_img)
        resolution_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(resolution_label)

        # Resolution dropdown
        self.resolution_combo = QComboBox()
        self.resolution_combo.setFont(QFont(self.font_family, 20))
        self.resolution_combo.setFixedWidth(180)

        # Add resolution options
        resolution_options = [f"{r['width']}x{r['height']}" for r in self.resolution_config['allowed_resolutions']]
        self.resolution_combo.addItems(resolution_options)
        current_res = f"{self.saved_config.get('last_width')}x{self.saved_config.get('last_height')}"
        if current_res in resolution_options:
            self.resolution_combo.setCurrentText(current_res)
        layout.addWidget(self.resolution_combo, alignment=Qt.AlignCenter)
        layout.addSpacing(5)

        # Use image for 'Zip Code' label
        zip_img = QPixmap("textures/graphics/zipcode.png")
        zip_img = zip_img.scaledToHeight(60, Qt.SmoothTransformation)
        zip_label = QLabel()
        zip_label.setPixmap(zip_img)
        zip_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(zip_label)

        # ZIP input
        self.zip_entry = QLineEdit()
        self.zip_entry.setFont(QFont(self.font_family, 20))
        self.zip_entry.setFixedWidth(100)
        self.zip_entry.setText(self.saved_config.get("last_zip", ""))
        layout.addWidget(self.zip_entry, alignment=Qt.AlignCenter)
        layout.addSpacing(30)

        # Start button (image-based with hover image swap)
        start_button = ImageButton("textures/graphics/start-button.png",
                                   "textures/graphics/start-button-hover.png")
        start_button.set_click_callback(self.start_mini8s)
        layout.addWidget(start_button, alignment=Qt.AlignCenter)

        # Add Mini8s logo
        try:
            logo_size = 225
            logo = QPixmap("textures/graphics/mini8s_verstring-setup.png")
            logo = logo.scaled(logo_size, int(logo_size * 1),
                             Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
            logo_label = QLabel()
            logo_label.setPixmap(logo)
            logo_label.setFixedSize(logo.size())
            logo_label.setStyleSheet("background: transparent;")
            logo_label.move(210, 5)  # Move to top-left
            logo_label.setParent(central_widget)
            
            # Position advanced settings button in top-right
            self.adv_settings_button.setParent(central_widget)
            self.adv_settings_button.move(window_width - 55, 5)  # 10px from top and right
            
            # Add rotation property to button for animation
            self.adv_settings_button.setProperty("rotation", 0)

            # Build date label in bottom-right corner
            build_date_label = QLabel("Build v0.3.99.1 completed on 12/28/2025", central_widget)
            build_date_label.setFont(QFont(self.font_family, 8))
            build_date_label.setStyleSheet("color: rgba(255, 255, 255, 150); background: transparent;")
            build_date_label.adjustSize()
            build_date_label.move(window_width - build_date_label.width() - 10,
                                 window_height - build_date_label.height() - 10)

        except Exception as e:
            print(f"Could not load logo image: {e}")


    def show_adv_menu(self, event):
        # Position the menu to the right of the icon
        pos = self.adv_settings_button.mapToGlobal(QPoint(self.adv_settings_button.width(), 0))
        self.adv_menu.exec_(pos)

    def handle_quality_selection(self, selected_action):
        """Handle quality option selection with ability to uncheck (return to Full)"""
        if selected_action.isChecked():
            # User just checked this option - uncheck all others
            for action in self.quality_action_group.actions():
                if action != selected_action:
                    action.setChecked(False)
        # If unchecked, do nothing - all options unchecked means Full (100%) quality
        # Save settings immediately
        self.save_advanced_settings()

    def save_advanced_settings(self):
        try:
            # Read current config
            try:
                with open("config.json", 'r') as f:
                    config = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                config = {}

            # Update advanced settings
            config["show_fps"] = self.fps_counter_action.isChecked()
            config["disable_vsync"] = self.disable_vsync_action.isChecked()

            # Determine quality setting
            if self.quality_high_action.isChecked():
                config["quality"] = "high"
            elif self.quality_medium_action.isChecked():
                config["quality"] = "medium"
            elif self.quality_low_action.isChecked():
                config["quality"] = "low"
            elif self.quality_verylow_action.isChecked():
                config["quality"] = "verylow"
            else:
                # Remove quality key if set to Full
                config.pop("quality", None)

            # Write config back
            with open("config.json", 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save advanced settings: {e}")

    def start_mini8s(self):
        # Validate inputs
        zip_code = self.zip_entry.text().strip()
        if not (zip_code.isdigit() and len(zip_code) == 5):
            QMessageBox.critical(self, "Invalid ZIP Code", 
                               "Please enter a 5-digit US ZIP code!")
            return

        resolution = self.resolution_combo.currentText()
        width, height = map(int, resolution.split('x'))

        # Quality levels
        if self.quality_high_action.isChecked():
            quality = "high"
            quality_factor = 0.90
        elif self.quality_medium_action.isChecked():
            quality = "medium"
            quality_factor = 0.85
        elif self.quality_low_action.isChecked():
            quality = "low"
            quality_factor = 0.75
        elif self.quality_verylow_action.isChecked():
            quality = "verylow"
            quality_factor = 0.65
        else:
            # Default: Full quality (no reduction selected)
            quality = None
            quality_factor = 1.0

        # Save configuration
        new_config = {
            "last_width": width,
            "last_height": height,
            "last_zip": zip_code,
            "show_fps": self.fps_counter_action.isChecked(),
            "disable_vsync": self.disable_vsync_action.isChecked()
        }

        # Only add quality if it's not full (None means full/default)
        if quality is not None:
            new_config["quality"] = quality

        try:
            with open("config.json", 'w') as f:
                json.dump(new_config, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save config: {e}")

        # Set global variables
        global ZIP_CODE, SCREEN_WIDTH, SCREEN_HEIGHT, SHOW_FPS, VSYNC_ENABLED, QUALITY_FACTOR
        ZIP_CODE = zip_code
        SCREEN_WIDTH = width
        SCREEN_HEIGHT = height
        SHOW_FPS = self.fps_counter_action.isChecked()
        VSYNC_ENABLED = not self.disable_vsync_action.isChecked()  # Inverted because checkbox is "Disable VSync"
        QUALITY_FACTOR = quality_factor

        # Set flag to indicate Start button was pressed
        self.should_start_mini8s = True

        # Close welcome window and quit Qt application
        self.close()
        QApplication.instance().quit()
        


def initialize_mini8s():
    global TARGET_FPS, pre_rendered_conditions_surface, pre_rendered_forecast_surface
    print(f"Mini8s {VERSION} by Starzainia and HexagonMidis!")

    # Load resolution validation file
    try:
        with open('var/resolutions169.json', 'r') as f:
            resolution_config = json.load(f)
            allowed_resolutions = [(r['width'], r['height']) for r in resolution_config['allowed_resolutions']]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load resolutions_16_9.json: {e}")
        print("Resolution validation disabled.")
        allowed_resolutions = None


    config_file = "config.json"
    default_config = {"last_width": 1280, "last_height": 720, "last_zip": ""}
    try:
        with open(config_file, 'r') as f:
            saved_config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        saved_config = default_config

    # Use default or saved values
    SCREEN_WIDTH = saved_config.get("last_width", 1280)
    SCREEN_HEIGHT = saved_config.get("last_height", 720)
    ZIP_CODE = saved_config.get("last_zip", "")

    # Preserve the entire config (including advanced settings like show_fps, disable_vsync, quality)
    # Only update the basic fields that may have changed
    saved_config["last_width"] = SCREEN_WIDTH
    saved_config["last_height"] = SCREEN_HEIGHT
    saved_config["last_zip"] = ZIP_CODE

    try:
        with open(config_file, 'w') as f:
            json.dump(saved_config, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save config: {e}")

    pygame.init()
    pygame.mixer.init()
    font_cache = {}; panel_texture_cache = {}; weather_icon_cache = {}
    gradient_title_cache = {}
    warning_text_cache = {}
    panel_text_cache = {}
    ticker_text_cache = {}
    played_alerts = set()

    screen = pygame.display.set_mode(
        (SCREEN_WIDTH, SCREEN_HEIGHT),
        pygame.HWSURFACE | pygame.DOUBLEBUF,
        vsync=1 if VSYNC_ENABLED else 0
    )
    scale_x, scale_y = calculate_scale_factors(SCREEN_WIDTH, SCREEN_HEIGHT)
    current_motd = get_random_motd(is_tropical=False, is_redmode=False)

    loading_screen_params = {
    "font_cache": font_cache,
    "motd_text": current_motd,
    "motd_y_position": screen.get_height() - scale_value(100, scale_y),
    "scale_x": scale_x,
    "scale_y": scale_y
    }

    draw_loading_screen(screen, "Initializing Mini8s...", **loading_screen_params)
    try:
        program_icon = pygame.image.load('textures/graphics/mini8s_taskbar.png')
        pygame.display.set_icon(program_icon)
    except Exception as e:
        print(f"Cannot load taskbar icon: {e}")

    TICKER_CONFIG = {"font_path": "fonts/Interstate_Light.otf", "font_size": 72, "color": (255, 255, 255), "position_y": SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT + 100, "position_offset": 10, "scroll_threshold": 800, "scroll_speed": 375}
    TITLE_CONFIG = {"font_path": "fonts/Interstate_Bold.otf", "font_size": 64, "color": (255, 50, 50), "position": (20, 10)}
    TKR_WARNING_TITLE_CONFIG = {"font_path": "fonts/Interstate_Bold.otf", "font_size": 32, "color": (255, 255, 255), "position": (15, SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT + 15)}
    CURRENT_CONDITIONS_CONFIG = {"font_path": "fonts/Frutiger-Black.otf", "title_font_size": 40, "condition_desc_font_size": 40, "condition_desc_x_offset": -2, "data_font_size": 28, "list_font_size": 28, "color": (255, 255, 255), "title_color": (220, 220, 50), "position": (10, 120), "line_height": 40, "background_color": (0, 0, 0, 180), "width": 550, "padding": 20, "max_height": 770}
    PANEL_TEXTURE_PATH = "textures/graphics/paneaero.png"
    WATCH_BAR_TEXTURE_PATH = "textures/graphics/watch_LDL.png"
    STATEMENT_BAR_TEXTURE_PATH = "textures/graphics/statement-advisory_LDL.png"
    ALERT_BAR_TEXTURE_PATH = "textures/graphics/warning_LDL.png"
    LOGO_CONFIG = {"path": "textures/graphics/mini8s_logo.png", "width": 200, "margin_right": 10, "margin_top": 10}

    # Universal scaling: base offset defined for 1920x1080, automatically scales to all resolutions
    BASE_WARNING_Y_OFFSET = 8  # Base vertical offset from LDL bar (reference: 1920x1080)
    BASE_WARNING_X_OFFSET = 15  # Base horizontal offset (reference: 1920x1080)

    scaled_bottom_bar_height = scale_value(BOTTOM_BAR_HEIGHT, scale_y)
    scaled_config = {
    "scale_x": scale_x,
    "scale_y": scale_y,
    "TITLE_CONFIG": {
        "font_path": TITLE_CONFIG["font_path"],
        "font_size": scale_font_size(TITLE_CONFIG["font_size"], scale_y),
        "color": TITLE_CONFIG["color"],
        "position": scale_pos(TITLE_CONFIG["position"], scale_x, scale_y)
    },
    "TKR_WARNING_TITLE_CONFIG": {
        "font_path": TKR_WARNING_TITLE_CONFIG["font_path"],
        "font_size": scale_font_size(TKR_WARNING_TITLE_CONFIG["font_size"], scale_y),
        "color": TKR_WARNING_TITLE_CONFIG["color"],
        "position": (scale_value(BASE_WARNING_X_OFFSET, scale_x), SCREEN_HEIGHT - scaled_bottom_bar_height + scale_value(BASE_WARNING_Y_OFFSET, scale_y))
    },
    "TICKER_CONFIG": {
        "font_path": TICKER_CONFIG["font_path"],
        "font_size": scale_font_size(TICKER_CONFIG["font_size"], scale_y),
        "color": TICKER_CONFIG["color"],
        # Base position: top of bottom bar + base offset (50). Add `position_offset` for fine tuning (positive moves down).
        "position_y": SCREEN_HEIGHT - scaled_bottom_bar_height + scale_value(50 + TICKER_CONFIG.get("position_offset", 0), scale_y),
        "scroll_threshold": scale_value(TICKER_CONFIG["scroll_threshold"], scale_x),
        "scroll_speed": scale_value(TICKER_CONFIG["scroll_speed"], scale_x)
    },
    "CURRENT_CONDITIONS_CONFIG": {
        "font_path": CURRENT_CONDITIONS_CONFIG["font_path"],
        "title_font_size": scale_font_size(CURRENT_CONDITIONS_CONFIG["title_font_size"], scale_y),
        "condition_desc_font_size": scale_font_size(CURRENT_CONDITIONS_CONFIG["condition_desc_font_size"], scale_y),
        "condition_desc_x_offset": scale_value(CURRENT_CONDITIONS_CONFIG["condition_desc_x_offset"], scale_x),
        "data_font_size": scale_font_size(CURRENT_CONDITIONS_CONFIG["data_font_size"], scale_y),
        "list_font_size": scale_font_size(CURRENT_CONDITIONS_CONFIG["list_font_size"], scale_y),
        "color": CURRENT_CONDITIONS_CONFIG["color"],
        "title_color": CURRENT_CONDITIONS_CONFIG["title_color"],
        "position": scale_pos(CURRENT_CONDITIONS_CONFIG["position"], scale_x, scale_y),
        "line_height": scale_value(CURRENT_CONDITIONS_CONFIG["line_height"], scale_y),
        "background_color": CURRENT_CONDITIONS_CONFIG["background_color"],
        "width": scale_value(CURRENT_CONDITIONS_CONFIG["width"], scale_x),
        "padding": scale_value(CURRENT_CONDITIONS_CONFIG["padding"], scale_x),
        "max_height": scale_value(CURRENT_CONDITIONS_CONFIG["max_height"], scale_y)
    },
    "LOGO_CONFIG": {
        "path": LOGO_CONFIG["path"],
        "width": scale_value(LOGO_CONFIG["width"], scale_x),
        "margin_right": scale_value(LOGO_CONFIG["margin_right"], scale_x),
        "margin_top": scale_value(LOGO_CONFIG["margin_top"], scale_y)
    }
}

    if SCREEN_WIDTH > 1920:
        config_to_edit = scaled_config["CURRENT_CONDITIONS_CONFIG"]
        config_to_edit["title_font_size"] = int(config_to_edit["title_font_size"] * 0.9)
        config_to_edit["data_font_size"] = int(config_to_edit["data_font_size"] * 0.9)
        config_to_edit["list_font_size"] = int(config_to_edit["list_font_size"] * 0.9)

    elif SCREEN_WIDTH < 1280:
        config_to_edit = scaled_config["CURRENT_CONDITIONS_CONFIG"]

        config_to_edit["title_font_size"] = int(config_to_edit["title_font_size"] * 0.9)
        config_to_edit["data_font_size"] = int(config_to_edit["data_font_size"] * 0.85)
        config_to_edit["list_font_size"] = int(config_to_edit["list_font_size"] * 0.9)
        config_to_edit["line_height"] = int(config_to_edit["line_height"] * 0.9)
        config_to_edit["padding"] = int(config_to_edit["padding"] * 0.7)

    pygame.display.set_caption(f"Mini8s {VERSION} for {ZIP_CODE}")
    clock = pygame.time.Clock()
    draw_loading_screen(screen, "Grabbing Weather Data...", **loading_screen_params)

    title_text = DEFAULT_TITLE_TEXT; warning_text = WARNING_TEXT

    display_mode = "STABLE_CONDITIONS"
    last_panel_switch_time = pygame.time.get_ticks()
    transition_sub_step_idx = 0
    last_flip_sub_step_time = 0
    current_bar_texture = None
    current_alert_level = None

    try:
        if QUALITY_FACTOR < 1.0:
            intermediate_w = int(SCREEN_WIDTH * QUALITY_FACTOR)
            intermediate_h = int(scaled_bottom_bar_height * QUALITY_FACTOR)

            temp_watch = pygame.transform.smoothscale(pygame.image.load(WATCH_BAR_TEXTURE_PATH).convert_alpha(), (intermediate_w, intermediate_h))
            watch_bar_texture = pygame.transform.smoothscale(temp_watch, (SCREEN_WIDTH, scaled_bottom_bar_height))

            temp_statement = pygame.transform.smoothscale(pygame.image.load(STATEMENT_BAR_TEXTURE_PATH).convert_alpha(), (intermediate_w, intermediate_h))
            statement_bar_texture = pygame.transform.smoothscale(temp_statement, (SCREEN_WIDTH, scaled_bottom_bar_height))

            temp_alert = pygame.transform.smoothscale(pygame.image.load(ALERT_BAR_TEXTURE_PATH).convert_alpha(), (intermediate_w, intermediate_h))
            alert_bar_texture = pygame.transform.smoothscale(temp_alert, (SCREEN_WIDTH, scaled_bottom_bar_height))
        else:
            watch_bar_texture = pygame.transform.smoothscale(pygame.image.load(WATCH_BAR_TEXTURE_PATH).convert_alpha(), (SCREEN_WIDTH, scaled_bottom_bar_height))
            statement_bar_texture = pygame.transform.smoothscale(pygame.image.load(STATEMENT_BAR_TEXTURE_PATH).convert_alpha(), (SCREEN_WIDTH, scaled_bottom_bar_height))
            alert_bar_texture = pygame.transform.smoothscale(pygame.image.load(ALERT_BAR_TEXTURE_PATH).convert_alpha(), (SCREEN_WIDTH, scaled_bottom_bar_height))
    except Exception as e: print(f"Bar texture error: {e}"); pygame.quit(); sys.exit()

    alert_list = []
    current_alert_index = 0
    ticker_scroll_count = 0
    single_alert_mode = False

    is_redmode = False
    logo_path = "textures/graphics/mini8s_logo.png"
    try:
        logo_orig = pygame.image.load(logo_path).convert_alpha()
        logo_w, logo_h = scaled_config["LOGO_CONFIG"]["width"], int(scaled_config["LOGO_CONFIG"]["width"] * (logo_orig.get_height() / logo_orig.get_width()))
        if QUALITY_FACTOR < 1.0:
            intermediate_w = int(logo_w * QUALITY_FACTOR)
            intermediate_h = int(logo_h * QUALITY_FACTOR)
            temp_logo = pygame.transform.smoothscale(logo_orig, (intermediate_w, intermediate_h))
            mini8s_logo = pygame.transform.smoothscale(temp_logo, (logo_w, logo_h))
        else:
            mini8s_logo = pygame.transform.smoothscale(logo_orig, (logo_w, logo_h))
        logo_rect = mini8s_logo.get_rect(topright=(SCREEN_WIDTH - scaled_config["LOGO_CONFIG"]["margin_right"], scaled_config["LOGO_CONFIG"]["margin_top"]))
    except Exception as e:
        print(f"Logo error: {e}")
    try:
        title_4hr_normal_orig = pygame.image.load("textures/graphics/4hrradar.png").convert_alpha()
        title_4hr_tropical_orig = pygame.image.load("textures/graphics/4hrradarsatellite.png").convert_alpha()
        title_4hr_redmode_orig = pygame.image.load("textures/graphics/4hrradar-redmode.png").convert_alpha()
        target_font_size = scaled_config["TITLE_CONFIG"]["font_size"]

        target_height = int(target_font_size * 1.2)

        normal_aspect = title_4hr_normal_orig.get_width() / title_4hr_normal_orig.get_height()
        tropical_aspect = title_4hr_tropical_orig.get_width() / title_4hr_tropical_orig.get_height()
        redmode_aspect = title_4hr_redmode_orig.get_width() / title_4hr_redmode_orig.get_height()
        normal_width = int(target_height * normal_aspect)
        tropical_width = int(target_height * tropical_aspect)
        redmode_width = int(target_height * redmode_aspect)

        # Apply user-selected quality reduction
        if QUALITY_FACTOR < 1.0:
            intermediate_normal_width = int(normal_width * QUALITY_FACTOR)
            intermediate_normal_height = int(target_height * QUALITY_FACTOR)
            intermediate_tropical_width = int(tropical_width * QUALITY_FACTOR)
            intermediate_tropical_height = int(target_height * QUALITY_FACTOR)
            intermediate_redmode_width = int(redmode_width * QUALITY_FACTOR)
            intermediate_redmode_height = int(target_height * QUALITY_FACTOR)

            title_4hr_normal_temp = pygame.transform.smoothscale(title_4hr_normal_orig, (intermediate_normal_width, intermediate_normal_height))
            title_4hr_normal = pygame.transform.smoothscale(title_4hr_normal_temp, (normal_width, target_height))

            title_4hr_tropical_temp = pygame.transform.smoothscale(title_4hr_tropical_orig, (intermediate_tropical_width, intermediate_tropical_height))
            title_4hr_tropical = pygame.transform.smoothscale(title_4hr_tropical_temp, (tropical_width, target_height))

            title_4hr_redmode_temp = pygame.transform.smoothscale(title_4hr_redmode_orig, (intermediate_redmode_width, intermediate_redmode_height))
            title_4hr_redmode = pygame.transform.smoothscale(title_4hr_redmode_temp, (redmode_width, target_height))
        else:
            # Full quality
            title_4hr_normal = pygame.transform.smoothscale(title_4hr_normal_orig, (normal_width, target_height))
            title_4hr_tropical = pygame.transform.smoothscale(title_4hr_tropical_orig, (tropical_width, target_height))
            title_4hr_redmode = pygame.transform.smoothscale(title_4hr_redmode_orig, (redmode_width, target_height))
    except Exception as e:
        print(f"Error loading title images: {e}")
        # Fallback to None if images not found
        title_4hr_normal = None
        title_4hr_tropical = None
        title_4hr_redmode = None
        pygame.quit()
        sys.exit()



    time_char_cache = {}
    time_font_size = scale_font_size(28, scale_y)
    try:
        time_font = pygame.font.Font(scaled_config["TITLE_CONFIG"]["font_path"], time_font_size)
        for char in "0123456789: AMP":
            time_char_cache[char] = time_font.render(char, True, (255,255,255))
    except Exception as e:
        print(f"Could not load font for time cache, will fall back to slower rendering: {e}")
        time_char_cache = None

    ticker_font_key = (scaled_config["TICKER_CONFIG"]["font_path"], scaled_config["TICKER_CONFIG"]["font_size"])
    if ticker_font_key not in font_cache:
        try: font_cache[ticker_font_key] = pygame.font.Font(ticker_font_key[0], ticker_font_key[1])
        except: font_cache[ticker_font_key] = pygame.font.SysFont(None, ticker_font_key[1])
    ticker_font = font_cache[ticker_font_key]

    # Cache FPS font to avoid loading from disk every frame
    fps_font_size = int(32 * (SCREEN_WIDTH / 1280))
    fps_font_key = ("default_fps_font", fps_font_size)
    if fps_font_key not in font_cache:
        font_cache[fps_font_key] = pygame.font.SysFont(None, fps_font_size, bold=True)
    fps_font = font_cache[fps_font_key]

# Anti-freezing worker thread.. This is part of the logic that stops the loading screen from looking frozen
    init_queue = queue.Queue(maxsize=1)
    progress_queue = queue.Queue()  # For stage progress updates
    init_stop_event = threading.Event()
    init_worker = InitializationWorker(ZIP_CODE, init_queue, progress_queue, init_stop_event)
    init_worker.start()
    
    # Initialize variables with defaults
    lat, lon, state, location_name = None, None, None, None
    forecast_url, current_conditions_data, forecast_periods_data = None, None, None
    alert_list, alert_type_val, is_tropical = [], None, False
    is_redmode = False
    warning_text = " "
    ticker_surface = None
    current_bar_texture = None
    current_alert_level = None
    pre_rendered_conditions_surface = None
    pre_rendered_forecast_surface = None
    radar_data_tuple = None
    init_data_received = False
    current_motd = get_random_motd(is_tropical=False, is_redmode=False)
    
    # Wait for initialization data while keeping the screen responsive
    loading_message = "Grabbing Weather Data..."

    while not init_data_received:
        # Check for progress updates on during loading
        try:
            progress = progress_queue.get_nowait()
            if progress.get('stage') == 'loading_radar':
                loading_message = "Loading Radar Data..."
        except queue.Empty:
            pass
        
        # Process pygame events to keep window responsive
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                init_stop_event.set()
                pygame.quit()
                sys.exit()
        
        # Try to get data from the worker thread (non-blocking)
        try:
            init_data = init_queue.get_nowait()
            init_data_received = True
            
            if init_data['status'] == 'error':
                error_msg = init_data['error']
                log_fatal_error(error_msg)
                fetch_radar_image.last_error = error_msg
                break
            
            # Unpack the data
            lat = init_data['lat']
            lon = init_data['lon']
            state = init_data['state']
            location_name = init_data['location_name']
            forecast_url = init_data['forecast_url']
            current_conditions_data = init_data['current_conditions']
            forecast_text_val = init_data['forecast_text']
            forecast_periods_data = init_data['forecast_periods']
            alert_list = init_data['alert_list']
            alert_type_val = init_data['alert_type']
            is_tropical = init_data['is_tropical']
            is_redmode = init_data['is_redmode']
            radar_data_tuple = init_data['radar_data']
            
            # Update MOTD based on alert type
            if is_redmode:
                if alert_type_val and ("HURRICANE" in alert_type_val.upper()):
                    current_motd = get_random_motd(is_tropical=is_tropical, is_redmode=True)
                    print("⚠️ REDMODE ACTIVATED ⚠️ A hurricane is at or approaching your area!")
                elif alert_type_val and ("TORNADO" in alert_type_val.upper()):
                    current_motd = get_random_motd(is_tropical=False, is_redmode=True)
                    print("⚠️ REDMODE ACTIVATED ⚠️ Tornado Watch or Warning in effect!")
            elif is_tropical:
                current_motd = get_random_motd(is_tropical=is_tropical, is_redmode=False)
                print(f"Looks like you might have a tropical system headed your way, stay safe!")
            
            # Handle redmode logo
            if is_redmode:
                try:
                    redmode_logo_path = "textures/graphics/mini8s-redmode_logo.png"
                    logo_orig = pygame.image.load(redmode_logo_path).convert_alpha()
                    logo_w, logo_h = scaled_config["LOGO_CONFIG"]["width"], int(scaled_config["LOGO_CONFIG"]["width"] * (logo_orig.get_height() / logo_orig.get_width()))
                    mini8s_logo = pygame.transform.smoothscale(logo_orig, (logo_w, logo_h))
                    logo_rect = mini8s_logo.get_rect(topright=(SCREEN_WIDTH - scaled_config["LOGO_CONFIG"]["margin_right"], scaled_config["LOGO_CONFIG"]["margin_top"]))
                except Exception as e:
                    print(f"Error loading redmode logo: {e}")
            
            # Process alerts and setup ticker
            if alert_list:
                single_alert_mode = (len(alert_list) == 1)
                current_alert_index = 0
                ticker_scroll_count = 0
                current_alert = alert_list[current_alert_index]
                
                warning_text = current_alert['event_upper']
                ticker_text_content = current_alert['ticker_text']
                
                if current_alert['alert_level'] == "ALERT":
                    current_bar_texture, current_alert_level = alert_bar_texture, "ALERT"
                elif current_alert['alert_level'] == "WATCH":
                    current_bar_texture, current_alert_level = watch_bar_texture, "WATCH"
                else:
                    current_bar_texture, current_alert_level = statement_bar_texture, "STATEMENT"
                
                outline_width_px = max(1, scale_value(3, scaled_config["scale_y"]))

                # Use freetype font to measure the actual text width (excludes surface padding)
                ft_font_key = (scaled_config["TICKER_CONFIG"]["font_path"], scaled_config["TICKER_CONFIG"]["font_size"], False)
                if ft_font_key not in _font_cache:
                    try:
                        _font_cache[ft_font_key] = pygame.freetype.Font(ft_font_key[0], ft_font_key[1])
                    except Exception:
                        _font_cache[ft_font_key] = pygame.freetype.SysFont(None, ft_font_key[1])
                ft_font = _font_cache[ft_font_key]
                text_rect_ft = ft_font.get_rect(ticker_text_content)
                text_actual_width = text_rect_ft.width

                ticker_surface = get_cached_warning_surface(
                    ticker_text_content,
                    scaled_config["TICKER_CONFIG"]["font_path"],
                    scaled_config["TICKER_CONFIG"]["font_size"],
                    scaled_config["TICKER_CONFIG"]["color"],
                    (0, 0, 0),
                    outline_width_px,
                    False,
                    ticker_text_cache
                )
                ticker_width = ticker_surface.get_width()
                should_scroll = text_actual_width > scaled_config["TICKER_CONFIG"]["scroll_threshold"]
                ticker_x = SCREEN_WIDTH if should_scroll else (SCREEN_WIDTH - ticker_width) // 2
                ticker_start_time = pygame.time.get_ticks()
                
                # Store alert to be played after loading finishes
                global pending_alert_for_audio
                pending_alert_for_audio = warning_text
            
            # Create pre-rendered surfaces if data is available
            if current_conditions_data:
                pre_rendered_conditions_surface = create_current_conditions_surface(current_conditions_data, location_name, scaled_config, panel_texture_cache, weather_icon_cache, font_cache, primary_alert_type=alert_type_val)
            if forecast_periods_data:
                pre_rendered_forecast_surface = create_forecast_panel_surface(forecast_periods_data, scaled_config, SCREEN_WIDTH, panel_texture_cache, weather_icon_cache, font_cache)
            
            break
            
        except queue.Empty:
            
            draw_loading_screen(screen, loading_message, **loading_screen_params)
            pygame.time.wait(100)  # Small delay to avoid 100% CPU usage

    if not init_data_received or not radar_data_tuple:
        error_msg = "Failed to load initialization data or radar images"
        print(error_msg)
        log_fatal_error(error_msg)
        if hasattr(fetch_radar_image, 'last_error'):
            fetch_radar_image.last_error
        draw_loading_screen(screen, "Loading Radar Data...", **loading_screen_params)
        pygame.time.wait(3000)
        pygame.quit()
        sys.exit()
    
    current_radar_frame_idx, last_radar_update_time = 0, pygame.time.get_ticks()
    # This value controls the speed of the radar loop!
    SPEED_FACTOR = 18

    radar_gif_list = []
    if radar_data_tuple:
        if isinstance(radar_data_tuple, list):
            radar_gif_list = radar_data_tuple
        elif isinstance(radar_data_tuple, tuple) and len(radar_data_tuple) == 2:
            radar_gif_list = [(radar_data_tuple[0], radar_data_tuple[1], 0)]

    radar_gif_frames = []
    radar_gif_durations = []
    for frames, durations, _ in radar_gif_list:
        radar_gif_frames.append(frames)
        radar_gif_durations.append(durations)
    num_gifs = len(radar_gif_frames)
    current_gif_idx = 0
    current_gif_frame_idx = 0
    last_gif_frame_time = pygame.time.get_ticks()
    gif_play_count = 0
    fade_state = "normal"
    fade_start_time = 0
    fade_duration = 1000
    next_gif_idx = 0

    # For compatibility with create_all_pre_rendered_frames, set radar_frames_raw to the first GIF's frames (or empty)
    radar_frames_raw = radar_gif_frames[0][:] if radar_gif_frames and radar_gif_frames[0] else []
    draw_loading_screen(screen, "Pre-Rendering...", **loading_screen_params)
    create_all_pre_rendered_frames(
        radar_frames_raw, pre_rendered_conditions_surface, pre_rendered_forecast_surface,
        title_text, mini8s_logo, logo_rect, current_bar_texture, warning_text,
        scaled_config, font_cache, PANEL_FLIP_ANIMATION_STEPS
    )
    
    # Play pending alert audio now that pre-rendering is complete
    if pending_alert_for_audio:
        play_ticker_audio(pending_alert_for_audio, is_new_alert=True, radar_loaded=True)
        pending_alert_for_audio = None
    panel_original_width_for_centering = scaled_config["CURRENT_CONDITIONS_CONFIG"]["width"]
    panel_render_pos_tuple = scaled_config["CURRENT_CONDITIONS_CONFIG"]["position"]

    display_mode = "STABLE_CONDITIONS"
    last_panel_switch_time = pygame.time.get_ticks()
    is_transitioning = False
    panel_to_blit_during_flip = None

    weather_queue = queue.Queue(maxsize=2)
    stop_event = threading.Event()
    weather_worker = WeatherDataWorker(ZIP_CODE, weather_queue, stop_event)
    
    # 5 Minutes.
    def start_weather_worker():
        weather_worker.start()
        print("Background weather worker thread started")
    
    weather_timer = threading.Timer(300.0, start_weather_worker)  # 300 seconds = 5 minutes
    weather_timer.start()

    if 'ticker_surface' not in locals():
        ticker_surface = None
        should_scroll = False
    running = True
    show_fps = SHOW_FPS
    is_transitioning = False
    panel_to_blit_during_flip = None

    while running:
        panel_render_pos_tuple = scaled_config["CURRENT_CONDITIONS_CONFIG"]["position"]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        current_ticks_ms = pygame.time.get_ticks()

        if not is_transitioning and current_ticks_ms - last_panel_switch_time >= PANEL_CYCLE_INTERVAL:
            is_transitioning = True
            transition_sub_step_idx = 0
            last_flip_sub_step_time = current_ticks_ms
            if display_mode == "STABLE_CONDITIONS":
                flip_anim_shrink = panel_shrink_cond_surfaces
                flip_anim_expand = panel_expand_fcst_surfaces
                display_mode_next = "FORECAST"
            else:
                flip_anim_shrink = panel_shrink_fcst_surfaces
                flip_anim_expand = panel_expand_cond_surfaces
                display_mode_next = "STABLE_CONDITIONS"
            panel_to_blit_during_flip = flip_anim_shrink[0]
            flip_anim_display_mode_next = display_mode_next

        if is_transitioning:
            now = pygame.time.get_ticks()
            if transition_sub_step_idx < PANEL_FLIP_ANIMATION_STEPS:
                if now - last_flip_sub_step_time > FLIP_SUB_STEP_DURATION_MS:

                    if flip_anim_shrink and transition_sub_step_idx < len(flip_anim_shrink):
                        panel_to_blit_during_flip = flip_anim_shrink[transition_sub_step_idx]
                    elif flip_anim_shrink:
                        panel_to_blit_during_flip = flip_anim_shrink[-1]
                    else:
                        # No animation frames available, skip transition
                        is_transitioning = False
                        display_mode = flip_anim_display_mode_next
                        panel_to_blit_during_flip = None
                        last_panel_switch_time = now
                        continue
                    transition_sub_step_idx += 1
                    last_flip_sub_step_time = now
            elif transition_sub_step_idx < 2 * PANEL_FLIP_ANIMATION_STEPS:
                if now - last_flip_sub_step_time > FLIP_SUB_STEP_DURATION_MS:
                    # Expand phase
                    expand_idx = transition_sub_step_idx - PANEL_FLIP_ANIMATION_STEPS
                    if flip_anim_expand and expand_idx < len(flip_anim_expand):
                        panel_to_blit_during_flip = flip_anim_expand[expand_idx]
                    elif flip_anim_expand:
                        panel_to_blit_during_flip = flip_anim_expand[-1]
                    else:
                        # No animation frames available, skip transition
                        is_transitioning = False
                        display_mode = flip_anim_display_mode_next
                        panel_to_blit_during_flip = None
                        last_panel_switch_time = now
                        continue
                    transition_sub_step_idx += 1
                    last_flip_sub_step_time = now
            else:
                is_transitioning = False
                display_mode = flip_anim_display_mode_next
                panel_to_blit_during_flip = None
                last_panel_switch_time = now
        try:
            weather_data = weather_queue.get_nowait()
            print("Main thread: Received weather data update from background thread")

            if weather_data.get('lat') and weather_data.get('lon'):
                title_text = f"4 Hour Radar"
                location_name = weather_data.get('location_name', 'Unknown Location')

                current_conditions_data = weather_data.get('current_conditions')
                alert_type_val = weather_data.get('alert_type')
                if current_conditions_data:
                    pre_rendered_conditions_surface = create_current_conditions_surface(
                        current_conditions_data, location_name, scaled_config,
                        panel_texture_cache, weather_icon_cache, font_cache,
                        primary_alert_type=alert_type_val
                    )

                alert_list = weather_data.get('alert_list', [])
                warning_text_cache.clear()
                # Only clear title cache if we're implementing the tropical change
                if is_tropical != weather_data.get('is_tropical', False):
                    gradient_title_cache.clear()

                current_bar_texture = None
                current_alert_level = None

                if alert_list:
                    single_alert_mode = (len(alert_list) == 1)
                    current_alert_index = 0
                    ticker_scroll_count = 0
                    current_alert = alert_list[current_alert_index]

                    warning_text = current_alert['event_upper']
                    ticker_text_content = current_alert['ticker_text']

                    if current_alert['alert_level'] == "ALERT":
                        current_bar_texture, current_alert_level = alert_bar_texture, "ALERT"
                    elif current_alert['alert_level'] == "WATCH":
                        current_bar_texture, current_alert_level = watch_bar_texture, "WATCH"
                    else:  # STATEMENT or ADVISORY
                        current_bar_texture, current_alert_level = statement_bar_texture, "STATEMENT"

                    outline_width_px = max(1, scale_value(3, scaled_config["scale_y"]))
                    ft_font_key = (scaled_config["TICKER_CONFIG"]["font_path"], scaled_config["TICKER_CONFIG"]["font_size"], False)
                    if ft_font_key not in _font_cache:
                        try:
                            _font_cache[ft_font_key] = pygame.freetype.Font(ft_font_key[0], ft_font_key[1])
                        except Exception:
                            _font_cache[ft_font_key] = pygame.freetype.SysFont(None, ft_font_key[1])
                    ft_font = _font_cache[ft_font_key]
                    text_rect_ft = ft_font.get_rect(ticker_text_content)
                    text_actual_width = text_rect_ft.width

                    ticker_surface = get_cached_warning_surface(
                        ticker_text_content,
                        scaled_config["TICKER_CONFIG"]["font_path"],
                        scaled_config["TICKER_CONFIG"]["font_size"],
                        scaled_config["TICKER_CONFIG"]["color"],
                        (0, 0, 0),
                        outline_width_px,
                        False,
                        ticker_text_cache
                    )
                    ticker_width = ticker_surface.get_width()
                    should_scroll = text_actual_width > scaled_config["TICKER_CONFIG"]["scroll_threshold"]
                    ticker_x = SCREEN_WIDTH if should_scroll else (SCREEN_WIDTH - ticker_width) // 2
                    ticker_start_time = pygame.time.get_ticks()
                    
                else:
                    warning_text = " "
                    ticker_surface = None
                    current_bar_texture = None
                    current_alert_level = None

                forecast_periods_data = weather_data.get('forecast_periods')
                if forecast_periods_data:
                    pre_rendered_forecast_surface = create_forecast_panel_surface(
                        forecast_periods_data, scaled_config, SCREEN_WIDTH, panel_texture_cache,
                        weather_icon_cache, font_cache
                    )

                radar_data_tuple = weather_data.get('radar_data')
                radar_gif_list = []
                radar_gif_frames = []
                radar_gif_durations = []
                if radar_data_tuple:
                    if isinstance(radar_data_tuple, list):
                        radar_gif_list = radar_data_tuple
                    elif isinstance(radar_data_tuple, tuple) and len(radar_data_tuple) == 2:
                        radar_gif_list = [(radar_data_tuple[0], radar_data_tuple[1], 0)]
                    for frames, durations, _ in radar_gif_list:
                        radar_gif_frames.append(frames)
                        radar_gif_durations.append(durations)
                num_gifs = len(radar_gif_frames)
                current_gif_idx = 0
                gif_switch_time = pygame.time.get_ticks()
                current_gif_frame_idx = 0
                last_gif_frame_time = pygame.time.get_ticks()
                # Reset fade transition variables when weather data updates
                fade_state = "normal"
                fade_start_time = 0
                next_gif_idx = 0
                gif_play_count = 0
                radar_frames_raw = radar_gif_frames[0][:] if radar_gif_frames and radar_gif_frames[0] else []
                create_all_pre_rendered_frames(
                    radar_frames_raw, pre_rendered_conditions_surface, pre_rendered_forecast_surface,
                    title_text, mini8s_logo, logo_rect, current_bar_texture, warning_text,
                    scaled_config, font_cache, PANEL_FLIP_ANIMATION_STEPS
                )
                
                if pending_alert_for_audio:
                    play_ticker_audio(pending_alert_for_audio, is_new_alert=True, radar_loaded=True)
                    pending_alert_for_audio = None

                print("Main thread: Weather data update processed successfully")
            else:
                title_text = "Oh great, where did we end up now?"

        except queue.Empty:
            pass

        if num_gifs > 0:
            if num_gifs > 1:
                frames = radar_gif_frames[current_gif_idx]
                durations = radar_gif_durations[current_gif_idx]
            else:
                frames = radar_gif_frames[0]
                durations = radar_gif_durations[0]

            if frames and durations:
                last_frame_idx = len(frames) - 1
                if current_gif_frame_idx >= len(frames):
                    current_gif_frame_idx = 0
                # If we're on the last frame, use the real duration + 2000ms pause
                if current_gif_frame_idx == last_frame_idx:
                    frame_duration = max(50, durations[current_gif_frame_idx] // SPEED_FACTOR) + 1500
                else:
                    frame_duration = max(50, durations[current_gif_frame_idx] // SPEED_FACTOR)
                if current_ticks_ms - last_gif_frame_time >= frame_duration:
                    # If we are about to loop from last frame to first, increment play count
                    if current_gif_frame_idx == last_frame_idx:
                        gif_play_count += 1
                        if num_gifs > 1 and gif_play_count >= 8:
                            # Start fade-out transition if in tropical mode
                            if is_tropical and num_gifs > 1:
                                next_gif_idx = (current_gif_idx + 1) % num_gifs
                                fade_state = "fading_out"
                                fade_start_time = current_ticks_ms
                                gif_play_count = 0
                            else:
                                # Immediate switch for non-tropical mode
                                current_gif_idx = (current_gif_idx + 1) % num_gifs
                                current_gif_frame_idx = 0
                                gif_play_count = 0
                                last_gif_frame_time = current_ticks_ms
                                frames = radar_gif_frames[current_gif_idx]
                                durations = radar_gif_durations[current_gif_idx]
                                last_frame_idx = len(frames) - 1
                                active_radar_frame = frames[0]
                                # Skip the rest of the logic for this frame
                                continue
                    current_gif_frame_idx = (current_gif_frame_idx + 1) % len(frames)
                    last_gif_frame_time = current_ticks_ms
                # Only set active_radar_frame if not in a fade transition
                if not (is_tropical and num_gifs > 1 and fade_state in ["fading_out", "fading_in"]):
                    active_radar_frame = frames[current_gif_frame_idx]
                else:
                    current_frame = frames[current_gif_frame_idx]
                    if fade_state != "fading_out":
                        active_radar_frame = current_frame
            else:
                active_radar_frame = None
        else:
            active_radar_frame = None

        # Title fading for the 4hrradar stuffs.
        current_fade_alpha = 255
        globals()['current_fade_alpha'] = current_fade_alpha
        
        if is_tropical and num_gifs > 1:
            if fade_state == "fading_out":
                fade_elapsed = current_ticks_ms - fade_start_time
                if fade_elapsed >= fade_duration:
                    current_gif_idx = next_gif_idx
                    current_gif_frame_idx = 0
                    last_gif_frame_time = current_ticks_ms
                    frames = radar_gif_frames[current_gif_idx]
                    durations = radar_gif_durations[current_gif_idx]
                    active_radar_frame = frames[0]
                    fade_state = "fading_in"
                    fade_start_time = current_ticks_ms
                    current_fade_alpha = 0
                else:
                    # Calculate title fade-out alpha
                    fade_progress = fade_elapsed / fade_duration
                    current_fade_alpha = int(255 * (1.0 - fade_progress))
                    current_fade_alpha = max(0, current_fade_alpha)
                    globals()['current_fade_alpha'] = current_fade_alpha
            elif fade_state == "fading_in":
                fade_elapsed = current_ticks_ms - fade_start_time
                if fade_elapsed >= fade_duration:
                    # Then, go to normal
                    fade_state = "normal"
                    current_fade_alpha = 255
                    globals()['current_fade_alpha'] = current_fade_alpha
                else:
                    fade_progress = fade_elapsed / fade_duration
                    current_fade_alpha = int(255 * fade_progress)
                    current_fade_alpha = min(255, current_fade_alpha)
                    globals()['current_fade_alpha'] = current_fade_alpha
            
        if active_radar_frame:
            # Calculate radar offset with automatic scaling
            base_offset = -75
            base_height = 720

            # Different scaling for at or below 720p
            if SCREEN_HEIGHT >= 720:
                multiplier = 1.0 + ((SCREEN_HEIGHT - 720) * 0.3 / 360)
            else:
                multiplier = 1.0 - ((720 - SCREEN_HEIGHT) * 0.3 / 360)
            radar_offset_y = int(base_offset * (SCREEN_HEIGHT / base_height) * multiplier) # Scaled offset
            screen.blit(active_radar_frame, (0, radar_offset_y))

            # THE LOCAITON DOT.
            try:
                if 'location_dot_original' not in globals():
                    global location_dot_original
                    location_dot_img = pygame.image.load("textures/icons/zip-location.png").convert_alpha()
                    # Scale the location dot to be appropriately sized
                    dot_size = int(32 * scaled_config["scale_y"])  # Scale with screen resolution
                    location_dot_original = pygame.transform.smoothscale(location_dot_img, (dot_size, dot_size))

                current_time = pygame.time.get_ticks()
                pulse_speed = 0.004  # Controls how fast the pulse is (lower = slower)
                min_alpha = 128
                max_alpha = 255
                # Keep the dot fully opaque when the user selected the very low quality preset
                if saved_config.get("quality") == "verylow":
                    alpha = max_alpha
                else:
                    alpha = min_alpha + (max_alpha - min_alpha) * (math.sin(current_time * pulse_speed) + 1) / 2

                # Create a copy of the original dot and set its alpha
                pulsing_dot = location_dot_original.copy()
                pulsing_dot.set_alpha(int(alpha))
                dot_x = SCREEN_WIDTH // 2 - pulsing_dot.get_width() // 2

                # This fucking dot.
                if SCREEN_WIDTH == 896 and SCREEN_HEIGHT == 504:
                    dot_y = (SCREEN_HEIGHT // 2) + (radar_offset_y // 3) - pulsing_dot.get_height() // 2
                elif SCREEN_WIDTH == 1024 and SCREEN_HEIGHT == 600:
                    dot_y = (SCREEN_HEIGHT // 2) + (radar_offset_y // 2.5) - pulsing_dot.get_height() // 2
                elif SCREEN_WIDTH == 960 and SCREEN_HEIGHT == 540:
                    dot_y = (SCREEN_HEIGHT // 2) + (radar_offset_y // 4.75) - pulsing_dot.get_height() // 2
                elif SCREEN_WIDTH == 1024 and SCREEN_HEIGHT == 576:
                    dot_y = (SCREEN_HEIGHT // 2) + (radar_offset_y // 5.45) - pulsing_dot.get_height() // 2
                else:
                    # For all other resolutions, use standard centering
                    dot_y = SCREEN_HEIGHT // 2 - pulsing_dot.get_height() // 2

                screen.blit(pulsing_dot, (dot_x, dot_y))
            except Exception as e:
                print(f"Error loading location dot: {e}")
        else:
                pass
        # Since images likely take less resources than gradient'd text.'
        if title_4hr_normal and title_4hr_tropical and title_4hr_redmode:
            if is_redmode:
                title_image = title_4hr_redmode
            elif is_tropical and num_gifs > 1:
                title_image = title_4hr_tropical if current_gif_idx == 1 else title_4hr_normal
            else:
                title_image = title_4hr_tropical if is_tropical else title_4hr_normal
            
            # Apply fade transitions to title in tropical mode  
            if is_tropical and num_gifs > 1 and 'current_fade_alpha' in globals() and globals()['current_fade_alpha'] < 255:
                faded_title = title_image.copy()
                faded_title.set_alpha(globals()['current_fade_alpha'])
                title_image = faded_title

            image_x = 10
            image_y = 10
            screen.blit(title_image, (image_x, image_y))
        else:
            title_cache_key = (title_text, scaled_config["TITLE_CONFIG"]["font_size"])
            if title_cache_key not in gradient_title_cache:
                gradient_title_cache[title_cache_key] = create_gradient_text_surface(
                    title_text,
                    scaled_config["TITLE_CONFIG"]["font_path"],
                    scaled_config["TITLE_CONFIG"]["font_size"],
                    (255, 50, 50),
                    (0, 0, 0),
                    (255, 255, 255),
                    4
                )
            screen.blit(gradient_title_cache[title_cache_key], scaled_config["TITLE_CONFIG"]["position"])
        screen.blit(mini8s_logo, logo_rect)
        if current_bar_texture:
            bar_rect = current_bar_texture.get_rect()
            bar_rect.topleft = (0, SCREEN_HEIGHT - bar_rect.height)
            screen.blit(current_bar_texture, bar_rect)
            if warning_text and warning_text.strip():
                        # Use cached pre-rendered surface instead of rendering each frame
                        warning_surface = get_cached_warning_surface(
                            warning_text,
                            scaled_config["TKR_WARNING_TITLE_CONFIG"]["font_path"],
                            scaled_config["TKR_WARNING_TITLE_CONFIG"]["font_size"],
                            scaled_config["TKR_WARNING_TITLE_CONFIG"]["color"],
                            (0, 0, 0),  # outline_color
                            scale_value(4, scaled_config["scale_y"]),  # outline_width
                            True,  # italic
                            warning_text_cache
                        )
                        screen.blit(warning_surface, scaled_config["TKR_WARNING_TITLE_CONFIG"]["position"])

        if is_transitioning and panel_to_blit_during_flip:
            current_panel_w = panel_to_blit_during_flip.get_width()
            blit_x = panel_render_pos_tuple[0] + (panel_original_width_for_centering - current_panel_w) // 2
            screen.blit(panel_to_blit_during_flip, (blit_x, panel_render_pos_tuple[1]))
        else:
            if display_mode == "STABLE_CONDITIONS":
                if pre_rendered_conditions_surface:
                    screen.blit(pre_rendered_conditions_surface, panel_render_pos_tuple)
            else:
                if pre_rendered_forecast_surface:
                    screen.blit(pre_rendered_forecast_surface, panel_render_pos_tuple)

        if ticker_surface:
            if should_scroll:
                # Double scroll speed if more than 3 alerts
                scroll_speed_multiplier = 1.5 if len(alert_list) > 3 else 1.0
                ticker_x -= scaled_config["TICKER_CONFIG"]["scroll_speed"] * scroll_speed_multiplier * (clock.get_time() / 1000.0)

                # Check if ticker has scrolled completely off screen
                if ticker_x + ticker_width < 0:
                    ticker_x = SCREEN_WIDTH
                    if len(alert_list) > 1:
                        ticker_scroll_count += 1
                        # Always use 1 scroll when more than 3 alerts to cycle through them faster
                        if len(alert_list) > 3:
                            required_scrolls = 1
                        elif len(alert_list) >= 3:
                            required_scrolls = 1
                        else:
                            required_scrolls = 2
                        if ticker_scroll_count >= required_scrolls:
                            ticker_scroll_count = 0
                            current_alert_index = (current_alert_index + 1) % len(alert_list)
                            current_alert = alert_list[current_alert_index]
                            warning_text = current_alert['event_upper']
                            ticker_text_content = current_alert['ticker_text']

                            # Change bar color based on new alert type
                            if current_alert['alert_level'] == "ALERT":
                                current_bar_texture, current_alert_level = alert_bar_texture, "ALERT"
                            elif current_alert['alert_level'] == "WATCH":
                                current_bar_texture, current_alert_level = watch_bar_texture, "WATCH"
                            else:  # STATEMENT or ADVISORY
                                current_bar_texture, current_alert_level = statement_bar_texture, "STATEMENT"
                            outline_width_px = max(1, scale_value(3, scaled_config["scale_y"]))
                            ft_font_key = (scaled_config["TICKER_CONFIG"]["font_path"], scaled_config["TICKER_CONFIG"]["font_size"], False)
                            if ft_font_key not in _font_cache:
                                try:
                                    _font_cache[ft_font_key] = pygame.freetype.Font(ft_font_key[0], ft_font_key[1])
                                except Exception:
                                    _font_cache[ft_font_key] = pygame.freetype.SysFont(None, ft_font_key[1])
                            ft_font = _font_cache[ft_font_key]
                            text_rect_ft = ft_font.get_rect(ticker_text_content)
                            text_actual_width = text_rect_ft.width

                            ticker_surface = get_cached_warning_surface(
                                ticker_text_content,
                                scaled_config["TICKER_CONFIG"]["font_path"],
                                scaled_config["TICKER_CONFIG"]["font_size"],
                                scaled_config["TICKER_CONFIG"]["color"],
                                (0, 0, 0),
                                outline_width_px,
                                False,
                                ticker_text_cache
                            )
                            ticker_width = ticker_surface.get_width()
                            should_scroll = text_actual_width > scaled_config["TICKER_CONFIG"]["scroll_threshold"]
                            ticker_x = SCREEN_WIDTH if should_scroll else (SCREEN_WIDTH - ticker_width) // 2
                            
                            # Play audio when ticker switches to display next alert
                            play_ticker_audio(warning_text, is_new_alert=False, radar_loaded=True)

            # So the text wont go out of bounds or clip out...
            ticker_y = scaled_config["TICKER_CONFIG"]["position_y"]

            # Outline thickness (3 scaled) — used to adjust ticker top so the glyph baseline remains unchanged
            outline_width_px = max(1, scale_value(3, scaled_config["scale_y"]))

            # Ensure the ticker (including its outline) sits comfortably inside the bottom alert bar
            bar_top = SCREEN_HEIGHT - scaled_bottom_bar_height
            inner_margin = scale_value(3, scaled_config["scale_y"])  # minimal gap from the top of bar to outline
            desired_final_ticker_y = ticker_y
            min_allowed_final_ticker_y = bar_top + inner_margin + outline_width_px
            final_ticker_y = max(desired_final_ticker_y, min_allowed_final_ticker_y)

            # Move the top of the ticker by the outline padding so the visible glyphs align.
            # Place the surface top at final_ticker_y - outline_width_px so glyphs (drawn at y==outline_width) are at final_ticker_y
            adjusted_ticker_y = final_ticker_y - outline_width_px

            screen_rect = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
            ticker_rect = pygame.Rect(ticker_x, adjusted_ticker_y, ticker_width, ticker_surface.get_height())
            clipped_rect = ticker_rect.clip(screen_rect)

            if clipped_rect.width > 0 and clipped_rect.height > 0:
                source_x = max(0, -ticker_x)
                # start from surface top since we adjusted the blit position above
                source_y = 0
                available_h = ticker_surface.get_height()
                blit_h = min(clipped_rect.height, available_h - source_y)
                source_rect = pygame.Rect(source_x, source_y, clipped_rect.width, blit_h)
                blit_y = clipped_rect.y
                screen.blit(ticker_surface, (clipped_rect.x, blit_y), source_rect)

        # Render FPS counter if enabled
        if show_fps:
            current_fps = clock.get_fps()
            fps_text = f"FPS: {current_fps:.1f}"
            fps_color = (173, 216, 230)  # Baby blue color
            fps_surface = fps_font.render(fps_text, True, fps_color)
            fps_rect = fps_surface.get_rect(center=(SCREEN_WIDTH // 2, fps_font_size // 2 + 5))
            screen.blit(fps_surface, fps_rect)

        pygame.display.flip()
        clock.tick()  # VSync enabled: syncs to monitor refresh | VSync disabled: unlimited FPS
    print("Stopping thread...")
    stop_event.set()
    
    try:
        weather_timer.cancel()
        print("Stopped weather threading update timer.")
    except:
        pass  # Timer may have already fired

    if weather_worker.is_alive():
        weather_worker.join(timeout=2.0)
        if weather_worker.is_alive():
            print("Exiting during threading update.")
        else:
            print("Exited normally?")
    else:
        print("Exiting...")
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    # Initialize PyQt5 application
    app = QApplication(sys.argv)
    app.setStyle("Oxygen")

    # Show welcome/setup window
    window = Mini8sWelcome()
    window.show()
    app.exec_()

    if window.should_start_mini8s:
        initialize_mini8s()

