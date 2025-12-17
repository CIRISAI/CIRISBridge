"""
CIRIS Infrastructure Status Display - Pimoroni Galactic Unicorn
53x11 RGB LED Matrix (583 LEDs) - ONE METRIC PER LED

Each LED represents a single metric with color-coded status:
  GREEN  = healthy/OK/low
  YELLOW = warning/degraded/medium
  RED    = error/critical/high
  BLUE   = informational/unknown
  OFF    = no data/disabled

Layout (53 columns x 11 rows):
  Row 0:     Critical alerts (53 metrics)
  Row 1-2:   Service health - billing, proxy, lens, dns (106 metrics)
  Row 3-4:   Node metrics - US and EU (106 metrics)
  Row 5-6:   Agent/manager status (106 metrics)
  Row 7-8:   Error rates and logs (106 metrics)
  Row 9-10:  System metrics - cert, disk, replication (106 metrics)
"""

import network
import urequests
import time
import json
from galactic import GalacticUnicorn
from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN

# =============================================================================
# CONFIGURATION
# =============================================================================

WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

LENS_API_URL = "https://lens.ciris-services-1.ai"
LENS_API_TOKEN = "YOUR_CIRISLENS_SERVICE_TOKEN"

BILLING_US_URL = "https://billing1.ciris-services-1.ai"
BILLING_EU_URL = "https://billing1.ciris-services-2.ai"
PROXY_US_URL = "https://proxy1.ciris-services-1.ai"
PROXY_EU_URL = "https://proxy1.ciris-services-2.ai"

REFRESH_INTERVAL_MS = 30000  # 30 seconds
BRIGHTNESS = 0.5  # 0.0 to 1.0

# =============================================================================
# DISPLAY SETUP
# =============================================================================

gu = GalacticUnicorn()
graphics = PicoGraphics(DISPLAY_GALACTIC_UNICORN)

WIDTH = GalacticUnicorn.WIDTH   # 53
HEIGHT = GalacticUnicorn.HEIGHT  # 11

# Color definitions (R, G, B)
COLOR_OFF = graphics.create_pen(0, 0, 0)
COLOR_GREEN = graphics.create_pen(0, 255, 0)
COLOR_YELLOW = graphics.create_pen(255, 200, 0)
COLOR_RED = graphics.create_pen(255, 0, 0)
COLOR_BLUE = graphics.create_pen(0, 100, 255)
COLOR_PURPLE = graphics.create_pen(150, 0, 255)
COLOR_WHITE = graphics.create_pen(255, 255, 255)
COLOR_DIM_GREEN = graphics.create_pen(0, 50, 0)
COLOR_DIM_RED = graphics.create_pen(50, 0, 0)

# =============================================================================
# METRIC DEFINITIONS - 583 metrics mapped to LEDs
# =============================================================================

# Each metric: (name, fetch_function, thresholds)
# Thresholds: (warn_threshold, crit_threshold) or None for boolean

class MetricState:
    """Holds current state of all metrics"""
    def __init__(self):
        self.data = {}
        self.last_update = 0

    def set(self, key, value):
        self.data[key] = value

    def get(self, key, default=None):
        return self.data.get(key, default)

state = MetricState()

# =============================================================================
# LED GRID MAPPING
# Each position (x, y) maps to exactly ONE metric
# =============================================================================

