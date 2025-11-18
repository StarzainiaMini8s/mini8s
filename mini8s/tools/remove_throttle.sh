#!/bin/bash

# Mini8s CPU Throttle Removal Tool
# Restores CPU frequencies to maximum available

echo "Remove CPU Throttle (for Mini8s v0.3.99)"
echo ""

# Check if running with root privileges
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run with sudo/root privileges to modify CPU frequencies."
    echo "Please run: sudo $0"
    exit 1
fi

# Get the maximum frequency from the first CPU
MAX_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq 2>/dev/null)

if [ -z "$MAX_FREQ" ]; then
    echo "ERROR: Unable to read CPU frequency information."
    echo "Make sure your system supports cpufreq and that nothing gets in the way of this!"
    exit 1
fi

# Get the minimum frequency from the first CPU
MIN_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq 2>/dev/null)

echo "Restoring CPU frequencies to normal..."

# Restore all CPUs to maximum frequency
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do
    if [ -f "$cpu" ]; then
        echo "$MAX_FREQ" > "$cpu" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo "WARNING: Failed to restore frequency for $cpu"
        fi
    fi
done

# Restore minimum frequency to original value
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_min_freq; do
    if [ -f "$cpu" ]; then
        echo "$MIN_FREQ" > "$cpu" 2>/dev/null
    fi
done

# Convert frequency to MHz for display
MAX_FREQ_MHZ=$((MAX_FREQ / 1000))

echo "CPU frequencies restored to maximum: ${MAX_FREQ_MHZ} MHz"
echo "Throttle removed successfully!"
