from .battery import get_battery, set_battery_mode, set_overnight, set_usb_charging
from .cooling import get_fans, get_thermals, set_fan_mode, set_fan_speed
from .gpu import deactivate_dgpu, get_gpu, set_gpu_mode, set_gpu_oc
from .history import update as update_history
from .input import get_input, set_backlight, set_fn_lock
from .lighting import (
    apply_theme_color,
    get_lighting,
    install_permissions,
    permissions_installed,
    set_color,
    set_effect,
    set_key_group,
    set_key_map,
    set_logo,
    set_model_override,
    set_power as set_lighting_power,
    set_theme_sync,
)
from .lighting import set_brightness as set_lighting_brightness
from .power import get_power, is_custom_mode, set_power, set_ppt, sync_power_profiles
from .system import get_system