def get_led_mapping():
    """
    Returns dict mapping (x, y) -> metric_config
    metric_config = {
        'name': str,
        'type': 'health'|'gauge'|'counter'|'boolean',
        'source': str,  # API endpoint or derived
        'key': str,     # JSON path to value
        'thresholds': (warn, crit) or None for boolean
    }
    """
    mapping = {}

    # =========================================================================
    # ROW 0: Critical Alerts (53 LEDs)
    # =========================================================================
    row = 0

    # Columns 0-7: Service Health (8 LEDs)
    mapping[(0, row)] = {'name': 'billing_us_health', 'type': 'health', 'source': 'billing_us'}
    mapping[(1, row)] = {'name': 'billing_eu_health', 'type': 'health', 'source': 'billing_eu'}
    mapping[(2, row)] = {'name': 'proxy_us_health', 'type': 'health', 'source': 'proxy_us'}
    mapping[(3, row)] = {'name': 'proxy_eu_health', 'type': 'health', 'source': 'proxy_eu'}
    mapping[(4, row)] = {'name': 'lens_health', 'type': 'health', 'source': 'lens'}
    mapping[(5, row)] = {'name': 'postgres_us_health', 'type': 'health', 'source': 'db_us'}
    mapping[(6, row)] = {'name': 'postgres_eu_health', 'type': 'health', 'source': 'db_eu'}
    mapping[(7, row)] = {'name': 'replication_health', 'type': 'health', 'source': 'replication'}

    # Columns 8-15: Error Counts (8 LEDs) - gauge with thresholds
    mapping[(8, row)] = {'name': 'billing_errors_1h', 'type': 'gauge', 'source': 'lens_stats', 'key': 'billing_errors_1h', 'thresholds': (5, 20)}
    mapping[(9, row)] = {'name': 'proxy_errors_1h', 'type': 'gauge', 'source': 'lens_stats', 'key': 'proxy_errors_1h', 'thresholds': (5, 20)}
    mapping[(10, row)] = {'name': 'lens_errors_1h', 'type': 'gauge', 'source': 'lens_stats', 'key': 'lens_errors_1h', 'thresholds': (5, 20)}
    mapping[(11, row)] = {'name': 'db_errors_1h', 'type': 'gauge', 'source': 'lens_stats', 'key': 'db_errors_1h', 'thresholds': (1, 5)}
    mapping[(12, row)] = {'name': 'total_errors_1h', 'type': 'gauge', 'source': 'lens_stats', 'key': 'total_errors_1h', 'thresholds': (10, 50)}
    mapping[(13, row)] = {'name': 'total_errors_24h', 'type': 'gauge', 'source': 'lens_stats', 'key': 'total_errors_24h', 'thresholds': (50, 200)}
    mapping[(14, row)] = {'name': 'warnings_1h', 'type': 'gauge', 'source': 'lens_stats', 'key': 'warnings_1h', 'thresholds': (20, 100)}
    mapping[(15, row)] = {'name': 'warnings_24h', 'type': 'gauge', 'source': 'lens_stats', 'key': 'warnings_24h', 'thresholds': (100, 500)}

    # Columns 16-23: Certificate Status (8 LEDs) - days until expiry
    mapping[(16, row)] = {'name': 'cert_billing_us', 'type': 'gauge', 'source': 'certs', 'key': 'billing_us_days', 'thresholds': (30, 14), 'invert': True}
    mapping[(17, row)] = {'name': 'cert_billing_eu', 'type': 'gauge', 'source': 'certs', 'key': 'billing_eu_days', 'thresholds': (30, 14), 'invert': True}
    mapping[(18, row)] = {'name': 'cert_proxy_us', 'type': 'gauge', 'source': 'certs', 'key': 'proxy_us_days', 'thresholds': (30, 14), 'invert': True}
    mapping[(19, row)] = {'name': 'cert_proxy_eu', 'type': 'gauge', 'source': 'certs', 'key': 'proxy_eu_days', 'thresholds': (30, 14), 'invert': True}
    mapping[(20, row)] = {'name': 'cert_lens', 'type': 'gauge', 'source': 'certs', 'key': 'lens_days', 'thresholds': (30, 14), 'invert': True}
    mapping[(21, row)] = {'name': 'cert_agents', 'type': 'gauge', 'source': 'certs', 'key': 'agents_days', 'thresholds': (30, 14), 'invert': True}
    mapping[(22, row)] = {'name': 'cert_root_us', 'type': 'gauge', 'source': 'certs', 'key': 'root_us_days', 'thresholds': (30, 14), 'invert': True}
    mapping[(23, row)] = {'name': 'cert_root_eu', 'type': 'gauge', 'source': 'certs', 'key': 'root_eu_days', 'thresholds': (30, 14), 'invert': True}

    # Columns 24-31: Disk Usage (8 LEDs) - percentage
    mapping[(24, row)] = {'name': 'disk_us_root', 'type': 'gauge', 'source': 'system', 'key': 'disk_us_pct', 'thresholds': (70, 85)}
    mapping[(25, row)] = {'name': 'disk_eu_root', 'type': 'gauge', 'source': 'system', 'key': 'disk_eu_pct', 'thresholds': (70, 85)}
    mapping[(26, row)] = {'name': 'disk_us_docker', 'type': 'gauge', 'source': 'system', 'key': 'disk_us_docker_pct', 'thresholds': (70, 85)}
    mapping[(27, row)] = {'name': 'disk_eu_docker', 'type': 'gauge', 'source': 'system', 'key': 'disk_eu_docker_pct', 'thresholds': (70, 85)}
    mapping[(28, row)] = {'name': 'disk_us_postgres', 'type': 'gauge', 'source': 'system', 'key': 'disk_us_pg_pct', 'thresholds': (60, 80)}
    mapping[(29, row)] = {'name': 'disk_eu_postgres', 'type': 'gauge', 'source': 'system', 'key': 'disk_eu_pg_pct', 'thresholds': (60, 80)}
    mapping[(30, row)] = {'name': 'disk_us_logs', 'type': 'gauge', 'source': 'system', 'key': 'disk_us_logs_pct', 'thresholds': (50, 75)}
    mapping[(31, row)] = {'name': 'disk_eu_logs', 'type': 'gauge', 'source': 'system', 'key': 'disk_eu_logs_pct', 'thresholds': (50, 75)}

    # Columns 32-39: Replication Status (8 LEDs)
    mapping[(32, row)] = {'name': 'repl_us_to_eu_active', 'type': 'boolean', 'source': 'replication', 'key': 'us_to_eu_active'}
    mapping[(33, row)] = {'name': 'repl_eu_to_us_active', 'type': 'boolean', 'source': 'replication', 'key': 'eu_to_us_active'}
    mapping[(34, row)] = {'name': 'repl_us_to_eu_lag', 'type': 'gauge', 'source': 'replication', 'key': 'us_to_eu_lag_sec', 'thresholds': (30, 120)}
    mapping[(35, row)] = {'name': 'repl_eu_to_us_lag', 'type': 'gauge', 'source': 'replication', 'key': 'eu_to_us_lag_sec', 'thresholds': (30, 120)}
    mapping[(36, row)] = {'name': 'repl_slot_us_active', 'type': 'boolean', 'source': 'replication', 'key': 'slot_us_active'}
    mapping[(37, row)] = {'name': 'repl_slot_eu_active', 'type': 'boolean', 'source': 'replication', 'key': 'slot_eu_active'}
    mapping[(38, row)] = {'name': 'repl_wal_us_mb', 'type': 'gauge', 'source': 'replication', 'key': 'wal_us_mb', 'thresholds': (100, 200)}
    mapping[(39, row)] = {'name': 'repl_wal_eu_mb', 'type': 'gauge', 'source': 'replication', 'key': 'wal_eu_mb', 'thresholds': (100, 200)}

    # Columns 40-47: Legacy Server Status (8 LEDs)
    mapping[(40, row)] = {'name': 'legacy_llm_health', 'type': 'health', 'source': 'legacy_llm'}
    mapping[(41, row)] = {'name': 'legacy_billing_health', 'type': 'health', 'source': 'legacy_billing'}
    mapping[(42, row)] = {'name': 'legacy_llm_traffic', 'type': 'boolean', 'source': 'legacy', 'key': 'llm_has_traffic'}
    mapping[(43, row)] = {'name': 'legacy_billing_traffic', 'type': 'boolean', 'source': 'legacy', 'key': 'billing_has_traffic'}
    mapping[(44, row)] = {'name': 'legacy_cirisnode0', 'type': 'boolean', 'source': 'legacy', 'key': 'cirisnode0_stopped'}
    mapping[(45, row)] = {'name': 'dns_cutover_ready', 'type': 'boolean', 'source': 'legacy', 'key': 'dns_cutover_ready'}
    mapping[(46, row)] = {'name': 'legacy_decom_safe', 'type': 'boolean', 'source': 'legacy', 'key': 'decom_safe'}
    mapping[(47, row)] = {'name': 'migration_complete', 'type': 'boolean', 'source': 'legacy', 'key': 'migration_complete'}

    # Columns 48-52: Heartbeat/Scheduler (5 LEDs)
    mapping[(48, row)] = {'name': 'heartbeat_us_ok', 'type': 'boolean', 'source': 'heartbeat', 'key': 'us_ok'}
    mapping[(49, row)] = {'name': 'heartbeat_eu_ok', 'type': 'boolean', 'source': 'heartbeat', 'key': 'eu_ok'}
    mapping[(50, row)] = {'name': 'scheduler_us_ok', 'type': 'boolean', 'source': 'scheduler', 'key': 'us_ok'}
    mapping[(51, row)] = {'name': 'scheduler_eu_ok', 'type': 'boolean', 'source': 'scheduler', 'key': 'eu_ok'}
    mapping[(52, row)] = {'name': 'alerting_ok', 'type': 'boolean', 'source': 'alerting', 'key': 'ok'}

    # =========================================================================
    # ROW 1-2: Service Metrics - Billing (106 LEDs)
    # =========================================================================
    for row in [1, 2]:
        base_col = 0 if row == 1 else 0
        region = 'us' if row == 1 else 'eu'

        # Request metrics (columns 0-15)
        mapping[(0, row)] = {'name': f'billing_{region}_requests_1m', 'type': 'gauge', 'source': f'billing_{region}', 'key': 'requests_1m', 'thresholds': (100, 500)}
        mapping[(1, row)] = {'name': f'billing_{region}_requests_5m', 'type': 'gauge', 'source': f'billing_{region}', 'key': 'requests_5m', 'thresholds': (500, 2000)}
        mapping[(2, row)] = {'name': f'billing_{region}_requests_1h', 'type': 'gauge', 'source': f'billing_{region}', 'key': 'requests_1h', 'thresholds': (5000, 20000)}
        mapping[(3, row)] = {'name': f'billing_{region}_success_rate', 'type': 'gauge', 'source': f'billing_{region}', 'key': 'success_rate', 'thresholds': (95, 99), 'invert': True}
        mapping[(4, row)] = {'name': f'billing_{region}_latency_p50', 'type': 'gauge', 'source': f'billing_{region}', 'key': 'latency_p50_ms', 'thresholds': (100, 500)}
        mapping[(5, row)] = {'name': f'billing_{region}_latency_p95', 'type': 'gauge', 'source': f'billing_{region}', 'key': 'latency_p95_ms', 'thresholds': (500, 2000)}
        mapping[(6, row)] = {'name': f'billing_{region}_latency_p99', 'type': 'gauge', 'source': f'billing_{region}', 'key': 'latency_p99_ms', 'thresholds': (1000, 5000)}
        mapping[(7, row)] = {'name': f'billing_{region}_errors_1m', 'type': 'gauge', 'source': f'billing_{region}', 'key': 'errors_1m', 'thresholds': (1, 5)}

        # Database metrics (columns 8-15)
        mapping[(8, row)] = {'name': f'billing_{region}_db_connected', 'type': 'boolean', 'source': f'billing_{region}', 'key': 'db_connected'}
        mapping[(9, row)] = {'name': f'billing_{region}_db_pool_used', 'type': 'gauge', 'source': f'billing_{region}', 'key': 'db_pool_used', 'thresholds': (80, 95)}
        mapping[(10, row)] = {'name': f'billing_{region}_db_queries_1m', 'type': 'gauge', 'source': f'billing_{region}', 'key': 'db_queries_1m', 'thresholds': (1000, 5000)}
        mapping[(11, row)] = {'name': f'billing_{region}_db_slow_queries', 'type': 'gauge', 'source': f'billing_{region}', 'key': 'db_slow_queries', 'thresholds': (5, 20)}
        mapping[(12, row)] = {'name': f'billing_{region}_accounts_total', 'type': 'counter', 'source': f'billing_{region}', 'key': 'accounts_total'}
        mapping[(13, row)] = {'name': f'billing_{region}_accounts_active', 'type': 'counter', 'source': f'billing_{region}', 'key': 'accounts_active'}
        mapping[(14, row)] = {'name': f'billing_{region}_credits_total', 'type': 'counter', 'source': f'billing_{region}', 'key': 'credits_total'}
        mapping[(15, row)] = {'name': f'billing_{region}_charges_today', 'type': 'counter', 'source': f'billing_{region}', 'key': 'charges_today'}

        # Endpoint health (columns 16-31)
        endpoints = ['health', 'credit_check', 'charge', 'balance', 'signup', 'oauth', 'admin', 'metrics',
                     'webhook', 'refund', 'history', 'products', 'verify', 'status', 'config', 'keys']
        for i, ep in enumerate(endpoints):
            mapping[(16 + i, row)] = {'name': f'billing_{region}_ep_{ep}', 'type': 'health', 'source': f'billing_{region}_endpoints', 'key': ep}

        # Container metrics (columns 32-39)
        mapping[(32, row)] = {'name': f'billing_{region}_container_running', 'type': 'boolean', 'source': f'container_{region}', 'key': 'billing_running'}
        mapping[(33, row)] = {'name': f'billing_{region}_container_healthy', 'type': 'boolean', 'source': f'container_{region}', 'key': 'billing_healthy'}
        mapping[(34, row)] = {'name': f'billing_{region}_cpu_pct', 'type': 'gauge', 'source': f'container_{region}', 'key': 'billing_cpu', 'thresholds': (70, 90)}
        mapping[(35, row)] = {'name': f'billing_{region}_mem_pct', 'type': 'gauge', 'source': f'container_{region}', 'key': 'billing_mem', 'thresholds': (70, 90)}
        mapping[(36, row)] = {'name': f'billing_{region}_restarts', 'type': 'gauge', 'source': f'container_{region}', 'key': 'billing_restarts', 'thresholds': (1, 3)}
        mapping[(37, row)] = {'name': f'billing_{region}_uptime_hours', 'type': 'gauge', 'source': f'container_{region}', 'key': 'billing_uptime_h', 'thresholds': (1, 0.5), 'invert': True}
        mapping[(38, row)] = {'name': f'billing_{region}_image_latest', 'type': 'boolean', 'source': f'container_{region}', 'key': 'billing_latest'}
        mapping[(39, row)] = {'name': f'billing_{region}_network_ok', 'type': 'boolean', 'source': f'container_{region}', 'key': 'billing_network'}

        # Log metrics (columns 40-47)
        log_levels = ['debug', 'info', 'warning', 'error', 'critical']
        for i, level in enumerate(log_levels):
            mapping[(40 + i, row)] = {'name': f'billing_{region}_log_{level}_1h', 'type': 'gauge', 'source': f'logs_{region}', 'key': f'billing_{level}_1h', 'thresholds': (100, 500) if level == 'debug' else (50, 200) if level == 'info' else (10, 50) if level == 'warning' else (1, 5)}
        mapping[(45, row)] = {'name': f'billing_{region}_log_rate', 'type': 'gauge', 'source': f'logs_{region}', 'key': 'billing_rate_per_min', 'thresholds': (100, 500)}
        mapping[(46, row)] = {'name': f'billing_{region}_log_errors_trend', 'type': 'gauge', 'source': f'logs_{region}', 'key': 'billing_error_trend', 'thresholds': (0, 1)}  # -1, 0, 1
        mapping[(47, row)] = {'name': f'billing_{region}_log_anomaly', 'type': 'boolean', 'source': f'logs_{region}', 'key': 'billing_anomaly'}

        # Feature flags/config (columns 48-52)
        mapping[(48, row)] = {'name': f'billing_{region}_stripe_ok', 'type': 'boolean', 'source': f'billing_{region}_config', 'key': 'stripe_connected'}
        mapping[(49, row)] = {'name': f'billing_{region}_google_ok', 'type': 'boolean', 'source': f'billing_{region}_config', 'key': 'google_connected'}
        mapping[(50, row)] = {'name': f'billing_{region}_oauth_ok', 'type': 'boolean', 'source': f'billing_{region}_config', 'key': 'oauth_configured'}
        mapping[(51, row)] = {'name': f'billing_{region}_migrations_ok', 'type': 'boolean', 'source': f'billing_{region}_config', 'key': 'migrations_current'}
        mapping[(52, row)] = {'name': f'billing_{region}_version_ok', 'type': 'boolean', 'source': f'billing_{region}_config', 'key': 'version_match'}

    # =========================================================================
    # ROW 3-4: Service Metrics - Proxy (106 LEDs)
    # =========================================================================
    for row in [3, 4]:
        region = 'us' if row == 3 else 'eu'

        # Request metrics (columns 0-15)
        mapping[(0, row)] = {'name': f'proxy_{region}_requests_1m', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'requests_1m', 'thresholds': (50, 200)}
        mapping[(1, row)] = {'name': f'proxy_{region}_requests_5m', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'requests_5m', 'thresholds': (200, 800)}
        mapping[(2, row)] = {'name': f'proxy_{region}_requests_1h', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'requests_1h', 'thresholds': (2000, 8000)}
        mapping[(3, row)] = {'name': f'proxy_{region}_success_rate', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'success_rate', 'thresholds': (95, 99), 'invert': True}
        mapping[(4, row)] = {'name': f'proxy_{region}_latency_p50', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'latency_p50_ms', 'thresholds': (1000, 5000)}
        mapping[(5, row)] = {'name': f'proxy_{region}_latency_p95', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'latency_p95_ms', 'thresholds': (5000, 15000)}
        mapping[(6, row)] = {'name': f'proxy_{region}_latency_p99', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'latency_p99_ms', 'thresholds': (10000, 30000)}
        mapping[(7, row)] = {'name': f'proxy_{region}_errors_1m', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'errors_1m', 'thresholds': (1, 5)}

        # LLM Provider metrics (columns 8-23)
        providers = ['groq', 'together', 'openrouter', 'anthropic', 'openai', 'google', 'mistral', 'cohere']
        for i, provider in enumerate(providers):
            mapping[(8 + i, row)] = {'name': f'proxy_{region}_{provider}_ok', 'type': 'boolean', 'source': f'proxy_{region}_providers', 'key': f'{provider}_available'}
            mapping[(16 + i, row)] = {'name': f'proxy_{region}_{provider}_latency', 'type': 'gauge', 'source': f'proxy_{region}_providers', 'key': f'{provider}_latency_ms', 'thresholds': (2000, 10000)}

        # Billing integration (columns 24-31)
        mapping[(24, row)] = {'name': f'proxy_{region}_billing_ok', 'type': 'boolean', 'source': f'proxy_{region}', 'key': 'billing_connected'}
        mapping[(25, row)] = {'name': f'proxy_{region}_credit_checks_1m', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'credit_checks_1m', 'thresholds': (50, 200)}
        mapping[(26, row)] = {'name': f'proxy_{region}_credit_check_latency', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'credit_check_latency_ms', 'thresholds': (100, 500)}
        mapping[(27, row)] = {'name': f'proxy_{region}_charges_1m', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'charges_1m', 'thresholds': (50, 200)}
        mapping[(28, row)] = {'name': f'proxy_{region}_charge_latency', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'charge_latency_ms', 'thresholds': (100, 500)}
        mapping[(29, row)] = {'name': f'proxy_{region}_billing_errors', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'billing_errors_1h', 'thresholds': (1, 5)}
        mapping[(30, row)] = {'name': f'proxy_{region}_insufficient_credits', 'type': 'gauge', 'source': f'proxy_{region}', 'key': 'insufficient_credits_1h', 'thresholds': (10, 50)}
        mapping[(31, row)] = {'name': f'proxy_{region}_circuit_breaker', 'type': 'boolean', 'source': f'proxy_{region}', 'key': 'circuit_closed'}  # True = closed (good)

        # Container metrics (columns 32-39)
        mapping[(32, row)] = {'name': f'proxy_{region}_container_running', 'type': 'boolean', 'source': f'container_{region}', 'key': 'proxy_running'}
        mapping[(33, row)] = {'name': f'proxy_{region}_container_healthy', 'type': 'boolean', 'source': f'container_{region}', 'key': 'proxy_healthy'}
        mapping[(34, row)] = {'name': f'proxy_{region}_cpu_pct', 'type': 'gauge', 'source': f'container_{region}', 'key': 'proxy_cpu', 'thresholds': (70, 90)}
        mapping[(35, row)] = {'name': f'proxy_{region}_mem_pct', 'type': 'gauge', 'source': f'container_{region}', 'key': 'proxy_mem', 'thresholds': (70, 90)}
        mapping[(36, row)] = {'name': f'proxy_{region}_restarts', 'type': 'gauge', 'source': f'container_{region}', 'key': 'proxy_restarts', 'thresholds': (1, 3)}
        mapping[(37, row)] = {'name': f'proxy_{region}_uptime_hours', 'type': 'gauge', 'source': f'container_{region}', 'key': 'proxy_uptime_h', 'thresholds': (1, 0.5), 'invert': True}
        mapping[(38, row)] = {'name': f'proxy_{region}_image_latest', 'type': 'boolean', 'source': f'container_{region}', 'key': 'proxy_latest'}
        mapping[(39, row)] = {'name': f'proxy_{region}_network_ok', 'type': 'boolean', 'source': f'container_{region}', 'key': 'proxy_network'}

        # Log metrics (columns 40-47)
        for i, level in enumerate(['debug', 'info', 'warning', 'error', 'critical']):
            mapping[(40 + i, row)] = {'name': f'proxy_{region}_log_{level}_1h', 'type': 'gauge', 'source': f'logs_{region}', 'key': f'proxy_{level}_1h', 'thresholds': (100, 500) if level == 'debug' else (50, 200) if level == 'info' else (10, 50) if level == 'warning' else (1, 5)}
        mapping[(45, row)] = {'name': f'proxy_{region}_log_rate', 'type': 'gauge', 'source': f'logs_{region}', 'key': 'proxy_rate_per_min', 'thresholds': (100, 500)}
        mapping[(46, row)] = {'name': f'proxy_{region}_log_errors_trend', 'type': 'gauge', 'source': f'logs_{region}', 'key': 'proxy_error_trend', 'thresholds': (0, 1)}
        mapping[(47, row)] = {'name': f'proxy_{region}_log_anomaly', 'type': 'boolean', 'source': f'logs_{region}', 'key': 'proxy_anomaly'}

        # LogShipper metrics (columns 48-52)
        mapping[(48, row)] = {'name': f'proxy_{region}_shipper_ok', 'type': 'boolean', 'source': f'proxy_{region}_shipper', 'key': 'shipper_healthy'}
        mapping[(49, row)] = {'name': f'proxy_{region}_shipper_circuit', 'type': 'boolean', 'source': f'proxy_{region}_shipper', 'key': 'circuit_closed'}
        mapping[(50, row)] = {'name': f'proxy_{region}_shipper_buffer', 'type': 'gauge', 'source': f'proxy_{region}_shipper', 'key': 'buffer_pct', 'thresholds': (50, 80)}
        mapping[(51, row)] = {'name': f'proxy_{region}_shipper_dropped', 'type': 'gauge', 'source': f'proxy_{region}_shipper', 'key': 'dropped_1h', 'thresholds': (10, 100)}
        mapping[(52, row)] = {'name': f'proxy_{region}_shipper_backoff', 'type': 'gauge', 'source': f'proxy_{region}_shipper', 'key': 'backoff_sec', 'thresholds': (30, 300)}

    # =========================================================================
    # ROW 5-6: CIRISLens & Infrastructure (106 LEDs)
    # =========================================================================
    row = 5
    # Lens service metrics (columns 0-26)
    mapping[(0, row)] = {'name': 'lens_api_health', 'type': 'health', 'source': 'lens'}
    mapping[(1, row)] = {'name': 'lens_grafana_health', 'type': 'health', 'source': 'grafana'}
    mapping[(2, row)] = {'name': 'lens_db_health', 'type': 'health', 'source': 'lens_db'}
    mapping[(3, row)] = {'name': 'lens_requests_1m', 'type': 'gauge', 'source': 'lens', 'key': 'requests_1m', 'thresholds': (100, 500)}
    mapping[(4, row)] = {'name': 'lens_log_ingestion_rate', 'type': 'gauge', 'source': 'lens', 'key': 'log_ingestion_per_min', 'thresholds': (1000, 5000)}
    mapping[(5, row)] = {'name': 'lens_total_logs', 'type': 'counter', 'source': 'lens', 'key': 'total_logs'}
    mapping[(6, row)] = {'name': 'lens_total_agents', 'type': 'counter', 'source': 'lens', 'key': 'total_agents'}
    mapping[(7, row)] = {'name': 'lens_active_agents', 'type': 'counter', 'source': 'lens', 'key': 'active_agents'}
    mapping[(8, row)] = {'name': 'lens_total_managers', 'type': 'counter', 'source': 'lens', 'key': 'total_managers'}
    mapping[(9, row)] = {'name': 'lens_db_size_gb', 'type': 'gauge', 'source': 'lens', 'key': 'db_size_gb', 'thresholds': (5, 10)}
    mapping[(10, row)] = {'name': 'lens_retention_days', 'type': 'gauge', 'source': 'lens', 'key': 'retention_days', 'thresholds': (7, 3), 'invert': True}

    # Grafana dashboards (columns 11-20)
    dashboards = ['main', 'services', 'billing', 'errors', 'logs', 'managers', 'traces', 'service_logs', 'public', 'telemetry']
    for i, dash in enumerate(dashboards):
        mapping[(11 + i, row)] = {'name': f'grafana_dash_{dash}', 'type': 'boolean', 'source': 'grafana', 'key': f'dash_{dash}_ok'}

    # Alerting (columns 21-26)
    mapping[(21, row)] = {'name': 'alerting_enabled', 'type': 'boolean', 'source': 'alerting', 'key': 'enabled'}
    mapping[(22, row)] = {'name': 'alerts_firing', 'type': 'gauge', 'source': 'alerting', 'key': 'firing_count', 'thresholds': (1, 5)}
    mapping[(23, row)] = {'name': 'alerts_pending', 'type': 'gauge', 'source': 'alerting', 'key': 'pending_count', 'thresholds': (3, 10)}
    mapping[(24, row)] = {'name': 'alert_heartbeat_us', 'type': 'boolean', 'source': 'alerting', 'key': 'heartbeat_us_ok'}
    mapping[(25, row)] = {'name': 'alert_heartbeat_eu', 'type': 'boolean', 'source': 'alerting', 'key': 'heartbeat_eu_ok'}
    mapping[(26, row)] = {'name': 'alert_notification_ok', 'type': 'boolean', 'source': 'alerting', 'key': 'notification_channel_ok'}

    # Caddy/TLS (columns 27-34)
    mapping[(27, row)] = {'name': 'caddy_us_health', 'type': 'health', 'source': 'caddy_us'}
    mapping[(28, row)] = {'name': 'caddy_eu_health', 'type': 'health', 'source': 'caddy_eu'}
    mapping[(29, row)] = {'name': 'caddy_us_requests_1m', 'type': 'gauge', 'source': 'caddy_us', 'key': 'requests_1m', 'thresholds': (500, 2000)}
    mapping[(30, row)] = {'name': 'caddy_eu_requests_1m', 'type': 'gauge', 'source': 'caddy_eu', 'key': 'requests_1m', 'thresholds': (500, 2000)}
    mapping[(31, row)] = {'name': 'caddy_us_errors_1m', 'type': 'gauge', 'source': 'caddy_us', 'key': 'errors_1m', 'thresholds': (5, 20)}
    mapping[(32, row)] = {'name': 'caddy_eu_errors_1m', 'type': 'gauge', 'source': 'caddy_eu', 'key': 'errors_1m', 'thresholds': (5, 20)}
    mapping[(33, row)] = {'name': 'tls_handshake_us', 'type': 'gauge', 'source': 'caddy_us', 'key': 'tls_handshake_ms', 'thresholds': (100, 500)}
    mapping[(34, row)] = {'name': 'tls_handshake_eu', 'type': 'gauge', 'source': 'caddy_eu', 'key': 'tls_handshake_ms', 'thresholds': (100, 500)}

    # DNS (columns 35-42)
    mapping[(35, row)] = {'name': 'dns_us_health', 'type': 'health', 'source': 'dns_us'}
    mapping[(36, row)] = {'name': 'dns_eu_health', 'type': 'health', 'source': 'dns_eu'}
    mapping[(37, row)] = {'name': 'dns_queries_1m', 'type': 'gauge', 'source': 'dns', 'key': 'queries_1m', 'thresholds': (100, 500)}
    mapping[(38, row)] = {'name': 'dns_cache_hit_rate', 'type': 'gauge', 'source': 'dns', 'key': 'cache_hit_pct', 'thresholds': (80, 95), 'invert': True}
    mapping[(39, row)] = {'name': 'dns_resolution_time', 'type': 'gauge', 'source': 'dns', 'key': 'resolution_ms', 'thresholds': (50, 200)}
    mapping[(40, row)] = {'name': 'redis_us_health', 'type': 'health', 'source': 'redis_us'}
    mapping[(41, row)] = {'name': 'redis_us_memory_pct', 'type': 'gauge', 'source': 'redis_us', 'key': 'memory_pct', 'thresholds': (70, 90)}
    mapping[(42, row)] = {'name': 'redis_us_connections', 'type': 'gauge', 'source': 'redis_us', 'key': 'connections', 'thresholds': (50, 100)}

    # PgBouncer (columns 43-48)
    mapping[(43, row)] = {'name': 'pgbouncer_us_health', 'type': 'health', 'source': 'pgbouncer_us'}
    mapping[(44, row)] = {'name': 'pgbouncer_eu_health', 'type': 'health', 'source': 'pgbouncer_eu'}
    mapping[(45, row)] = {'name': 'pgbouncer_us_active', 'type': 'gauge', 'source': 'pgbouncer_us', 'key': 'active_conns', 'thresholds': (20, 40)}
    mapping[(46, row)] = {'name': 'pgbouncer_eu_active', 'type': 'gauge', 'source': 'pgbouncer_eu', 'key': 'active_conns', 'thresholds': (20, 40)}
    mapping[(47, row)] = {'name': 'pgbouncer_us_waiting', 'type': 'gauge', 'source': 'pgbouncer_us', 'key': 'waiting_conns', 'thresholds': (5, 15)}
    mapping[(48, row)] = {'name': 'pgbouncer_eu_waiting', 'type': 'gauge', 'source': 'pgbouncer_eu', 'key': 'waiting_conns', 'thresholds': (5, 15)}

    # System load (columns 49-52)
    mapping[(49, row)] = {'name': 'load_us_1m', 'type': 'gauge', 'source': 'system_us', 'key': 'load_1m', 'thresholds': (2, 4)}
    mapping[(50, row)] = {'name': 'load_eu_1m', 'type': 'gauge', 'source': 'system_eu', 'key': 'load_1m', 'thresholds': (2, 4)}
    mapping[(51, row)] = {'name': 'memory_us_pct', 'type': 'gauge', 'source': 'system_us', 'key': 'memory_pct', 'thresholds': (70, 85)}
    mapping[(52, row)] = {'name': 'memory_eu_pct', 'type': 'gauge', 'source': 'system_eu', 'key': 'memory_pct', 'thresholds': (70, 85)}

    # Row 6: More infrastructure and agents
    row = 6
    # Agent metrics (columns 0-26)
    for i in range(27):
        mapping[(i, row)] = {'name': f'agent_{i}_health', 'type': 'health', 'source': 'agents', 'key': f'agent_{i}'}

    # Manager metrics (columns 27-36)
    for i in range(10):
        mapping[(27 + i, row)] = {'name': f'manager_{i}_health', 'type': 'health', 'source': 'managers', 'key': f'manager_{i}'}

    # Covenant metrics (columns 37-52)
    mapping[(37, row)] = {'name': 'wbd_pending', 'type': 'gauge', 'source': 'covenant', 'key': 'wbd_pending', 'thresholds': (5, 20)}
    mapping[(38, row)] = {'name': 'wbd_total', 'type': 'counter', 'source': 'covenant', 'key': 'wbd_total'}
    mapping[(39, row)] = {'name': 'pdma_pending', 'type': 'gauge', 'source': 'covenant', 'key': 'pdma_pending', 'thresholds': (3, 10)}
    mapping[(40, row)] = {'name': 'pdma_total', 'type': 'counter', 'source': 'covenant', 'key': 'pdma_total'}
    mapping[(41, row)] = {'name': 'pdma_avg_risk', 'type': 'gauge', 'source': 'covenant', 'key': 'pdma_avg_risk', 'thresholds': (0.5, 0.8)}
    mapping[(42, row)] = {'name': 'creator_ledger_entries', 'type': 'counter', 'source': 'covenant', 'key': 'creator_entries'}
    mapping[(43, row)] = {'name': 'sunset_pending', 'type': 'gauge', 'source': 'covenant', 'key': 'sunset_pending', 'thresholds': (1, 5)}
    mapping[(44, row)] = {'name': 'sunset_deferred', 'type': 'gauge', 'source': 'covenant', 'key': 'sunset_deferred', 'thresholds': (3, 10)}
    mapping[(45, row)] = {'name': 'compliance_score', 'type': 'gauge', 'source': 'covenant', 'key': 'avg_compliance', 'thresholds': (0.9, 0.95), 'invert': True}
    mapping[(46, row)] = {'name': 'agents_covenant_enabled', 'type': 'counter', 'source': 'covenant', 'key': 'agents_enabled'}
    mapping[(47, row)] = {'name': 'agents_wbd_enabled', 'type': 'counter', 'source': 'covenant', 'key': 'wbd_enabled'}
    mapping[(48, row)] = {'name': 'agents_pdma_enabled', 'type': 'counter', 'source': 'covenant', 'key': 'pdma_enabled'}
    mapping[(49, row)] = {'name': 'principle_conflicts', 'type': 'gauge', 'source': 'covenant', 'key': 'conflicts_24h', 'thresholds': (5, 20)}
    mapping[(50, row)] = {'name': 'stakeholder_impacts', 'type': 'counter', 'source': 'covenant', 'key': 'stakeholder_impacts'}
    mapping[(51, row)] = {'name': 'covenant_version', 'type': 'counter', 'source': 'covenant', 'key': 'version_count'}
    mapping[(52, row)] = {'name': 'covenant_health', 'type': 'health', 'source': 'covenant'}

    # =========================================================================
    # ROW 7-10: Reserved for expansion / per-request metrics / traces
    # =========================================================================
    for row in range(7, 11):
        for col in range(53):
            if (col, row) not in mapping:
                mapping[(col, row)] = {'name': f'reserved_{col}_{row}', 'type': 'reserved', 'source': 'none'}

    return mapping


