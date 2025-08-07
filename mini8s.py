import pygame # Community Edition as of v0.3.98!
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
import ptext

VERSION = "v0.3.98 [BETA]"
# Completely revamped loading screen
# Optimized temperature grabbing
# The LDL/ticker scroll can now read out multiple alerts (one after the other)
# Added a "Redmode" exclusive to Hurricanes.
# Fixed multiple QoL issues and bugs.
# Replaced PyGame with PyGame-ce!

with open('cond_names.json', 'r') as f:
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

    # Draw outline first if requested
    if outline_color and outline_width > 0:
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    outline_surface = font.render(text, True, outline_color)
                    final_surface.blit(outline_surface, (outline_width + dx, outline_width + dy))

    # Create gradient
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
                        forecast_text_val, forecast_periods_data = fetch_weather_forecast(forecast_url)
                        radar_data_tuple = fetch_radar_image(is_tropical=is_tropical)

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
TITLE_CONFIG = {"font_size": 64}
WARNING_CONFIG = {"font_path": "fonts/Interstate_Bold.otf", "font_size": 32, "color": (255, 255, 255), "position": (10, SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT + 15)}
TICKER_CONFIG = {"font_path": "fonts/Interstate_Light.otf", "font_size": 64, "color": (255, 255, 255), "position_y": SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT + 50, "scroll_threshold": 800, "scroll_speed": 300, "static_duration": 3000}
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
PANEL_TEXTURE_PATH = "textures/graphics/paneaero.png"
WATCH_BAR_TEXTURE_PATH = "textures/graphics/watch-statement_LDL.png"
ALERT_BAR_TEXTURE_PATH = "textures/graphics/warning_LDL.png"
# Changing LOGO_CONFIG doesn't actually do anything? WTF?'
LOGO_CONFIG = {"path": "textures/graphics/mini8s_logo.png", "width": 175, "margin_right": 10, "margin_top": 10}
CURRENT_CONDITIONS_ICON_SIZE_RATIO = 0.15
FORECAST_ICON_SIZE_MULTIPLIER = 2.0

PANEL_FLIP_ANIMATION_STEPS = 19
FLIP_SUB_STEP_DURATION_MS = 10

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
        if not data: return None, None, None, f"ZIP {zip_code}"
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

        location_name = f"{county} County" if county else f"ZIP {zip_code}"
        return latitude, longitude, county, location_name
    except Exception as e:
        print(f"Error getting coordinates from ZIP: {e}")
        return None, None, None, f"ZIP {zip_code}"

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
            conditions_data['gusts'] = f"{round(gust_kmh / 1.60934)} MPH" if gust_kmh is not None else "None"
        else:
            print(f"Unable to get data ({obs_res.status_code}), using partial data.")
            conditions_data['humidity'] = f"{current_period.get('relativeHumidity', {}).get('value', 'N/A')}%"
        conditions_text = conditions_data['conditions']
        if conditions_data.get('conditions') == "Chance Showers And Thunderstorms":
            conditions_data['conditions'] = "Showers Nearby"

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
def build_radar_url(lat, lon):
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
# DEBUG MODE HERE
    params = {
        'tzoff': '0',
        'lat0': f"{lat:.10f}",
        'lon0': f"{lon:.10f}",
        'layers[]': ['nexrad', 'warnings', 'uscounties', 'watches', 'blank'],
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
        'frames': '1',
        'interval': '5',
        'filter': '0',
        'cu': '0',
        'sortcol': 'fcster',
        'sortdir': 'DESC',
        'lsrlook': '%2B',
        'lsrwindow': '0'
    }

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

