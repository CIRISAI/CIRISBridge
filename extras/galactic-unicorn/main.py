"""
CIRIS Infrastructure Status Display - Pimoroni Galactic Unicorn
Floating bubbles with scrolling labels

Colors:
  GREEN  = operational/healthy
  YELLOW = degraded/warning
  RED    = outage/critical
  BLUE   = unknown/no data
"""

import network
import urequests
import time
import random
import math
from galactic import GalacticUnicorn
from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN

# =============================================================================
# CONFIGURATION
# =============================================================================

WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
LENS_API_URL = "https://lens.ciris-services-1.ai"

try:
    from secrets import WIFI_SSID, WIFI_PASSWORD
except ImportError:
    pass

REFRESH_INTERVAL_MS = 30000
BRIGHTNESS = 0.5

# =============================================================================
# DISPLAY SETUP
# =============================================================================

gu = GalacticUnicorn()
graphics = PicoGraphics(DISPLAY_GALACTIC_UNICORN)

WIDTH = GalacticUnicorn.WIDTH   # 53
HEIGHT = GalacticUnicorn.HEIGHT  # 11

# Pre-create pens for performance
PEN_BLACK = graphics.create_pen(0, 0, 0)
PEN_GREEN = graphics.create_pen(0, 200, 0)
PEN_GREEN_DIM = graphics.create_pen(0, 80, 0)
PEN_GREEN_BRIGHT = graphics.create_pen(0, 255, 0)
PEN_YELLOW = graphics.create_pen(200, 160, 0)
PEN_YELLOW_DIM = graphics.create_pen(80, 60, 0)
PEN_YELLOW_BRIGHT = graphics.create_pen(255, 200, 0)
PEN_RED = graphics.create_pen(200, 0, 0)
PEN_RED_DIM = graphics.create_pen(80, 0, 0)
PEN_RED_BRIGHT = graphics.create_pen(255, 0, 0)
PEN_BLUE = graphics.create_pen(0, 60, 150)
PEN_BLUE_DIM = graphics.create_pen(0, 25, 60)
PEN_BLUE_BRIGHT = graphics.create_pen(0, 100, 200)

# =============================================================================
# METRICS STATE
# =============================================================================

metrics = {}  # name -> 'operational' | 'degraded' | 'outage' | None


def log(msg):
    print(f"[{time.ticks_ms()}] {msg}")


# =============================================================================
# BUBBLE CLASS
# =============================================================================

class Bubble:
    def __init__(self, metric_name, x=None):
        self.metric_name = metric_name
        self.label = metric_name.replace('_', ' ').upper()[:8]  # Short label
        self.x = float(x if x is not None else random.randint(0, WIDTH - 1))
        self.y = float(random.randint(0, HEIGHT - 1))
        self.r = random.uniform(2.0, 4.0)  # radius
        self.speed = random.uniform(0.03, 0.1)  # upward speed
        self.wobble = random.uniform(0, 6.28)  # phase offset
        self.wobble_speed = random.uniform(0.03, 0.1)
        self.text_offset = 0.0  # for scrolling text

    def update(self):
        # Float upward
        self.y -= self.speed

        # Gentle horizontal wobble
        self.wobble += self.wobble_speed
        self.x += math.sin(self.wobble) * 0.15

        # Scroll text
        self.text_offset += 0.1

        # Wrap around
        if self.y < -self.r:
            self.y = HEIGHT + self.r
            self.x = float(random.randint(3, WIDTH - 4))

        # Keep in bounds horizontally
        if self.x < 1:
            self.x = 1
        if self.x >= WIDTH - 1:
            self.x = WIDTH - 2

    def get_pens(self):
        """Get (dim, mid, bright) pens based on status"""
        status = metrics.get(self.metric_name)

        if status == 'operational':
            return (PEN_GREEN_DIM, PEN_GREEN, PEN_GREEN_BRIGHT)
        elif status == 'degraded':
            return (PEN_YELLOW_DIM, PEN_YELLOW, PEN_YELLOW_BRIGHT)
        elif status == 'outage':
            return (PEN_RED_DIM, PEN_RED, PEN_RED_BRIGHT)
        else:
            return (PEN_BLUE_DIM, PEN_BLUE, PEN_BLUE_BRIGHT)


# =============================================================================
# METRIC DEFINITIONS
# =============================================================================

METRIC_NAMES = [
    # Core services
    'billing_us', 'billing_eu', 'proxy_us', 'proxy_eu',
    # Infrastructure
    'infra_vultr', 'infra_hetzner', 'infra_github',
    # LLM Providers
    'llm_openrouter', 'llm_groq', 'llm_together',
    # Databases
    'db_lens', 'db_us', 'db_eu',
    # Auth
    'auth_google_oauth', 'auth_google_play',
    # Internal
    'internal_grafana', 'internal_brave',
    # Overall
    'overall',
]

bubbles = []