# =============================================================================
# DATA FETCHING
# =============================================================================

def connect_wifi():
    """Connect to WiFi network"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print(f"Connecting to {WIFI_SSID}...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        timeout = 30
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1

    if wlan.isconnected():
        print(f"Connected! IP: {wlan.ifconfig()[0]}")
        return True
    else:
        print("WiFi connection failed")
        return False


def fetch_health(url, timeout=5):
    """Fetch health endpoint and return True if healthy"""
    try:
        response = urequests.get(f"{url}/health", timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            response.close()
            return data.get('status') == 'healthy' or data.get('database') == 'connected'
        elif response.status_code == 401:
            # Proxy returns 401 for unauthenticated /health - but it's up
            response.close()
            return True
        response.close()
        return False
    except Exception as e:
        print(f"Health check failed for {url}: {e}")
        return False


def fetch_lens_stats():
    """Fetch statistics from CIRISLens API"""
    try:
        headers = {'Authorization': f'Bearer {LENS_API_TOKEN}'}
        response = urequests.get(
            f"{LENS_API_URL}/lens-api/api/admin/stats",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            response.close()
            return data
        response.close()
        return {}
    except Exception as e:
        print(f"Lens stats fetch failed: {e}")
        return {}


def fetch_all_metrics():
    """Fetch all metrics and update state"""
    print("Fetching metrics...")

    # Health checks
    state.set('billing_us_health', fetch_health(BILLING_US_URL))
    state.set('billing_eu_health', fetch_health(BILLING_EU_URL))
    state.set('proxy_us_health', fetch_health(PROXY_US_URL))
    state.set('proxy_eu_health', fetch_health(PROXY_EU_URL))
    state.set('lens_health', fetch_health(LENS_API_URL))

    # Lens stats
    lens_data = fetch_lens_stats()
    if lens_data:
        for key, value in lens_data.items():
            state.set(f'lens_{key}', value)

    state.last_update = time.time()
    print(f"Metrics updated at {state.last_update}")


# =============================================================================
# DISPLAY RENDERING
# =============================================================================

def get_color_for_metric(metric_config, value):
    """Determine LED color based on metric type and value"""

    if value is None:
        return COLOR_BLUE  # No data

    metric_type = metric_config.get('type', 'unknown')

    if metric_type == 'health' or metric_type == 'boolean':
        # Boolean: True = green, False = red
        return COLOR_GREEN if value else COLOR_RED

    elif metric_type == 'gauge':
        thresholds = metric_config.get('thresholds')
        if thresholds:
            warn, crit = thresholds
            invert = metric_config.get('invert', False)

            if invert:
                # Lower is worse (e.g., cert days remaining)
                if value <= crit:
                    return COLOR_RED
                elif value <= warn:
                    return COLOR_YELLOW
                else:
                    return COLOR_GREEN
            else:
                # Higher is worse (e.g., error count)
                if value >= crit:
                    return COLOR_RED
                elif value >= warn:
                    return COLOR_YELLOW
                else:
                    return COLOR_GREEN
        return COLOR_GREEN

    elif metric_type == 'counter':
        # Counters just show activity - dim green if > 0
        return COLOR_DIM_GREEN if value > 0 else COLOR_OFF

    elif metric_type == 'reserved':
        return COLOR_OFF

    return COLOR_BLUE  # Unknown


def render_display():
    """Render all metrics to the LED matrix"""
    mapping = get_led_mapping()

    graphics.set_pen(COLOR_OFF)
    graphics.clear()

    for (x, y), config in mapping.items():
        metric_name = config['name']
        source = config.get('source', '')
        key = config.get('key', metric_name)

        # Get value from state
        if config['type'] == 'health':
            value = state.get(f'{source}_health', state.get(metric_name))
        else:
            value = state.get(key, state.get(metric_name))

        # Get color
        color = get_color_for_metric(config, value)

        # Set pixel
        graphics.set_pen(color)
        graphics.pixel(x, y)

    gu.update(graphics)


def show_startup_animation():
    """Show a brief startup animation"""
    # Sweep green across display
    for x in range(WIDTH):
        graphics.set_pen(COLOR_OFF)
        graphics.clear()
        for y in range(HEIGHT):
            graphics.set_pen(COLOR_GREEN)
            graphics.pixel(x, y)
        gu.update(graphics)
        time.sleep_ms(20)

    # Flash all green then clear
    graphics.set_pen(COLOR_GREEN)
    graphics.clear()
    for x in range(WIDTH):
        for y in range(HEIGHT):
            graphics.pixel(x, y)
    gu.update(graphics)
    time.sleep_ms(500)

    graphics.set_pen(COLOR_OFF)
    graphics.clear()
    gu.update(graphics)


def show_error_pattern():
    """Show error pattern when data fetch fails"""
    # Red X pattern
    graphics.set_pen(COLOR_OFF)
    graphics.clear()
    graphics.set_pen(COLOR_RED)

    for i in range(min(WIDTH, HEIGHT)):
        graphics.pixel(i, i)
        graphics.pixel(WIDTH - 1 - i, i)

    gu.update(graphics)


# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    print("CIRIS Infrastructure Status Display")
    print(f"Display: {WIDTH}x{HEIGHT} = {WIDTH * HEIGHT} LEDs")

    # Set brightness
    gu.set_brightness(BRIGHTNESS)

    # Startup animation
    show_startup_animation()

    # Connect to WiFi
    if not connect_wifi():
        show_error_pattern()
        return

    # Initial fetch
    fetch_all_metrics()
    render_display()

    last_fetch = time.ticks_ms()

    while True:
        # Check for button presses
        if gu.is_pressed(GalacticUnicorn.SWITCH_BRIGHTNESS_UP):
            gu.adjust_brightness(+0.1)
        if gu.is_pressed(GalacticUnicorn.SWITCH_BRIGHTNESS_DOWN):
            gu.adjust_brightness(-0.1)
        if gu.is_pressed(GalacticUnicorn.SWITCH_A):
            # Force refresh
            fetch_all_metrics()
            render_display()
            last_fetch = time.ticks_ms()

        # Periodic refresh
        if time.ticks_diff(time.ticks_ms(), last_fetch) > REFRESH_INTERVAL_MS:
            try:
                fetch_all_metrics()
                render_display()
            except Exception as e:
                print(f"Update error: {e}")
                show_error_pattern()
            last_fetch = time.ticks_ms()

        time.sleep_ms(100)


if __name__ == "__main__":
    main()