def fetch_radar_image(is_tropical=False):
    try:
        lat, lon, _, _ = get_coordinates_from_zip(ZIP_CODE)
        if not lat or not lon:
            return None

        # First, get the standard radar GIF
        radar_url = build_radar_url(lat, lon)
        def get_gif_frames_and_durations(radar_url):
            response = requests.get(radar_url, stream=True, timeout=30)
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
                print("Could not find the GIF download link on the page.")
                return None, None
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
                        scaled_frame = cropped_frame.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        pygame_surface = pygame.image.frombytes(scaled_frame.tobytes(), scaled_frame.size, scaled_frame.mode).convert_alpha()
                        if is_tropical:
                            offset_y = 40  # tropical: crop already applied, keep as before
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
                    # Add a 2 second pause (2000 ms) to the last frame
                    if pygame_frames and frame_durations_ms:
                        frame_durations_ms[-1] += 1500
                    return pygame_frames, frame_durations_ms
            return None, None

        # Always get the standard radar GIF
        frames1, durations1 = get_gif_frames_and_durations(radar_url)
        if frames1 is None or durations1 is None:
            return None

        if is_tropical:
            print(f"Well crap, looks like you got a tropical system on your hands, stay safe!")
            def build_tropical_url(lat, lon):
                current_time = datetime.now()
                base_url = "https://mesonet.agron.iastate.edu/GIS/apps/rview/warnings.phtml"
                params = {
                    'tzoff': '0',
                    'lat0': f"{lat:.10f}",
                    'lon0': f"{lon:.10f}",
                    'layers[]': ['goes_ir', 'nexrad', 'warnings', 'uscounties', 'watches', 'blank'],
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
                url_parts = [base_url + "?"]
                for key, value in params.items():
                    if key == 'layers[]':
                        for layer in value:
                            url_parts.append(f"layers%5B%5D={layer}&")
                    else:
                        url_parts.append(f"{key}={value}&")
                return ''.join(url_parts).rstrip('&')

            tropical_url = build_tropical_url(lat, lon)
            frames2, durations2 = get_gif_frames_and_durations(tropical_url)
            if frames2 and durations2:
                return [(frames1, durations1, 0), (frames2, durations2, 25000)]

        return [(frames1, durations1, 0)]
    except Exception as e:
        print(f"Error in fetch_radar_image: {e}")
        traceback.print_exc()
        return None

# I hate how disorganized this looks, but it'll work for now.
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

        response = requests.get(alerts_url, headers={'User-Agent': 'Mini8sWeatherApp/1.0'})
        response.raise_for_status()
        data = response.json()
        features = data.get('features', [])
        if not features: return [], None, None, False
        all_alerts = []
        is_tropical = False

        # Define alert type hierarchy (higher number = higher priority)
        alert_type_hierarchy = {
            "TORNADO EMERGENCY": 12,
            "TORNADO WARNING": 10,
            "SEVERE THUNDERSTORM WARNING": 9,
            "TORNADO WATCH": 8,
            "SEVERE THUNDERSTORM WATCH": 7,
            "FLASH FLOOD WARNING": 6,
            "FLOOD WARNING": 5,
            "FLASH FLOOD WATCH": 4,
            "FLOOD WATCH": 3,
            "HURRICANE WARNING": 2,
            "HURRICANE WATCH": 2,
            "TROPICAL STORM WARNING": 1,
            "TROPICAL STORM WATCH": 1,
        }

        # Process all alerts
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
            priority_score = alert_type_hierarchy.get(event_upper_normalized, 0)

            # Determine alert level
            if "WARNING" in event_upper_normalized:
                alert_level = "ALERT"
            elif any(keyword in event_upper_normalized for keyword in ["WATCH", "STATEMENT", "ADVISORY"]):
                alert_level = "WATCH"
            elif event_upper_normalized == "AIR QUALITY ALERT":
                alert_level = "WATCH"
            else:
                alert_level = "WATCH"

            # Store each alert as a dictionary
            alert_data = {
                'event': event,
                'event_upper': event.upper(),
                'headline': headline,
                'description': description,
                'ticker_text': (' ... '.join([headline, description] + ([instruction] if instruction and instruction.strip().upper() not in ['N/A', 'NA', ''] else [])).replace('\n', ' ').replace('\r', ' ').replace('  ', ' ').strip()),
                'priority': priority_score,
                'alert_level': alert_level
            }
            all_alerts.append(alert_data)

        # Sort alerts by priority (highest first)
        all_alerts.sort(key=lambda x: x['priority'], reverse=True)

        # Get the highest priority alert type for logo/redmode purposes
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
        ptext.draw(text, center=(x, y), fontname=font_path, fontsize=font_size,
                   color=text_color, ocolor=outline_color, owidth=outline_width)
    else:
        ptext.draw(text, (x, y), fontname=font_path, fontsize=font_size,
                   color=text_color, ocolor=outline_color, owidth=outline_width)
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

    # Load the JSON config (you should do this once at startup, not every call)
    import json
    with open('cond_names.json', 'r') as f:
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

    # Special handling for clear with modifiers
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

    # Add path prefix if not already there
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

        # Forecast truncation if words are too big.
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
        loaded_tex = pygame.image.load(PANEL_TEXTURE_PATH).convert_alpha()
        panel_bg_texture = pygame.transform.smoothscale(loaded_tex, (panel_width, panel_height))
        panel_surface.blit(panel_bg_texture, (0, 0))
    except:
        panel_surface.fill(config["background_color"])

    y_pos_draw = padding
    # Draw "72 Hour Forecast" with white text and black outline using ptext, this looks amazing!
    ptext.draw("72 Hour Forecast", (padding, y_pos_draw), fontname=config["font_path"],
               fontsize=config["title_font_size"], color=(255, 255, 255),
               ocolor=(0, 0, 0), owidth=3, surf=panel_surface)
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
        content_height += len(lines) * int(config["line_height"] * 0.85)

    remaining_space = panel_height - (padding * 2) - content_height
    spacing_between_entries = 15
    if len(entries_to_draw) > 1 and remaining_space > 0:
        spacing_between_entries += remaining_space / (len(entries_to_draw) - 1)

    for i, period in enumerate(entries_to_draw):
        if y_pos_draw + config["line_height"] > panel_height - padding: break
        icon_size = int(config["line_height"] * FORECAST_ICON_SIZE_MULTIPLIER)

        # Day name
        day_name = period.get('name', '')
        ptext.draw(day_name + " - ",
                   (padding, y_pos_draw),
                   fontname=config["font_path"],
                   fontsize=config["data_font_size"],
                   color=(220, 221, 51),        # Black text
                   ocolor=(0, 0, 0),  # White outline
                   owidth=1,                # 2 pixel outline
                   surf=panel_surface)
        day_text_width = period_font.size(day_name + " - ")[0]
        temp_x_start = padding + day_text_width

        # 72 Hour Forecast ptext
        temp_text = f"{period.get('temperature', '')}°{period.get('temperatureUnit', '')}"
        ptext.draw(temp_text,
                   (temp_x_start, y_pos_draw),
                   fontname=config["font_path"],
                   fontsize=config["data_font_size"],
                   color=(255, 255, 255),  # White
                   ocolor=(0, 0, 0),       # Black outline
                   owidth=2,               # 1 pixel outline
                   surf=panel_surface)

        icon_filename = get_weather_icon_filename(period.get('shortForecast', ''), "night" in period.get('name', '').lower())
        icon_image = pygame.transform.smoothscale(pygame.image.load(icon_filename).convert_alpha(), (icon_size, icon_size))
        panel_surface.blit(icon_image, (panel_width - padding - icon_size, y_pos_draw))
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

    return panel_surface

def create_current_conditions_surface(current, location_name, scaled_config, panel_texture_cache, weather_icon_cache, font_cache):
    if not current: return None
    config = scaled_config["CURRENT_CONDITIONS_CONFIG"]
    padding = config["padding"]
    panel_width = config["width"]
    panel_height = config["max_height"]

    _, current_alert_level, primary_alert_type, _ = get_weather_alerts(ZIP_CODE) if 'ZIP_CODE' in globals() else (None, None, None, None)

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
        loaded_tex = pygame.image.load(PANEL_TEXTURE_PATH).convert_alpha()
        panel_bg_texture = pygame.transform.smoothscale(loaded_tex, (panel_width, panel_height))
        panel_surface.blit(panel_bg_texture, (0, 0))
    except:
        panel_surface.fill(config["background_color"])
    y_pos = padding
    ptext.draw(location_name, midtop=((panel_width // 2), y_pos), fontname=config["font_path"],
               fontsize=config["title_font_size"], color=(0, 0, 0),
               ocolor=(255, 255, 255), owidth=2, surf=panel_surface)
    y_pos += title_font.get_height() + 15

    icon_size_val = int(panel_height * CURRENT_CONDITIONS_ICON_SIZE_RATIO)
    is_night = not current.get("isDaytime", True)
    icon_filename = get_weather_icon_filename(current.get('conditions', 'N/A'), is_night)
    icon_image = pygame.transform.smoothscale(pygame.image.load(icon_filename).convert_alpha(), (icon_size_val, icon_size_val))
    panel_surface.blit(icon_image, ((panel_width - icon_size_val) // 2, y_pos)); y_pos += icon_size_val + 15

    is_heat_alert = primary_alert_type and ("HEAT" in primary_alert_type.upper())
    temp_color = (200, 0, 25) if is_heat_alert else config["color"]

    ptext.draw(f"{current.get('temperature', 'N/A')}°F",
               midtop=((panel_width // 2), y_pos),
               fontname=config["font_path"],
               fontsize=scale_font_size(80, scaled_config['scale_y']),
               color=temp_color,
               ocolor=(0, 0, 0),
               owidth=2,
               surf=panel_surface)
    y_pos += temp_font.get_height() + 15

    conditions_text = current.get('conditions', 'N/A')
    x_offset = config.get("condition_desc_x_offset", 0)
    ptext.draw(conditions_text,
               midtop=((panel_width // 2) + x_offset, y_pos),
               fontname=config["font_path"],
               fontsize=config["condition_desc_font_size"],
               color=config["color"],
               ocolor=(0, 0, 0),
               owidth=2,
               surf=panel_surface)
    y_pos += desc_font.get_height() + 20

    conditions_list = [("Humidity", current.get('humidity', 'N/A')), ("Dew Point", current.get('dewpoint', 'N/A')), ("Pressure", current.get('pressure', 'N/A')), ("Visibility", current.get('visibility', 'N/A')), ("Wind", current.get('wind', 'N/A')), ("Gusts", current.get('gusts', 'N/A'))]
    remaining_height = panel_height - y_pos - padding
    if conditions_list and remaining_height > 20:
        dynamic_line_height = remaining_height / len(conditions_list)
        max_label_width = max([list_font.size(f"{label}:")[0] for label, _ in conditions_list])
        list_start_x = padding
        for label, value in conditions_list:
            ptext.draw(f"{label}:",
                      (list_start_x, y_pos),
                      fontname=config["font_path"],
                      fontsize=config["list_font_size"],
                      color=config["title_color"],  # Yellow color
                      ocolor=(0, 0, 0),
                      owidth=1,
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

                # Draw with ptext for outline
                ptext.draw(str(value),
                          (list_start_x + max_label_width + 20, y_pos),
                          fontname=config["font_path"],
                          fontsize=config["list_font_size"],
                          color=text_color,
                          ocolor=(0, 0, 0),
                          owidth=2,
                          surf=panel_surface)
            else:
                panel_surface.blit(list_font.render(str(value), True, config["color"]), (list_start_x + max_label_width + 20, y_pos))
            y_pos += dynamic_line_height
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
            shrink_frames.append(pygame.transform.smoothscale(panel_surface_to_animate, (scaled_width_shrink, panel_height)))
        else:
            shrink_frames.append(pygame.Surface((0, panel_height), pygame.SRCALPHA))

        scale_expand = i / num_animation_steps if num_animation_steps > 0 else 1.0
        scaled_width_expand = max(0, int(original_panel_width * scale_expand))
        if scaled_width_expand > 0:
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
        for frame_img in radar_frames_list:
            base_frame = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            base_frame.fill((0, 0, 0))
            frame_rect = frame_img.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            base_frame.blit(frame_img, frame_rect)
            draw_text(base_frame, title_text, scaled_config["TITLE_CONFIG"]["position"], scaled_config["TITLE_CONFIG"]["font_path"], scaled_config["TITLE_CONFIG"]["font_size"], font_cache, scaled_config["TITLE_CONFIG"]["color"])
            base_frame.blit(mini8s_logo, logo_rect)
            if current_bar_texture:
                bar_rect = current_bar_texture.get_rect()
                bar_rect.topleft = (0, SCREEN_HEIGHT - bar_rect.height)
                base_frame.blit(current_bar_texture, bar_rect)
            draw_text(base_frame, warning_text, scaled_config["WARNING_CONFIG"]["position"], scaled_config["WARNING_CONFIG"]["font_path"], scaled_config["WARNING_CONFIG"]["font_size"], font_cache, scaled_config["WARNING_CONFIG"]["color"])
            base_common_frames_global.append(base_frame)
    else: # Fallback for no radar
        base_frame = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        base_frame.fill((0, 0, 0))
        draw_text(base_frame, "Radar data unavailable", (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), scaled_config["TITLE_CONFIG"]["font_path"], 36, font_cache, (255, 100, 100), center_x=True)
        draw_text(base_frame, title_text, scaled_config["TITLE_CONFIG"]["position"], scaled_config["TITLE_CONFIG"]["font_path"], scaled_config["TITLE_CONFIG"]["font_size"], font_cache, scaled_config["TITLE_CONFIG"]["color"])
        base_frame.blit(mini8s_logo, logo_rect)
        if current_bar_texture:
            bar_rect = current_bar_texture.get_rect()
            bar_rect.topleft = (0, SCREEN_HEIGHT - bar_rect.height)
            base_frame.blit(current_bar_texture, bar_rect)
        draw_text(base_frame, warning_text, scaled_config["WARNING_CONFIG"]["position"], scaled_config["WARNING_CONFIG"]["font_path"], scaled_config["WARNING_CONFIG"]["font_size"], font_cache, scaled_config["WARNING_CONFIG"]["color"])
        base_common_frames_global.append(base_frame)

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
# "Loading..." seems useless
def draw_loading_screen(screen, message="Loading...", font_cache=None):
    display_width = screen.get_width()
    display_height = screen.get_height()

    # Try to load and draw background image
    try:
        bg_image = pygame.image.load("textures/graphics/background.png").convert()
        # Scale background to fit screen
        bg_image = pygame.transform.smoothscale(bg_image, (display_width, display_height))
        screen.blit(bg_image, (0, 0))
    except Exception as e:
        screen.fill((0, 0, 0))
        print(f"Could not load background image: {e}")

    # Draw main loading message with ptext (white text with black outline)
    ptext.draw(message,
               center=(display_width // 2, display_height // 2 - 30),
               fontname="fonts/Interstate_Bold.otf",
               fontsize=48,
               color=(255, 255, 255),
               ocolor=(0, 0, 0),
               owidth=3,
               italic=True)
    try:
        version_logo = pygame.image.load("textures/graphics/mini8s_logo_verstring.png").convert_alpha()
        version_logo = pygame.transform.smoothscale(version_logo,
                                                   (int(version_logo.get_width() * 0.5),
                                                    int(version_logo.get_height() * 0.5)))
        logo_rect = version_logo.get_rect(center=(display_width // 2 - 5, display_height // 2 + 100))
        screen.blit(version_logo, logo_rect)
    except Exception as e:
        # Fallback to text if image not found
        ptext.draw(f"Mini8s {VERSION}",
                   center=(display_width // 2, display_height // 2 + 80),
                   fontname="fonts/Interstate_Light.otf",
                   fontsize=24,
                   color=(255, 255, 255),
                   ocolor=(0, 0, 0),
                   owidth=2)
        print(f"Could not load version logo: {e}")

    pygame.display.flip()

def main():
    print(f"Mini8s {VERSION} by Starzainia and HexagonMidis!")
    global ZIP_CODE, SCREEN_WIDTH, SCREEN_HEIGHT, TARGET_FPS, pre_rendered_conditions_surface, pre_rendered_forecast_surface

    # Load config file if it exists
    config_file = "config.json"
    default_config = {"last_width": 1280, "last_height": 720, "last_zip": ""}

    try:
        with open(config_file, 'r') as f:
            saved_config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        saved_config = default_config

    while True:
        # Get user inputs from console with saved defaults
        while True:
            last_zip = saved_config.get("last_zip", "")
            if last_zip:
                user_zip = input(f"ZIP Code [Last: {last_zip}]: ").strip()
                if not user_zip:
                    user_zip = last_zip
            else:
                user_zip = input("ZIP Code: ").strip()

            if user_zip.isdigit() and len(user_zip) == 5:
                ZIP_CODE = user_zip
                break
            else:
                print("Invalid ZIP code. Please enter a 5-digit number.")

        while True:
            try:
                last_width = saved_config.get("last_width", 1280)
                width_input = input(f"Enter width [Last: {last_width}]: ").strip()
                if not width_input:  # User pressed Enter
                    SCREEN_WIDTH = last_width
                else:
                    SCREEN_WIDTH = int(width_input)

                if SCREEN_WIDTH <= 0:
                    print("..how does negative resolution work?")
                elif SCREEN_WIDTH > 9999:
                    print("Width must be 4 digits or less (max 9999).")
                else:
                    break
            except ValueError:
                print("Please put in a non-negative width.")

        while True:
            try:
                last_height = saved_config.get("last_height", 720)
                height_input = input(f"Enter height [Last: {last_height}]: ").strip()
                if not height_input:  # User pressed Enter
                    SCREEN_HEIGHT = last_height
                else:
                    SCREEN_HEIGHT = int(height_input)

                if SCREEN_HEIGHT <= 0:
                    print("ok are you intentially getting this wrong???")
                elif SCREEN_HEIGHT > 9999:
                    print("Height must be 4 digits or less (max 9999).")
                else:
                    break
            except ValueError:
                print("Invalid height. Please enter a number.")

        if SCREEN_WIDTH <= 800 and SCREEN_HEIGHT <= 600:
            print(f"Sorry, but {SCREEN_WIDTH}x{SCREEN_HEIGHT} is too low for Mini8s!")
            continue
        break

    new_config = {
        "last_width": SCREEN_WIDTH,
        "last_height": SCREEN_HEIGHT,
        "last_zip": ZIP_CODE
    }

    try:
        with open(config_file, 'w') as f:
            json.dump(new_config, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save config: {e}")

    TARGET_FPS = 60 # Change this to fit your refresh rate!

    pygame.init()
    font_cache = {}; panel_texture_cache = {}; weather_icon_cache = {}
    gradient_title_cache = {}  # For "4 Hour Radar" title
    warning_text_cache = {}    # For warning bar text
    panel_text_cache = {}

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.HWSURFACE | pygame.DOUBLEBUF)
    draw_loading_screen(screen, "Initializing Mini8s...", font_cache)

    try:
        program_icon = pygame.image.load('textures/graphics/mini8s_taskbar.png')
        pygame.display.set_icon(program_icon)

    except Exception as e:
        print(f"Cannot load taskbar icon: {e}")

    TICKER_CONFIG = {"font_path": "fonts/Interstate_Light.otf", "font_size": 64, "color": (255, 255, 255), "position_y": SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT + 50, "scroll_threshold": 800, "scroll_speed": 300, "static_duration": 3000}
    TITLE_CONFIG = {"font_path": "fonts/Interstate_Bold.otf", "font_size": 64, "color": (255, 50, 50), "position": (20, 10)}
    WARNING_CONFIG = {"font_path": "fonts/Interstate_Bold.otf", "font_size": 32, "color": (255, 255, 255), "position": (20, SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT + 15)}
    CURRENT_CONDITIONS_CONFIG = {"font_path": "fonts/Frutiger-Black.otf", "title_font_size": 40, "condition_desc_font_size": 40, "condition_desc_x_offset": -2, "data_font_size": 28, "list_font_size": 28, "color": (255, 255, 255), "title_color": (220, 220, 50), "position": (10, 120), "line_height": 40, "background_color": (0, 0, 0, 180), "width": 550, "padding": 20, "max_height": 770}
    PANEL_TEXTURE_PATH = "textures/graphics/paneaero.png"
    WATCH_BAR_TEXTURE_PATH = "textures/graphics/watch-statement_LDL.png"
    ALERT_BAR_TEXTURE_PATH = "textures/graphics/warning_LDL.png"
    LOGO_CONFIG = {"path": "textures/graphics/mini8s_logo.png", "width": 200, "margin_right": 10, "margin_top": 10}

    scale_x, scale_y = calculate_scale_factors(SCREEN_WIDTH, SCREEN_HEIGHT)
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
    "WARNING_CONFIG": {
        "font_path": WARNING_CONFIG["font_path"],
        "font_size": scale_font_size(WARNING_CONFIG["font_size"], scale_y),
        "color": WARNING_CONFIG["color"],
        "position": (scale_value(WARNING_CONFIG["position"][0], scale_x), SCREEN_HEIGHT - scaled_bottom_bar_height + scale_value(7, scale_y))
    },
    "TICKER_CONFIG": {
        "font_path": TICKER_CONFIG["font_path"],
        "font_size": scale_font_size(TICKER_CONFIG["font_size"], scale_y),
        "color": TICKER_CONFIG["color"],
        "position_y": SCREEN_HEIGHT - scaled_bottom_bar_height + scale_value(50, scale_y),
        "scroll_threshold": scale_value(TICKER_CONFIG["scroll_threshold"], scale_x),
        "scroll_speed": scale_value(TICKER_CONFIG["scroll_speed"], scale_x),
        "static_duration": TICKER_CONFIG["static_duration"]
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
        config_to_edit["data_font_size"] = int(config_to_edit["data_font_size"] * 0.84)
        config_to_edit["list_font_size"] = int(config_to_edit["list_font_size"] * 0.9)
        config_to_edit["line_height"] = int(config_to_edit["line_height"] * 0.8)

    pygame.display.set_caption(f"Mini8s {VERSION} for {ZIP_CODE}")
    clock = pygame.time.Clock()
    draw_loading_screen(screen, "Grabbing Weather Data...", font_cache)

    title_text = DEFAULT_TITLE_TEXT; warning_text = WARNING_TEXT

    display_mode = "STABLE_CONDITIONS"
    last_panel_switch_time = pygame.time.get_ticks()

    transition_sub_step_idx = 0
    last_flip_sub_step_time = 0

    current_bar_texture = None
    current_alert_level = None

    try:
        watch_bar_texture = pygame.transform.smoothscale(pygame.image.load(WATCH_BAR_TEXTURE_PATH).convert_alpha(), (SCREEN_WIDTH, scaled_bottom_bar_height))
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
        mini8s_logo = pygame.transform.smoothscale(logo_orig, (logo_w, logo_h))
        logo_rect = mini8s_logo.get_rect(topright=(SCREEN_WIDTH - scaled_config["LOGO_CONFIG"]["margin_right"], scaled_config["LOGO_CONFIG"]["margin_top"]))
    except Exception as e:
        print(f"Logo error: {e}")
    try:
        title_4hr_normal_orig = pygame.image.load("textures/graphics/4hrradar.png").convert_alpha()
        title_4hr_tropical_orig = pygame.image.load("textures/graphics/4hrradarsatellite.png").convert_alpha()
        target_font_size = scaled_config["TITLE_CONFIG"]["font_size"]

        target_height = int(target_font_size * 1.2)

        normal_aspect = title_4hr_normal_orig.get_width() / title_4hr_normal_orig.get_height()
        tropical_aspect = title_4hr_tropical_orig.get_width() / title_4hr_tropical_orig.get_height()
        normal_width = int(target_height * normal_aspect)
        tropical_width = int(target_height * tropical_aspect)

        title_4hr_normal = pygame.transform.smoothscale(title_4hr_normal_orig, (normal_width, target_height))
        title_4hr_tropical = pygame.transform.smoothscale(title_4hr_tropical_orig, (tropical_width, target_height))

    except Exception as e:
        print(f"Error loading title images: {e}")
        # Fallback to None if images not found
        title_4hr_normal = None
        title_4hr_tropical = None
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

    lat, lon, state, location_name = get_coordinates_from_zip(ZIP_CODE)
    forecast_url, current_conditions_data, forecast_periods_data = None, None, None

    if lat and lon:
        _, _, _, forecast_url, _ = get_forecast_grid_point(lat, lon)
        title_text = f"4 Hour Radar"
        current_conditions_data = fetch_current_conditions(lat, lon)
    alert_list, _, alert_type_val, is_tropical = get_weather_alerts(zip_code=ZIP_CODE, state=state)
    single_alert_mode = False

    # Redmode logo logic.
    if alert_type_val:
        alert_upper = alert_type_val.upper()
        if "HURRICANE WATCH" in alert_upper or "HURRICANE WARNING" in alert_upper:
            is_redmode = True
            logo_path = "textures/graphics/mini8s-redmode_logo.png"
            try:
                logo_orig = pygame.image.load(logo_path).convert_alpha()
                logo_w, logo_h = scaled_config["LOGO_CONFIG"]["width"], int(scaled_config["LOGO_CONFIG"]["width"] * (logo_orig.get_height() / logo_orig.get_width()))
                mini8s_logo = pygame.transform.smoothscale(logo_orig, (logo_w, logo_h))
                logo_rect = mini8s_logo.get_rect(topright=(SCREEN_WIDTH - scaled_config["LOGO_CONFIG"]["margin_right"], scaled_config["LOGO_CONFIG"]["margin_top"]))
                print("!!! REDMODE ACTIVATED !!! Hurricane detected in your area!")
            except Exception as e:
                print(f"Error loading redmode logo: {e}")

    if alert_list:
        single_alert_mode = (len(alert_list) == 1)

        current_alert_index = 0
        ticker_scroll_count = 0
        current_alert = alert_list[current_alert_index]

        warning_text = current_alert['event_upper']
        ticker_text_content = current_alert['ticker_text']

        if current_alert['alert_level'] == "ALERT":
            current_bar_texture, current_alert_level = alert_bar_texture, "ALERT"
        else:
            current_bar_texture, current_alert_level = watch_bar_texture, "WATCH"

        ticker_surface = ticker_font.render(ticker_text_content, True, scaled_config["TICKER_CONFIG"]["color"])
        ticker_width = ticker_surface.get_width()
        should_scroll = ticker_width > scaled_config["TICKER_CONFIG"]["scroll_threshold"]
        ticker_x = SCREEN_WIDTH if should_scroll else (SCREEN_WIDTH - ticker_width) // 2
        ticker_start_time = pygame.time.get_ticks()
    else:
        warning_text = " "
        ticker_surface = None
        current_bar_texture = None
        current_alert_level = None

    forecast_text_val, forecast_periods_data = fetch_weather_forecast(forecast_url)

    if current_conditions_data:
        pre_rendered_conditions_surface = create_current_conditions_surface(current_conditions_data, location_name, scaled_config, panel_texture_cache, weather_icon_cache, font_cache)
    if forecast_periods_data:
        pre_rendered_forecast_surface = create_forecast_panel_surface(forecast_periods_data, scaled_config, SCREEN_WIDTH, panel_texture_cache, weather_icon_cache, font_cache)

    draw_loading_screen(screen, "Loading Radar Data...", font_cache)
    radar_data_tuple = fetch_radar_image(is_tropical=is_tropical)
    current_radar_frame_idx, last_radar_update_time = 0, pygame.time.get_ticks()
    # This value controls the speed of the radar loop!
    SPEED_FACTOR = 16

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

    # For compatibility with create_all_pre_rendered_frames, set radar_frames_raw to the first GIF's frames (or empty)
    radar_frames_raw = radar_gif_frames[0][:] if radar_gif_frames and radar_gif_frames[0] else []
    draw_loading_screen(screen, "Pre-Rendering...", font_cache)
    create_all_pre_rendered_frames(
        radar_frames_raw, pre_rendered_conditions_surface, pre_rendered_forecast_surface,
        title_text, mini8s_logo, logo_rect, current_bar_texture, warning_text,
        scaled_config, font_cache, PANEL_FLIP_ANIMATION_STEPS
    )
    panel_original_width_for_centering = scaled_config["CURRENT_CONDITIONS_CONFIG"]["width"]
    panel_render_pos_tuple = scaled_config["CURRENT_CONDITIONS_CONFIG"]["position"]

    display_mode = "STABLE_CONDITIONS"
    last_panel_switch_time = pygame.time.get_ticks()
    is_transitioning = False
    panel_to_blit_during_flip = None

    weather_queue = queue.Queue(maxsize=2)
    stop_event = threading.Event()
    weather_worker = WeatherDataWorker(ZIP_CODE, weather_queue, stop_event)
    weather_worker.start()
    print("Background weather worker thread started")

    if 'ticker_surface' not in locals():
        ticker_surface = None
        should_scroll = False

    running = True
    show_fps = False
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
                if current_conditions_data:
                    pre_rendered_conditions_surface = create_current_conditions_surface(
                        current_conditions_data, location_name, scaled_config,
                        panel_texture_cache, weather_icon_cache, font_cache
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
                    else:
                        current_bar_texture, current_alert_level = watch_bar_texture, "WATCH"

                    ticker_surface = ticker_font.render(ticker_text_content, True, scaled_config["TICKER_CONFIG"]["color"])
                    ticker_width = ticker_surface.get_width()
                    should_scroll = ticker_width > scaled_config["TICKER_CONFIG"]["scroll_threshold"]
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

                # For compatibility with create_all_pre_rendered_frames, set radar_frames_raw to the first GIF's frames (or empty)
                radar_frames_raw = radar_gif_frames[0][:] if radar_gif_frames and radar_gif_frames[0] else []
                create_all_pre_rendered_frames(
                    radar_frames_raw, pre_rendered_conditions_surface, pre_rendered_forecast_surface,
                    title_text, mini8s_logo, logo_rect, current_bar_texture, warning_text,
                    scaled_config, font_cache, PANEL_FLIP_ANIMATION_STEPS
                )

                print("Main thread: Weather data update processed successfully")
            else:
                title_text = "Oh great, where the hell did we end up now?"

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
                            current_gif_idx = (current_gif_idx + 1) % num_gifs
                            current_gif_frame_idx = 0
                            gif_play_count = 0
                            last_gif_frame_time = current_ticks_ms
                            frames = radar_gif_frames[current_gif_idx]
                            durations = radar_gif_durations[current_gif_idx]
                            last_frame_idx = len(frames) - 1
                            # Immediately set active_radar_frame to first frame of new GIF
                            active_radar_frame = frames[0]
                            # Skip the rest of the logic for this frame
                            continue
                    current_gif_frame_idx = (current_gif_frame_idx + 1) % len(frames)
                    last_gif_frame_time = current_ticks_ms
                active_radar_frame = frames[current_gif_frame_idx]
            else:
                active_radar_frame = None
        else:
            active_radar_frame = None

        if active_radar_frame:
            screen.blit(active_radar_frame, (0, -75))
        else:
            screen.fill((0, 0, 0))

        # Since it's semi-static, use images instead of performance-heavy ptext outline+gradient.
        if title_4hr_normal and title_4hr_tropical:
            # Choose appropriate title based on is_tropical
            title_image = title_4hr_tropical if is_tropical else title_4hr_normal
            image_x = 10  # Adjust this
            image_y = 10  # Adjust this
            screen.blit(title_image, (image_x, image_y))
        else:
            title_cache_key = (title_text, scaled_config["TITLE_CONFIG"]["font_size"])
            if title_cache_key not in gradient_title_cache:
                gradient_title_cache[title_cache_key] = create_gradient_text_surface(
                    title_text,
                    scaled_config["TITLE_CONFIG"]["font_path"],
                    scaled_config["TITLE_CONFIG"]["font_size"],
                    (255, 50, 50),    # Red at top
                    (0, 0, 0),        # Black at bottom
                    (255, 255, 255),  # White outline
                    3                 # Outline width
                )
            screen.blit(gradient_title_cache[title_cache_key], scaled_config["TITLE_CONFIG"]["position"])
        screen.blit(mini8s_logo, logo_rect)
        if current_bar_texture:
            bar_rect = current_bar_texture.get_rect()
            bar_rect.topleft = (0, SCREEN_HEIGHT - bar_rect.height)
            screen.blit(current_bar_texture, bar_rect)
        if warning_text and warning_text.strip():
            warning_cache_key = (warning_text, scaled_config["WARNING_CONFIG"]["font_size"])
            if warning_cache_key not in warning_text_cache:
                font_key = (scaled_config["WARNING_CONFIG"]["font_path"], scaled_config["WARNING_CONFIG"]["font_size"])
                if font_key not in font_cache:
                    font_cache[font_key] = pygame.font.Font(font_key[0], font_key[1])
                warning_text_cache[warning_cache_key] = font_cache[font_key].render(
                    warning_text, True, scaled_config["WARNING_CONFIG"]["color"]
                )
            screen.blit(warning_text_cache[warning_cache_key], scaled_config["WARNING_CONFIG"]["position"])

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
            if should_scroll and pygame.time.get_ticks() - ticker_start_time > scaled_config["TICKER_CONFIG"]["static_duration"]:
                ticker_x -= scaled_config["TICKER_CONFIG"]["scroll_speed"] * (clock.get_time() / 1000.0)

                # Check if ticker has scrolled completely off screen
                if ticker_x + ticker_width < 0:
                    ticker_x = SCREEN_WIDTH
                    if len(alert_list) > 1:
                        ticker_scroll_count += 1
                        if len(alert_list) >= 3:
                            required_scrolls = 1
                        else:
                            required_scrolls = 2

                        if ticker_scroll_count >= required_scrolls:
                            ticker_scroll_count = 0
                            current_alert_index = (current_alert_index + 1) % len(alert_list)
                            current_alert = alert_list[current_alert_index]

                            # Update everything for the new alert
                            warning_text = current_alert['event_upper']
                            ticker_text_content = current_alert['ticker_text']

                            # Change bar color based on new alert type
                            if current_alert['alert_level'] == "ALERT":
                                current_bar_texture, current_alert_level = alert_bar_texture, "ALERT"
                            else:
                                current_bar_texture, current_alert_level = watch_bar_texture, "WATCH"

                            # Re-render the ticker for the new alert
                            ticker_surface = ticker_font.render(ticker_text_content, True, scaled_config["TICKER_CONFIG"]["color"])
                            ticker_width = ticker_surface.get_width()
                            should_scroll = ticker_width > scaled_config["TICKER_CONFIG"]["scroll_threshold"]
                            ticker_x = SCREEN_WIDTH if should_scroll else (SCREEN_WIDTH - ticker_width) // 2

            # Handle non-scrolling alerts, this likely won't last long.
            elif not should_scroll and len(alert_list) > 1:
                current_time = pygame.time.get_ticks()
                if current_time - ticker_start_time > 15000:  # 15 seconds per display
                    ticker_scroll_count += 1
                    if len(alert_list) >= 3:
                        required_displays = 1
                    else:
                        required_displays = 2
                    if ticker_scroll_count >= required_displays:
                        ticker_scroll_count = 0  # Reset counter
                        current_alert_index = (current_alert_index + 1) % len(alert_list)
                        current_alert = alert_list[current_alert_index]

                        # Update everything for the new alert
                        warning_text = current_alert['event_upper']
                        ticker_text_content = current_alert['ticker_text']

                        if current_alert['alert_level'] == "ALERT":
                            current_bar_texture, current_alert_level = alert_bar_texture, "ALERT"
                        else:
                            current_bar_texture, current_alert_level = watch_bar_texture, "WATCH"

                        ticker_surface = ticker_font.render(ticker_text_content, True, scaled_config["TICKER_CONFIG"]["color"])
                        ticker_width = ticker_surface.get_width()
                        should_scroll = ticker_width > scaled_config["TICKER_CONFIG"]["scroll_threshold"]
                        ticker_x = SCREEN_WIDTH if should_scroll else (SCREEN_WIDTH - ticker_width) // 2
                    ticker_start_time = current_time
            screen.blit(ticker_surface, (ticker_x, scaled_config["TICKER_CONFIG"]["position_y"]))

        pygame.display.flip()
        clock.tick(TARGET_FPS)

    print("Stopping thread...")
    stop_event.set()
    weather_worker.join(timeout=2.0)
    if weather_worker.is_alive():
        print("Thread was prematurely amputated!")
    else:
        print("Exited normally.")
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
