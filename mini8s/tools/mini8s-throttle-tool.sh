#!/bin/bash

# Mini8s CPU Throttling Tool for Mobile Devices! (v0.3.99)
# Linux-only tool for maximizing battery life by throttling CPU to lowest frequency

# Print welcome message
echo "Welcome to the Mini8s v0.3.99.1 Throttling Tool!"

# Sleep for 500ms
sleep 0.5

# Print warning and get user confirmation
echo ""
echo "⚠️ WARNING: This throttling tool is specifically designed for maximizing runtime of Mini8s v0.3.99.1 on battery powered devices, running this tool will THROTTLE YOUR CPU TO IT'S LOWEST POSSIBLE FREQUENCY!!! If you are aware of what this tool does and would like proceed, enter \"Y\", if otherwise, enter \"N\"."
echo ""
read -p "[Y/N]: " choice

# Convert to uppercase for comparison
choice=$(echo "$choice" | tr '[:lower:]' '[:upper:]')

if [ "$choice" != "Y" ]; then
    echo "Well then, fair enough!"
    exit 0
fi

# Check if running with root privileges
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run with sudo/root privileges to modify CPU frequencies."
    echo "Please run: sudo $0"
    exit 1
fi

echo ""
echo "Throttling CPU to lowest frequency..."

# Get the minimum frequency from the first CPU
MIN_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq 2>/dev/null)

if [ -z "$MIN_FREQ" ]; then
    echo "ERROR: Unable to read CPU frequency information."
    echo "Make sure your system supports cpufreq and the necessary drivers are loaded."
    exit 1
fi

# Set all CPUs to the minimum frequency
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do
    if [ -f "$cpu" ]; then
        echo "$MIN_FREQ" > "$cpu" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo "WARNING: Failed to set frequency for $cpu"
        fi
    fi
done

# Also set minimum frequency as the floor
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_min_freq; do
    if [ -f "$cpu" ]; then
        echo "$MIN_FREQ" > "$cpu" 2>/dev/null
    fi
done

# Convert frequency to MHz for display
FREQ_MHZ=$((MIN_FREQ / 1000))

echo "CPU has been throttled to: ${FREQ_MHZ} MHz"
echo ""

# Array of random messages
messages=(
    "Whatever you're dealing with, good luck!"
    "May your storm chasing experiences be safe and glorious!"
    "Looks like you may just be in the barrel today!"
    "Live it all, live it clearly!"
    "By HexagonMidis and Starzainia!"
)

# Select and print a random message
random_index=$((RANDOM % 5))
echo "${messages[$random_index]}"