def setup_bubbles():
    global bubbles
    bubbles = []
    # Spread bubbles across the display
    for i, name in enumerate(METRIC_NAMES):
        x = (i * (WIDTH // len(METRIC_NAMES))) + random.randint(0, 3)
        bubbles.append(Bubble(name, x))
    log(f"Created {len(bubbles)} bubbles")


# =============================================================================
# NETWORKING
# =============================================================================

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        log(f"Connecting to {WIFI_SSID}...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        for i in range(30):
            if wlan.isconnected():
                break
            time.sleep(1)

    if wlan.isconnected():
        log(f"Connected! IP: {wlan.ifconfig()[0]}")
        return True
    else:
        log("WiFi failed!")
        return False


def fetch_metrics():
    """Fetch status from CIRISLens public API"""
    log("Fetching metrics...")

    try:
        response = urequests.get(
            f"{LENS_API_URL}/lens-api/api/v1/status",
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            response.close()

            # Overall
            metrics['overall'] = data.get('status', 'unknown')
            log(f"  Overall: {metrics['overall']}")

            # Regional services
            regions = data.get('regions', {})
            for region_key, region_data in regions.items():
                region = 'us' if 'us' in region_key.lower() else 'eu'
                services = region_data.get('services', {})

                for svc_name, svc_data in services.items():
                    key = f"{svc_name}_{region}"
                    metrics[key] = svc_data.get('status', 'unknown')

            # Infrastructure
            for name, info in data.get('infrastructure', {}).items():
                metrics[f'infra_{name}'] = info.get('status', 'unknown')

            # LLM Providers
            for name, info in data.get('llm_providers', {}).items():
                metrics[f'llm_{name}'] = info.get('status', 'unknown')

            # Database
            for name, info in data.get('database_providers', {}).items():
                # Simplify names like 'lens.postgresql' -> 'db_lens'
                simple = name.split('.')[0]
                metrics[f'db_{simple}'] = info.get('status', 'unknown')

            # Auth
            for name, info in data.get('auth_providers', {}).items():
                metrics[f'auth_{name}'] = info.get('status', 'unknown')

            # Internal
            for name, info in data.get('internal_providers', {}).items():
                simple = name.split('.')[0]
                metrics[f'internal_{simple}'] = info.get('status', 'unknown')

            log(f"  Loaded {len(metrics)} metrics")
            return True
        else:
            log(f"  ERROR: {response.status_code}")
            response.close()
            return False

    except Exception as e:
        log(f"  ERROR: {type(e).__name__}: {e}")
        return False


# =============================================================================
# RENDERING
# =============================================================================

@micropython.native
def draw_bubbles():
    """Draw all bubbles with glow effect"""
    # Clear to black
    graphics.set_pen(PEN_BLACK)
    graphics.clear()

    # Draw each bubble
    for bubble in bubbles:
        bubble.update()
        pen_dim, pen_mid, pen_bright = bubble.get_pens()

        cx, cy = int(bubble.x), int(bubble.y)
        radius = int(bubble.r)

        # Draw concentric rings for glow effect (fast version)
        # Outer ring (dim)
        for dy in range(-radius-1, radius+2):
            for dx in range(-radius-1, radius+2):
                px, py = cx + dx, cy + dy
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    dist_sq = dx*dx + dy*dy
                    r_sq = (radius+1) * (radius+1)
                    if dist_sq <= r_sq:
                        if dist_sq <= radius * radius * 0.3:
                            graphics.set_pen(pen_bright)
                        elif dist_sq <= radius * radius * 0.7:
                            graphics.set_pen(pen_mid)
                        else:
                            graphics.set_pen(pen_dim)
                        graphics.pixel(px, py)

    gu.update(graphics)


def show_connecting():
    """Show yellow bubbles while connecting"""
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()

    for i in range(5):
        x = 10 + i * 8
        graphics.set_pen(graphics.create_pen(255, 200, 0))
        graphics.pixel(x, 5)

    gu.update(graphics)


def show_error():
    """Show red X on error"""
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    graphics.set_pen(graphics.create_pen(255, 0, 0))

    for i in range(min(WIDTH, HEIGHT)):
        graphics.pixel(i, i)
        graphics.pixel(WIDTH - 1 - i, i)

    gu.update(graphics)


# =============================================================================
# MAIN
# =============================================================================

def main():
    log("=" * 40)
    log("CIRIS Status Bubbles")
    log(f"Display: {WIDTH}x{HEIGHT}")
    log("=" * 40)

    gu.set_brightness(BRIGHTNESS)
    show_connecting()

    if not connect_wifi():
        show_error()
        return

    setup_bubbles()

    if not fetch_metrics():
        log("Initial fetch failed, continuing anyway...")

    last_fetch = time.ticks_ms()

    log("Starting bubble animation...")

    while True:
        # Button controls
        if gu.is_pressed(GalacticUnicorn.SWITCH_BRIGHTNESS_UP):
            gu.adjust_brightness(+0.05)
        if gu.is_pressed(GalacticUnicorn.SWITCH_BRIGHTNESS_DOWN):
            gu.adjust_brightness(-0.05)
        if gu.is_pressed(GalacticUnicorn.SWITCH_A):
            fetch_metrics()
            last_fetch = time.ticks_ms()

        # Periodic refresh
        if time.ticks_diff(time.ticks_ms(), last_fetch) > REFRESH_INTERVAL_MS:
            fetch_metrics()
            last_fetch = time.ticks_ms()

        # Animate
        draw_bubbles()

        time.sleep_ms(50)  # ~20 FPS


if __name__ == "__main__":
    main()
