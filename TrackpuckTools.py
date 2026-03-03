#
# 6DoF HID Peripheral Navigation Addins For Autodesk Fusion 360
#

import adsk.core    # type: ignore[reportMissingImports]
import adsk.fusion  # type: ignore[reportMissingImports]
import traceback
import time
import math
import importlib
import importlib.util
import os
import sys
import zipfile
import glob
import queue
import struct
import threading


# -------------------------
# Logging
# -------------------------
def log(msg):
    None
    # try:
    #     import datetime
    #     desktop = os.path.expanduser("~/Desktop")
    #     with open(os.path.join(desktop, "TrackpuckTools.log"), "a") as f:
    #         f.write(f"{datetime.datetime.now()}: {msg}\n")
    # except:
    #     pass


# -------------------------
# Config
# -------------------------
# Load default config from JSON
import json
import os

_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
try:
    with open(_config_path, 'r') as _f:
        _default_config = json.load(_f)
    # log(f"Loaded config from {_config_path}: {_default_config}")
except Exception as e:
    log(f"Failed to load config: {str(e)}")
    _default_config = {}

VENDOR_ID_STR = _default_config.get('VENDOR_ID')
PRODUCT_ID_STR = _default_config.get('PRODUCT_ID')

def parse_hex_or_int(value, default):
    if value is None:
        return default
    try:
        if isinstance(value, str):
            return int(value, 0)
        return int(value)
    except (ValueError, TypeError):
        return None

VENDOR_ID = parse_hex_or_int(VENDOR_ID_STR, 0x1d50)
PRODUCT_ID = parse_hex_or_int(PRODUCT_ID_STR, 0x615e)

# Axis sensitivities settings (set to 1 for normal, negative to invert)
SCALE_X = _default_config.get('SCALE_X')
SCALE_Y = _default_config.get('SCALE_Y')
SCALE_Z = _default_config.get('SCALE_Z')
SCALE_RX = _default_config.get('SCALE_RX')
SCALE_RY = _default_config.get('SCALE_RY')
SCALE_RZ = _default_config.get('SCALE_RZ')

# Motion mode settings 
# - 1 to use orbital motion mode (move the target)
# - 2 to use navigating motion mode (move the camera)
MOTION_MODE = _default_config.get('MOTION_MODE')

# Movement sensitivities settings
ROTATION_SENSITIVITY = _default_config.get('ROTATION_SENSITIVITY')

# Distance-based translation sensitivity (linear scaling)
NEAR_DISTANCE = _default_config.get('NEAR_DISTANCE')
FAR_DISTANCE = _default_config.get('FAR_DISTANCE')
NEAR_TRANS_SENSITIVITY = _default_config.get('NEAR_TRANS_SENSITIVITY')
FAR_TRANS_SENSITIVITY = _default_config.get('FAR_TRANS_SENSITIVITY')
DYN_TRANS_SENSITIVITY = 0.0

# Orthographic mode zoom factor coefficient
# - to scale zooming to being similar to perspective camera
ORTHO_MODE_ZOOM_FACTOR_COEFF = 0.1289

# Palette button configuration
BUTTON_PROPERTIES = {
    'id': 'TrackpuckToolsCommand',
    'display_name': 'TrackpuckTools',
    'description': '6DoF HID Trackpuck Integration Tools',
    'resources': 'resources',
    'palette_id': 'TrackpuckToolsPalette'
}

# Custom Event ID
TP_QUEUE_EVENT_ID = 'TrackpuckTools_QueueEvent'

# Process Queue Event Sleep Interval (In Second)
PROCESS_EVENT_SLEEP_SEC = 0.01 # 10ms = 100Hz


# -------------------------
# Runtime Variables
# -------------------------
REQUIRED_PACKAGES = [
    ("hid", "hidapi"),  # (import_name, package_name)
]
app = None
ui = None
hid = None
device = None
running = True
active_palette_instance = None
event_handlers_list = []
hid_queue = None
hid_queue_stop_event = None
hid_thread = None
process_queue_event_handler = None
process_queue_thread = None
process_queue_stop_event = None
device_connected = False
disconnect_error = None


# -------------------------
# Preferences
# -------------------------
def get_prefs_path():
    try:
        if sys.platform == "win32":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
            prefs_dir = os.path.join(base, "Autodesk", "TrackpuckTools")
        else:
            base = os.path.expanduser("~/Library/Application Support/Autodesk")
            prefs_dir = os.path.join(base, "TrackpuckTools")
        if not os.path.exists(prefs_dir):
            os.makedirs(prefs_dir)
        return os.path.join(prefs_dir, "prefs.json")
    except Exception as e:
        log(f"Failed to get prefs path: {str(e)}")
        return None

try:
    PREFS_PATH = get_prefs_path()
except Exception as e:
    log(f"Failed to initialize PREFS_PATH: {str(e)}")
    PREFS_PATH = None


def save_prefs(prefs):
    try:
        if PREFS_PATH:
            with open(PREFS_PATH, "w") as f:
                json.dump(prefs, f)
    except Exception as e:
        log(f"Failed to save prefs: {str(e)}")


def load_prefs():
    try:
        if PREFS_PATH and os.path.exists(PREFS_PATH):
            with open(PREFS_PATH, "r") as f:
                return json.load(f)
    except Exception as e:
        log(f"Failed to load prefs: {str(e)}")
    return {}


def apply_prefs(prefs):
    global NEAR_DISTANCE, FAR_DISTANCE, NEAR_TRANS_SENSITIVITY, FAR_TRANS_SENSITIVITY
    global ROTATION_SENSITIVITY, MOTION_MODE
    global SCALE_X, SCALE_Y, SCALE_Z, SCALE_RX, SCALE_RY, SCALE_RZ
    
    if 'NEAR_DISTANCE' in prefs:
        NEAR_DISTANCE = prefs['NEAR_DISTANCE']
    if 'FAR_DISTANCE' in prefs:
        FAR_DISTANCE = prefs['FAR_DISTANCE']
    if 'NEAR_TRANS_SENSITIVITY' in prefs:
        NEAR_TRANS_SENSITIVITY = prefs['NEAR_TRANS_SENSITIVITY']
    if 'FAR_TRANS_SENSITIVITY' in prefs:
        FAR_TRANS_SENSITIVITY = prefs['FAR_TRANS_SENSITIVITY']
    if 'ROTATION_SENSITIVITY' in prefs:
        ROTATION_SENSITIVITY = prefs['ROTATION_SENSITIVITY']
    if 'MOTION_MODE' in prefs:
        MOTION_MODE = prefs['MOTION_MODE']
    if 'SCALE_X' in prefs:
        SCALE_X = prefs['SCALE_X']
    if 'SCALE_Y' in prefs:
        SCALE_Y = prefs['SCALE_Y']
    if 'SCALE_Z' in prefs:
        SCALE_Z = prefs['SCALE_Z']
    if 'SCALE_RX' in prefs:
        SCALE_RX = prefs['SCALE_RX']
    if 'SCALE_RY' in prefs:
        SCALE_RY = prefs['SCALE_RY']
    if 'SCALE_RZ' in prefs:
        SCALE_RZ = prefs['SCALE_RZ']


# -------------------------
# Movement Controls
# -------------------------
def apply_6dof_orbital_motion(view, tx, ty, tz, rx, ry, rz):
    # -------------------------
    # Apply full 6-DoF orbital motion to the lock target in viewport
    # tx: translate left and right (target x-axis)
    # ty: translate zoom-in and out (target z-axis/look direction)  
    # tz: translate up and down (target y-axis, eye level, altitude)
    # rx: rotate on x axis (pitch - tilt up/down)
    # ry: rotate on y axis (roll - twist around look direction)
    # rz: rotate on z axis (yaw/orbit - rotate left/right)
    # -------------------------
    # | Puck Movement | Camera Movement | What You See | Movement Type |
    # |---------------|-----------------|--------------|---------------|
    # | Push **Right** | Camera pans right | Model shifts left | Pan (X) |
    # | Push **Left** | Camera pans left | Model shifts right | Pan (X) |
    # | Push **Down** | Camera pans down | Model shifts up | Pan (Y) |
    # | Push **Up** | Camera pans up | Model shifts down | Pan (Y) |
    # | Pull **Back (toward you)** | Camera moves backward | Zoom out (model smaller) | Zoom (Z) |
    # | Push **Forward (away from you)** | Camera moves forward | Zoom in (model larger) | Zoom (Z) |
    # | Tilt puck **Forward** (top away from you) | Camera orbits downward around pivot | View rotates downward around model | Orbit Pitch (X-rotation) |
    # | Tilt puck **Back** (top toward you) | Camera orbits upward around pivot | View rotates upward around model | Orbit Pitch (X-rotation) |
    # | Tilt puck **Right** (right side down) | Camera orbits right around pivot | View rotates right around model | Orbit Yaw (Y-rotation) |
    # | Tilt puck **Left** (left side down) | Camera orbits left around pivot | View rotates left around model | Orbit Yaw (Y-rotation) |
    # | Twist puck **Right (clockwise)** | Camera rolls clockwise | View tilts right (horizon rotates) | Roll (Z-rotation) |
    # | Twist puck **Left (counter-clockwise)** | Camera rolls counter-clockwise | View tilts left (horizon rotates) | Roll (Z-rotation) |
    # -------------------------
    
    global ROTATION_SENSITIVITY, DYN_TRANS_SENSITIVITY
    
    # keep this for inverse input
    tx = -tx
    tz = -tz
    ry = -ry

    # Skip if no movement
    if tx == 0 and ty == 0 and tz == 0 and rx == 0 and ry == 0 and rz == 0:
        return

    camera = view.camera
    camera.isSmoothTransition = False

    eye = camera.eye
    target = camera.target
    up = camera.upVector
    
    view_vec = adsk.core.Vector3D.create(eye.x - target.x, eye.y - target.y, eye.z - target.z)
    distance = view_vec.length
    view_vec.normalize()
    
    right_vec = up.copy()
    right_vec = right_vec.crossProduct(view_vec)
    right_vec.normalize()
    
    up_normalized = view_vec.copy()
    up_normalized = up_normalized.crossProduct(right_vec)
    up_normalized.normalize()
    
    # ORBITAL ROTATIONS: Camera orbits around FIXED target point
    # rx: orbit pitch (rotate view_vec around right vector)
    # ry: roll (rotate up around view vector)
    # rz: orbit yaw (rotate view_vec around up vector)
    
    if rx != 0 or ry != 0 or rz != 0:
        # Yaw rotation (orbit around up vector)
        if rz != 0:
            angle = rz * ROTATION_SENSITIVITY
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            
            new_right = adsk.core.Vector3D.create(
                right_vec.x * cos_a - view_vec.x * sin_a,
                right_vec.y * cos_a - view_vec.y * sin_a,
                right_vec.z * cos_a - view_vec.z * sin_a
            )
            new_view = adsk.core.Vector3D.create(
                right_vec.x * sin_a + view_vec.x * cos_a,
                right_vec.y * sin_a + view_vec.y * cos_a,
                right_vec.z * sin_a + view_vec.z * cos_a
            )
            right_vec = new_right
            view_vec = new_view
        
        # Pitch rotation (orbit around right vector)
        if rx != 0:
            angle = rx * ROTATION_SENSITIVITY
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            
            new_up = adsk.core.Vector3D.create(
                up_normalized.x * cos_a - view_vec.x * sin_a,
                up_normalized.y * cos_a - view_vec.y * sin_a,
                up_normalized.z * cos_a - view_vec.z * sin_a
            )
            new_view = adsk.core.Vector3D.create(
                up_normalized.x * sin_a + view_vec.x * cos_a,
                up_normalized.y * sin_a + view_vec.y * cos_a,
                up_normalized.z * sin_a + view_vec.z * cos_a
            )
            up_normalized = new_up
            view_vec = new_view
        
        # Roll rotation (twist around view vector)
        if ry != 0:
            angle = ry * ROTATION_SENSITIVITY
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            
            new_right = adsk.core.Vector3D.create(
                right_vec.x * cos_a - up_normalized.x * sin_a,
                right_vec.y * cos_a - up_normalized.y * sin_a,
                right_vec.z * cos_a - up_normalized.z * sin_a
            )
            new_up = adsk.core.Vector3D.create(
                right_vec.x * sin_a + up_normalized.x * cos_a,
                right_vec.y * sin_a + up_normalized.y * cos_a,
                right_vec.z * sin_a + up_normalized.z * cos_a
            )
            right_vec = new_right
            up_normalized = new_up
    
    # ORBITAL TRANSLATIONS: Move target (eye follows via orbital formula)
    # tx, tz: pan - translate target horizontally/vertically
    # ty: zoom - adjust orbital distance (eye moves closer/farther)
    
    # Calculate dynamic translation/zoom sensitivity based on distance (perspective) or viewExtents (ortho)
    is_ortho = camera.cameraType == adsk.core.CameraTypes.OrthographicCameraType
    
    if is_ortho:
        extent = camera.viewExtents
        if extent <= NEAR_DISTANCE:
            dyn_trans_sensitivity = NEAR_TRANS_SENSITIVITY
        elif extent >= FAR_DISTANCE:
            dyn_trans_sensitivity = FAR_TRANS_SENSITIVITY
        else:
            t = (extent - NEAR_DISTANCE) / (FAR_DISTANCE - NEAR_DISTANCE)
            dyn_trans_sensitivity = NEAR_TRANS_SENSITIVITY + t * (FAR_TRANS_SENSITIVITY - NEAR_TRANS_SENSITIVITY)
    else:
        if distance <= NEAR_DISTANCE:
            dyn_trans_sensitivity = NEAR_TRANS_SENSITIVITY
        elif distance >= FAR_DISTANCE:
            dyn_trans_sensitivity = FAR_TRANS_SENSITIVITY
        else:
            t = (distance - NEAR_DISTANCE) / (FAR_DISTANCE - NEAR_DISTANCE)
            dyn_trans_sensitivity = NEAR_TRANS_SENSITIVITY + t * (FAR_TRANS_SENSITIVITY - NEAR_TRANS_SENSITIVITY)
    
    DYN_TRANS_SENSITIVITY = dyn_trans_sensitivity
    
    if tx != 0 or tz != 0:
        trans_x = adsk.core.Vector3D.create(right_vec.x * tx * dyn_trans_sensitivity, 
                                             right_vec.y * tx * dyn_trans_sensitivity, 
                                             right_vec.z * tx * dyn_trans_sensitivity)
        trans_z = adsk.core.Vector3D.create(up_normalized.x * (-tz) * dyn_trans_sensitivity, 
                             up_normalized.y * (-tz) * dyn_trans_sensitivity, 
                             up_normalized.z * (-tz) * dyn_trans_sensitivity)
        target.translateBy(trans_x)
        target.translateBy(trans_z)
    
    if ty != 0:
        if is_ortho:
            current_extent = camera.viewExtents
            zoom_factor = ty * dyn_trans_sensitivity * ORTHO_MODE_ZOOM_FACTOR_COEFF
            new_extent = current_extent * (1.0 - zoom_factor)
            if new_extent > 0.001:
                camera.viewExtents = new_extent
            ty = 0
        
        if ty != 0:
            distance -= ty * dyn_trans_sensitivity
            if distance < 0.01:
                distance = 0.01
    
    new_eye = adsk.core.Point3D.create(
        target.x + view_vec.x * distance,
        target.y + view_vec.y * distance,
        target.z + view_vec.z * distance
    )
    
    camera.eye = new_eye
    camera.target = target
    camera.upVector = up_normalized
    camera.isSmoothTransition = False

    view.camera = camera
    view.refresh()


def apply_6dof_navigating_motion(view, tx, ty, tz, rx, ry, rz):    
    # -------------------------
    # Apply full 6-DoF navigation motion of the viewport camera
    # tx: translate left and right (camera target x-axis)
    # ty: translate zoom-in and out (camera target z-axis/look direction)  
    # tz: translate up and down (camera target y-axis, eye level, altitude)
    # rx: rotate on x axis (pitch - tilt up/down)
    # ry: rotate on y axis (roll - twist around look direction)
    # rz: rotate on z axis (yaw/orbit - rotate left/right)
    # -------------------------
    # | Puck Movement | Camera Movement | What You See | Movement Type |
    # |---------------|-----------------|--------------|---------------|
    # | Push **Right** | Camera moves right | Model shifts left | Pan (X) |
    # | Push **Left** | Camera moves left | Model shifts right | Pan (X) |
    # | Push **Down** | Camera moves down | Model shifts up | Pan (Z) |
    # | Push **Up** | Camera moves up | Model shifts down | Pan (Z) |
    # | Pull **Back (toward you)** | Camera moves backward | Zoom out (model smaller) | Zoom (Y) |
    # | Push **Forward (away from you)** | Camera moves forward | Zoom in (model larger) | Zoom (Y) |
    # | Tilt puck **Forward** (top away from you) | Camera pitches down | View looks downward | Pitch (X-rotation) |
    # | Tilt puck **Back** (top toward you) | Camera pitches up | View looks upward | Pitch (X-rotation) |
    # | Tilt puck **Right** (right side down) | Camera rolls right | View tilts right | Roll (Y-rotation) |
    # | Tilt puck **Left** (left side down) | Camera rolls left | View tilts left | Roll (Y-rotation) |
    # | Twist puck **Right (clockwise)** | Camera yaws clockwise | View rotates right around model | Yaw (Z-rotation) |
    # | Twist puck **Left (counter-clockwise)** | Camera yaws counter-clockwise | View rotates left around model | Yaw (Z-rotation) |
    # -------------------------

    global ROTATION_SENSITIVITY, DYN_TRANS_SENSITIVITY
    
    # keep this for inverse input
    rx = -rx
    rz = -rz

    # Skip if no movement
    if tx == 0 and ty == 0 and tz == 0 and rx == 0 and ry == 0 and rz == 0:
        return

    camera = view.camera
    camera.isSmoothTransition = False

    # Get current camera state
    eye = camera.eye
    target = camera.target
    up = camera.upVector
    
    # Create vector from target to eye (view direction)
    view_vec = adsk.core.Vector3D.create(eye.x - target.x, eye.y - target.y, eye.z - target.z)
    distance = view_vec.length
    
    # Normalize view vector for rotation calculations
    view_vec.normalize()
    
    # Calculate right vector (perpendicular to view and up)
    right_vec = up.copy()
    right_vec = right_vec.crossProduct(view_vec)
    right_vec.normalize()
    
    # Recalculate up vector to ensure orthogonality
    up_normalized = view_vec.copy()
    up_normalized = up_normalized.crossProduct(right_vec)
    up_normalized.normalize()
    
    # Apply rotations around target using orbital motion
    # rx: pitch (rotate around right vector)
    # ry: roll (rotate around view vector)
    # rz: yaw (rotate around up vector)
    
    if rx != 0 or ry != 0 or rz != 0:
        # Create rotation matrix from individual rotations
        # Apply rotations in order: yaw (rz), pitch (rx), roll (ry)
        
        # Yaw rotation (around up vector)
        if rz != 0:
            angle = rz * ROTATION_SENSITIVITY
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            
            new_right = adsk.core.Vector3D.create(
                right_vec.x * cos_a - view_vec.x * sin_a,
                right_vec.y * cos_a - view_vec.y * sin_a,
                right_vec.z * cos_a - view_vec.z * sin_a
            )
            new_view = adsk.core.Vector3D.create(
                right_vec.x * sin_a + view_vec.x * cos_a,
                right_vec.y * sin_a + view_vec.y * cos_a,
                right_vec.z * sin_a + view_vec.z * cos_a
            )
            right_vec = new_right
            view_vec = new_view
        
        # Pitch rotation (around right vector)
        if rx != 0:
            angle = rx * ROTATION_SENSITIVITY
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            
            new_up = adsk.core.Vector3D.create(
                up_normalized.x * cos_a - view_vec.x * sin_a,
                up_normalized.y * cos_a - view_vec.y * sin_a,
                up_normalized.z * cos_a - view_vec.z * sin_a
            )
            new_view = adsk.core.Vector3D.create(
                up_normalized.x * sin_a + view_vec.x * cos_a,
                up_normalized.y * sin_a + view_vec.y * cos_a,
                up_normalized.z * sin_a + view_vec.z * cos_a
            )
            up_normalized = new_up
            view_vec = new_view
        
        # Roll rotation (around view vector - twist)
        if ry != 0:
            angle = ry * ROTATION_SENSITIVITY
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            
            new_right = adsk.core.Vector3D.create(
                right_vec.x * cos_a - up_normalized.x * sin_a,
                right_vec.y * cos_a - up_normalized.y * sin_a,
                right_vec.z * cos_a - up_normalized.z * sin_a
            )
            new_up = adsk.core.Vector3D.create(
                right_vec.x * sin_a + up_normalized.x * cos_a,
                right_vec.y * sin_a + up_normalized.y * cos_a,
                right_vec.z * sin_a + up_normalized.z * cos_a
            )
            right_vec = new_right
            up_normalized = new_up
    
    # Apply translations in camera space
    if tx != 0 or ty != 0 or tz != 0:
        # Calculate dynamic translation/zoom sensitivity based on distance (perspective) or viewExtents (ortho)
        is_ortho = camera.cameraType == adsk.core.CameraTypes.OrthographicCameraType
        
        if is_ortho:
            extent = camera.viewExtents
            if extent <= NEAR_DISTANCE:
                dyn_trans_sensitivity = NEAR_TRANS_SENSITIVITY
            elif extent >= FAR_DISTANCE:
                dyn_trans_sensitivity = FAR_TRANS_SENSITIVITY
            else:
                t = (extent - NEAR_DISTANCE) / (FAR_DISTANCE - NEAR_DISTANCE)
                dyn_trans_sensitivity = NEAR_TRANS_SENSITIVITY + t * (FAR_TRANS_SENSITIVITY - NEAR_TRANS_SENSITIVITY)
        else:
            if distance <= NEAR_DISTANCE:
                dyn_trans_sensitivity = NEAR_TRANS_SENSITIVITY
            elif distance >= FAR_DISTANCE:
                dyn_trans_sensitivity = FAR_TRANS_SENSITIVITY
            else:
                t = (distance - NEAR_DISTANCE) / (FAR_DISTANCE - NEAR_DISTANCE)
                dyn_trans_sensitivity = NEAR_TRANS_SENSITIVITY + t * (FAR_TRANS_SENSITIVITY - NEAR_TRANS_SENSITIVITY)
        
        DYN_TRANS_SENSITIVITY = dyn_trans_sensitivity
        
        # tx: translate along right vector
        # ty: translate along view vector (zoom in/out towards target)
        # tz: translate along up vector
        
        trans_x = adsk.core.Vector3D.create(right_vec.x * tx * dyn_trans_sensitivity, 
                                             right_vec.y * tx * dyn_trans_sensitivity, 
                                             right_vec.z * tx * dyn_trans_sensitivity)
        
        # For orthographic mode, use camera viewExtents for zoom instead of translation
        if is_ortho:
            if ty != 0:
                current_extent = camera.viewExtents
                zoom_factor = ty * dyn_trans_sensitivity * ORTHO_MODE_ZOOM_FACTOR_COEFF
                new_extent = current_extent * (1.0 - zoom_factor)
                if new_extent > 0.001:
                    camera.viewExtents = new_extent
            ty = 0  # Skip translation for ty in ortho mode
        
        trans_y = adsk.core.Vector3D.create(view_vec.x * ty * dyn_trans_sensitivity, 
                                             view_vec.y * ty * dyn_trans_sensitivity, 
                                             view_vec.z * ty * dyn_trans_sensitivity)
        # Vertical input: positive should move the camera down (push down -> camera moves down)
        # up_normalized points upward, so negate tz to move downward for positive input
        trans_z = adsk.core.Vector3D.create(up_normalized.x * (-tz) * dyn_trans_sensitivity, 
                             up_normalized.y * (-tz) * dyn_trans_sensitivity, 
                             up_normalized.z * (-tz) * dyn_trans_sensitivity)
        
        # Apply translation to both eye and target
        target.translateBy(trans_x)
        target.translateBy(trans_y)
        target.translateBy(trans_z)
        
        eye.translateBy(trans_x)
        eye.translateBy(trans_y)
        eye.translateBy(trans_z)
    
    # Update eye position based on rotated view vector (maintaining orbital distance)
    new_eye = adsk.core.Point3D.create(
        target.x + view_vec.x * distance,
        target.y + view_vec.y * distance,
        target.z + view_vec.z * distance
    )
    
    # Update camera
    camera.eye = new_eye
    camera.target = target
    camera.upVector = up_normalized
    camera.isSmoothTransition = False

    view.camera = camera
    view.refresh()


# -------------------------
# HID thread
# -------------------------
def hid_loop():
    # HID reading loop - runs in separate thread to avoid blocking main UI
    global device, running, hid_queue, hid_queue_stop_event
    global SCALE_X, SCALE_Y, SCALE_Z, SCALE_RX, SCALE_RY, SCALE_RZ
    global disconnect_error

    if not device:
        return

    try:
        device.set_nonblocking(True)
    except Exception as e:
        log(f"HID device error!\n\nError: {type(e).__name__}: {e}")
        return

    # Main HID read loop - runs in background thread
    while running and not hid_queue_stop_event.is_set():
        try:
            data = device.read(64)
            if data:
                # Parse as signed 8-bit integers (range: -127 to +127), then normalize
                tx = struct.unpack('b', bytes([data[1]]))[0] / 127.0 * SCALE_X
                ty = struct.unpack('b', bytes([data[2]]))[0] / 127.0 * SCALE_Y
                tz = struct.unpack('b', bytes([data[3]]))[0] / 127.0 * SCALE_Z
                rx = struct.unpack('b', bytes([data[4]]))[0] / 127.0 * SCALE_RX
                ry = struct.unpack('b', bytes([data[5]]))[0] / 127.0 * SCALE_RY
                rz = struct.unpack('b', bytes([data[6]]))[0] / 127.0 * SCALE_RZ
                btns = data[7]
                # Put data in queue for main thread to process
                hid_queue.put((tx, ty, tz, rx, ry, rz, btns))
                # log(f"{tx}, {ty}, {tz}, {rx}, {ry}, {rz}")
        except Exception as e:
            log(f"Device disconnected: {type(e).__name__}: {e}")
            disconnect_error = f"Device disconnected"
            break
        
        # Use event wait with timeout instead of sleep for faster response to stop signal
        hid_queue_stop_event.wait(PROCESS_EVENT_SLEEP_SEC)


def process_hid_queue():
    # Process HID data from queue (called by queue_processor_loop)
    global running, hid_queue, hid_queue_stop_event, app, active_palette_instance
    global MOTION_MODE, DYN_TRANS_SENSITIVITY, disconnect_error, ui

    if disconnect_error:
        error_msg = disconnect_error
        disconnect_error = None
        deactivate_device_read(error_msg)
        return True

    if not running or hid_queue_stop_event.is_set():
        return False

    palette_update_counter = 0
    was_dark = None

    try:
        # Process all queued HID events
        while True:
            tx, ty, tz, rx, ry, rz, btns = hid_queue.get_nowait()

            try:
                view = app.activeViewport
            except (RuntimeError, Exception):
                adsk.doEvents()
                break

            if btns & 1:
                view.fit()
            if btns & 2:
                view.goHome(False)
            if btns & 4:
                None

            # Apply motion based on selected mode
            if MOTION_MODE == 1:
                apply_6dof_orbital_motion(view, tx, ty, tz, rx, ry, rz)
            elif MOTION_MODE == 2:
                apply_6dof_navigating_motion(view, tx, ty, tz, rx, ry, rz)

            # Update palette with current sensitivity and theme
            if active_palette_instance:
                if palette_update_counter == 0:
                    try:
                        active_palette_instance.sendInfoToHTML('updateSensitivity', f'{DYN_TRANS_SENSITIVITY:.3f}')
                    except Exception as e:
                        log(f"sendInfoToHTML error: {e}")
                
                if palette_update_counter == 0:
                    try:
                        theme = app.preferences.generalPreferences.activeUserInterfaceTheme
                        is_dark = theme in [2, 3]
                        if is_dark != was_dark:
                            active_palette_instance.sendInfoToHTML('setTheme', json.dumps({'darkMode': is_dark}))
                            was_dark = is_dark
                    except Exception as e:
                        log(f"sendTheme error: {e}")

                palette_update_counter += 1
                if palette_update_counter >= 10:
                    palette_update_counter = 0

            adsk.doEvents()
            time.sleep(PROCESS_EVENT_SLEEP_SEC)

    except queue.Empty:
        pass
    
    return True


# -------------------------
# Custom event for main-thread queue processing
# -------------------------
class ProcessQueueEventHandler(adsk.core.CustomEventHandler):
    # Handles periodic queue processing events (main thread safe).
    def notify(self, eventArgs):
        try:
            process_hid_queue()
        except Exception:
            pass  # Suppress errors for periodic processing


def deactivate_device_read(error_msg=None):
    global app, ui, running, device, hid_thread, hid_queue_stop_event, device_connected

    running = False
    device_connected = False

    try:
        # Signal the HID thread to stop
        if hid_queue_stop_event:
            hid_queue_stop_event.set()

        # Wait for HID thread to finish (with timeout)
        if hid_thread and hid_thread.is_alive():
            hid_thread.join(timeout=2.0)
            hid_thread = None

    except Exception as e:
        log(f"Error deactivate_device_read, stage 1: {e}")
        
    try:
        # Stop the background thread that fires custom events.
        global process_queue_thread, process_queue_stop_event
        if process_queue_stop_event:
            process_queue_stop_event.set()

        if process_queue_thread and process_queue_thread.is_alive():
            process_queue_thread.join(timeout=1.0)
        process_queue_thread = None
        process_queue_stop_event = None

    except Exception as e:
        log(f"Error deactivate_device_read, stage 2: {e}")
        
    try:
        # Close device after thread has stopped
        if device:
            try:
                device.close()
            except Exception as e:
                log(f"Error closing device: {e}")
            device = None

    except Exception as e:
        log(f"Error deactivate_device_read, stage 3: {e}")

    try:
        notify_device_state()
    except Exception as e:
        log(f"Error deactivate_device_read, stage 4: {e}")

    if error_msg:
        if ui:
            ui.messageBox(error_msg)


def activate_device_read(silent=False):
    # Start HID reading in background thread with queue processing
    global VENDOR_ID, PRODUCT_ID, hid_device_path, app, ui, running, hid, device
    global SCALE_X, SCALE_Y, SCALE_Z, SCALE_RX, SCALE_RY, SCALE_RZ, MOTION_MODE
    global hid_thread, hid_queue_stop_event, hid_queue, device_connected

    try:
        hid_device_path = None

        dbg = []
        for dev in hid.enumerate():
            if dev['vendor_id'] == VENDOR_ID and dev['product_id'] == PRODUCT_ID:
                if dev['usage'] == 0x4:
                    dbg.append(f"Device: {dev['product_string']}")
                    dbg.append(f"  VID: {hex(dev['vendor_id'])} | PID: {hex(dev['product_id'])}")
                    dbg.append(f"  Usage Page: {hex(dev['usage_page'])} | Usage: {hex(dev['usage'])}")
                    try:
                        device = hid.device()
                        device.open_path(dev['path'])
                        dbg.append("Device connected.")
                        hid_device_path = dev['path']
                    except IOError as e:
                        dbg.append(f"Couldn't connect to device: {e}")
                    break

        # ui.messageBox("\n".join(dbg))

        if hid_device_path == None:
            if not silent:
                ui.messageBox(f"No Trackpuck found.")
            device_connected = False
            notify_device_state()
            return

        if not device:
            if not silent:
                ui.messageBox(f"Failed to open Trackpuck device.")
            device_connected = False
            notify_device_state()
            return

        device_connected = True
        notify_device_state()

        # Start background thread for HID reading
        running = True

        hid_queue = queue.Queue()
        hid_queue_stop_event = threading.Event()

        hid_thread = threading.Thread(target=hid_loop)
        hid_thread.daemon = True
        hid_thread.start()

        # Start the background thread that fires custom events.
        global process_queue_thread, process_queue_stop_event
        if process_queue_thread and process_queue_thread.is_alive():
            return  # Already running
        process_queue_stop_event = threading.Event()
        def run():
            while process_queue_stop_event is not None and not process_queue_stop_event.is_set():
                app.fireCustomEvent(TP_QUEUE_EVENT_ID, '')
                time.sleep(PROCESS_EVENT_SLEEP_SEC)
        process_queue_thread = threading.Thread(target=run, daemon=True)
        process_queue_thread.start()

    except:
        log(f"Error activate_device_read: {e}")
        if ui:
            ui.messageBox(traceback.format_exc())


def notify_device_state():
    global active_palette_instance, device_connected
    if active_palette_instance:
        try:
            active_palette_instance.sendInfoToHTML('deviceState', json.dumps({'connected': device_connected}))
        except Exception as e:
            log(f"Error sending device state to HTML: {e}")


# -------------------------
# Import modules
# -------------------------
def find_wheel_file(pkg_name):
    # Find .whl file in package-specific folder (e.g., hidapi/*.whl)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Only search in the package-specific subdirectory
    # User should run: pip download {pkg} -d {pkg}
    pattern = os.path.join(script_dir, pkg_name, "*.whl")
    wheels = glob.glob(pattern)
    
    for wheel in wheels:
        # Check if wheel filename contains package name
        wheel_lower = os.path.basename(wheel).lower()
        if pkg_name.lower() in wheel_lower:
            return wheel
    
    return None


def extract_wheel(wheel_path, extract_dir):
    # Extract wheel file to directory
    if not os.path.exists(extract_dir):
        os.makedirs(extract_dir)
    
    with zipfile.ZipFile(wheel_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)


def get_module_paths(extract_dir):
    # Get paths to add to sys.path from extracted wheel
    paths = [extract_dir]
    
    # Check for .dist-info and skip it
    for item in os.listdir(extract_dir):
        full_path = os.path.join(extract_dir, item)
        if os.path.isdir(full_path) and item.endswith('.dist-info'):
            continue
        if os.path.isdir(full_path):
            paths.append(full_path)
    
    return paths


def find_module_in_extracted(extract_dir, pkg_name):
    # Find the actual module file/directory in extracted wheel
    pkg_name_lower = pkg_name.lower()
    
    # Check for package directory (e.g., 'hid/')
    for item in os.listdir(extract_dir):
        full_path = os.path.join(extract_dir, item)
        item_lower = item.lower()
        
        # Skip metadata
        if item.endswith('.dist-info') or item.endswith('.pth'):
            continue
        
        # Check if directory matches package name
        if os.path.isdir(full_path) and item_lower == pkg_name_lower:
            return full_path, item
        
        # Check for .py file (e.g., 'hid.py')
        if os.path.isfile(full_path) and item_lower == f"{pkg_name_lower}.py":
            return full_path, item.replace('.py', '')
        
        # Check for compiled extension files (.so on Linux/macOS, .pyd on Windows)
        # Pattern: hid.cpython-314-darwin.so or hid.pyd
        if os.path.isfile(full_path) and item_lower.startswith(f"{pkg_name_lower}."):
            if item.endswith(('.so', '.pyd', '.dll')):
                return full_path, pkg_name
    
    return None, None


def import_libs():
    # Import required packages from pre-downloaded wheel files
    global app, ui, hid
    lib_ready = True
    report = []
    missing_packages = []
    
    for pkg_spec in REQUIRED_PACKAGES:
        # Handle both string and tuple formats
        if isinstance(pkg_spec, tuple):
            import_name, package_name = pkg_spec
        else:
            import_name = package_name = pkg_spec
        
        try:
            # Try to import directly first
            module = importlib.import_module(import_name)
            # Check if it has the expected attributes
            if hasattr(module, 'device'):
                globals()[import_name] = module
                report.append(f"{import_name}: OK (has device)")
            else:
                raise ImportError(f"Module {import_name} imported but missing 'device' attribute")
        except ImportError:
            # Look for wheel file using package_name
            wheel_path = find_wheel_file(package_name)
            
            if wheel_path:
                try:
                    # Extract wheel to temp directory
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    extract_dir = os.path.join(script_dir, "__extracted__", package_name)
                    
                    report.append(f"{import_name}: Found wheel at {wheel_path}")
                    
                    # Extract the wheel
                    extract_wheel(wheel_path, extract_dir)
                    
                    # Add extracted paths to sys.path
                    module_paths = get_module_paths(extract_dir)
                    for path in module_paths:
                        if path not in sys.path:
                            sys.path.insert(0, path)
                    
                    # Find and import the module from extracted location using import_name
                    module_path, module_name = find_module_in_extracted(extract_dir, import_name)
                    
                    if module_path:
                        # Add parent directory to sys.path for proper imports
                        parent_dir = os.path.dirname(module_path) if os.path.isfile(module_path) else module_path
                        if parent_dir not in sys.path:
                            sys.path.insert(0, parent_dir)
                        
                        # Import using spec with import_name
                        module = None
                        if os.path.isfile(module_path):
                            # Single .py file
                            spec = importlib.util.spec_from_file_location(import_name, module_path)
                            if spec and spec.loader:
                                module = importlib.util.module_from_spec(spec)
                                sys.modules[import_name] = module
                                spec.loader.exec_module(module)
                            else:
                                raise ImportError(f"Cannot load spec from {module_path}")
                        else:
                            # Package directory
                            init_path = os.path.join(module_path, "__init__.py")
                            if os.path.exists(init_path):
                                spec = importlib.util.spec_from_file_location(import_name, init_path)
                                if spec and spec.loader:
                                    module = importlib.util.module_from_spec(spec)
                                    sys.modules[import_name] = module
                                    spec.loader.exec_module(module)
                                else:
                                    raise ImportError(f"Cannot load spec from {init_path}")
                            else:
                                # Fallback to regular import
                                module = importlib.import_module(import_name)
                        
                        # Assign to global variable
                        globals()[import_name] = module
                        # Verify it has required attributes
                        if not hasattr(module, 'device'):
                            raise ImportError(f"Module {import_name} loaded from {module_path} but missing 'device' attribute. Check wheel contents.")
                        report.append(f"{import_name}: Loaded successfully from {module_path}")
                    else:
                        # Fallback to regular import
                        module = importlib.import_module(import_name)
                        if not hasattr(module, 'device'):
                            raise ImportError(f"Module {import_name} imported but missing 'device' attribute")
                        globals()[import_name] = module
                        report.append(f"{import_name}: Loaded successfully")
                    
                except Exception as e:
                    report.append(f"{import_name}: Error loading wheel - {str(e)}")
                    missing_packages.append(package_name)
                    lib_ready = False
            else:
                missing_packages.append(package_name)
                lib_ready = False

    # ui.messageBox("\n".join(report))
    
    # Show message if packages are missing
    if missing_packages:
        msg = []
        msg.append("The following packages are missing:")
        msg.append("")
        for pkg in missing_packages:
            msg.append(f"  - {pkg}")
        msg.append("")
        msg.append("Please download the wheel files using pip:")
        msg.append("")
        for pkg in missing_packages:
            msg.append(f"  pip download {pkg} -d {pkg}")
        msg.append("")
        msg.append("Note: The package name may differ from import name.")
        msg.append("For 'hid' module, use: pip download hidapi -d hidapi")
        msg.append("")
        msg.append("Then place the .whl files here:")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        for pkg in missing_packages:
            msg.append(f"  {script_dir}/{pkg}/")
        
        ui.messageBox("\n".join(msg))

    return lib_ready


def pull_libs():
    # Download wheel files from PyPI using urllib (no pip needed).
    import urllib.request
    import json
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    packages_to_pull = ["hidapi"]
    
    for pkg_name in packages_to_pull:
        pkg_dir = os.path.join(script_dir, pkg_name)
        if not os.path.exists(pkg_dir):
            os.makedirs(pkg_dir)
        
        wheel_path = find_wheel_file(pkg_name)
        if wheel_path:
            log(f"pull_libs: wheel already exists: {wheel_path}")
            continue
        
        try:
            log(f"pull_libs: downloading {pkg_name} from PyPI...")
            
            metadata_url = f"https://pypi.org/pypi/{pkg_name}/json"
            with urllib.request.urlopen(metadata_url, timeout=30) as response:
                metadata = json.loads(response.read().decode())
            
            releases = metadata.get("releases", {})
            if not releases:
                log(f"pull_libs: no releases found for {pkg_name}")
                continue
            
            version = metadata["info"]["version"]
            log(f"pull_libs: latest version is {version}")
            
            import platform
            system = platform.system().lower()
            machine = platform.machine().lower()
            
            if system == "darwin":
                platform_tag = "macosx"
                if machine == "x86_64":
                    platform_tag += "_10_15_x86_64"
                elif machine == "arm64":
                    platform_tag += "_11_0_arm64"
            elif system == "windows":
                platform_tag = "win_amd64"
            else:
                platform_tag = "manylinux2014_x86_64"
            
            py_version = f"cp{sys.version_info.major}{sys.version_info.minor}"
            
            log(f"pull_libs: looking for {py_version} on {platform_tag}")
            
            best_wheel_url = None
            best_wheel_filename = None
            
            for rel_version, files in releases.items():
                for file_info in files:
                    filename = file_info["filename"]
                    if filename.endswith(".whl"):
                        # Use strict version names (e.g. "-cp314-cp314-")
                        # The wheels should be named:
                        #   - hidapi-0.15.0-cp314-cp314-macosx_10_15_x86_64.whl
                        #   - hidapi-0.15.0-cp314-cp314-win_amd64.whl
                        if f"-{py_version}-{py_version}-" in filename and platform_tag in filename:
                            best_wheel_url = file_info["url"]
                            best_wheel_filename = filename
                            break
                if best_wheel_url:
                    break
            
            if not best_wheel_url:
                for rel_version, files in releases.items():
                    for file_info in files:
                        filename = file_info["filename"]
                        if filename.endswith(".whl") and py_version in filename:
                            best_wheel_url = file_info["url"]
                            best_wheel_filename = filename
                            break
                    if best_wheel_url:
                        break
            
            if not best_wheel_url:
                log(f"pull_libs: no compatible wheel found for {pkg_name}")
                continue
            
            log(f"pull_libs: downloading {best_wheel_filename}...")
            dest_path = os.path.join(pkg_dir, best_wheel_filename)
            
            with urllib.request.urlopen(best_wheel_url, timeout=60) as response:
                with open(dest_path, "wb") as f:
                    f.write(response.read())
            
            log(f"pull_libs: downloaded {best_wheel_filename} to {dest_path}")
            
        except Exception as e:
            log(f"pull_libs: error downloading {pkg_name}: {str(e)}")
            continue
    
    return True


# -------------------------
# Palette Command Handlers
# -------------------------
class PaletteIncomingEventHandler(adsk.core.HTMLEventHandler):
    # Handle incoming messages from the palette HTML.
    def __init__(self, palette):
        super().__init__()
        self.palette = palette
        
    def notify(self, eventArgs):
        global NEAR_DISTANCE, FAR_DISTANCE, NEAR_TRANS_SENSITIVITY, FAR_TRANS_SENSITIVITY
        global ROTATION_SENSITIVITY, MOTION_MODE
        global SCALE_X, SCALE_Y, SCALE_Z, SCALE_RX, SCALE_RY, SCALE_RZ
        try:
            import json
            event_args = adsk.core.HTMLEventArgs.cast(eventArgs)
            action = event_args.action
            data = event_args.data
            
            if action == 'closePalette':
                if active_palette_instance:
                    active_palette_instance.isVisible = False
            elif action == 'deactivateTrackpuck':
                deactivate_device_read()
            elif action == 'activateTrackpuck':
                activate_device_read()
            elif action == 'savePrefs':
                import json
                prefs_data = json.loads(data)
                existing_prefs = load_prefs()
                existing_prefs.update(prefs_data)
                save_prefs(existing_prefs)
            elif action == 'savePrefs':
                import json
                prefs_data = json.loads(data)
                save_prefs(prefs_data)
            elif action == 'loadPrefs':
                saved = load_prefs()
                if saved:
                    apply_prefs(saved)
                    config_payload = json.dumps({
                        'NEAR_DISTANCE': NEAR_DISTANCE,
                        'FAR_DISTANCE': FAR_DISTANCE,
                        'NEAR_TRANS_SENSITIVITY': NEAR_TRANS_SENSITIVITY,
                        'FAR_TRANS_SENSITIVITY': FAR_TRANS_SENSITIVITY,
                        'ROTATION_SENSITIVITY': ROTATION_SENSITIVITY,
                        'MOTION_MODE': MOTION_MODE,
                        'SCALE_X': SCALE_X,
                        'SCALE_Y': SCALE_Y,
                        'SCALE_Z': SCALE_Z,
                        'SCALE_RX': SCALE_RX,
                        'SCALE_RY': SCALE_RY,
                        'SCALE_RZ': SCALE_RZ
                    })
                    try:
                        self.palette.sendInfoToHTML('loadConfig', config_payload)
                    except:
                        pass
            elif action == 'updateConfig':
                import json
                config_data = json.loads(data)
                key = config_data.get('key')
                value = config_data.get('value')
                if key == 'NEAR_DISTANCE':
                    NEAR_DISTANCE = value
                elif key == 'FAR_DISTANCE':
                    FAR_DISTANCE = value
                elif key == 'NEAR_TRANS_SENSITIVITY':
                    NEAR_TRANS_SENSITIVITY = value
                elif key == 'FAR_TRANS_SENSITIVITY':
                    FAR_TRANS_SENSITIVITY = value
                elif key == 'ROTATION_SENSITIVITY':
                    ROTATION_SENSITIVITY = value
                elif key == 'MOTION_MODE':
                    MOTION_MODE = value
                elif key == 'SCALE_X':
                    SCALE_X = value
                elif key == 'SCALE_Y':
                    SCALE_Y = value
                elif key == 'SCALE_Z':
                    SCALE_Z = value
                elif key == 'SCALE_RX':
                    SCALE_RX = value
                elif key == 'SCALE_RY':
                    SCALE_RY = value
                elif key == 'SCALE_RZ':
                    SCALE_RZ = value
            elif action == 'paletteReady':
                config_payload = json.dumps({
                    'NEAR_DISTANCE': NEAR_DISTANCE,
                    'FAR_DISTANCE': FAR_DISTANCE,
                    'NEAR_TRANS_SENSITIVITY': NEAR_TRANS_SENSITIVITY,
                    'FAR_TRANS_SENSITIVITY': FAR_TRANS_SENSITIVITY,
                    'ROTATION_SENSITIVITY': ROTATION_SENSITIVITY,
                    'MOTION_MODE': MOTION_MODE,
                    'SCALE_X': SCALE_X,
                    'SCALE_Y': SCALE_Y,
                    'SCALE_Z': SCALE_Z,
                    'SCALE_RX': SCALE_RX,
                    'SCALE_RY': SCALE_RY,
                    'SCALE_RZ': SCALE_RZ
                })
                try:
                    self.palette.sendInfoToHTML('loadConfig', config_payload)
                except Exception as e:
                    log(f"Error sending loadConfig to HTML: {e}")

                try:
                    theme = app.preferences.generalPreferences.activeUserInterfaceTheme
                    is_dark = theme in [2, 3]
                    self.palette.sendInfoToHTML('setTheme', json.dumps({'darkMode': is_dark}))
                except Exception as e:
                    log(f"Error sending theme to HTML: {e}")

                try:
                    notify_device_state()
                except Exception as e:
                    log(f"Error sending device state to HTML: {e}")

        except Exception as e:
            log(f"Error handling palette message: {e}")


class PaletteCloseEventHandler(adsk.core.UserInterfaceGeneralEventHandler):
    # Handle palette close events.
    def __init__(self):
        super().__init__()
        
    def notify(self, eventArgs):
        global active_palette_instance
        try:
            if active_palette_instance:
                active_palette_instance.isVisible = False
        except Exception as e:
            log(f"Error handling palette close: {e}")


class ShowPaletteCommandExecuteHandler(adsk.core.CommandEventHandler):
    # Handle execution of the show palette command.
    def __init__(self):
        super().__init__()
        
    def notify(self, eventArgs):
        global active_palette_instance
        try:
            active_palette_instance = ui.palettes.itemById(BUTTON_PROPERTIES['palette_id'])
            if not active_palette_instance:
                active_palette_instance = ui.palettes.add(
                    BUTTON_PROPERTIES['palette_id'],
                    'Trackpuck Tools',
                    'TrackpuckTools.html',
                    True,   # isResizable
                    False,  # isModal  
                    True,   # isVisible
                    320,    # width
                    580     # height
                )
                active_palette_instance.setMinimumSize(320, 150)
                active_palette_instance.setMaximumSize(320, 600)
                active_palette_instance.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
                
                palette_close_handler = PaletteCloseEventHandler()
                active_palette_instance.closed.add(palette_close_handler)
                event_handlers_list.append(palette_close_handler)
                
                palette_incoming_handler = PaletteIncomingEventHandler(active_palette_instance)
                active_palette_instance.incomingFromHTML.add(palette_incoming_handler)
                event_handlers_list.append(palette_incoming_handler)

            if active_palette_instance:
                active_palette_instance.isVisible = True

        except Exception as e:
            log(f"Error showing palette: {e}")
            if ui:
                ui.messageBox(f'Failed to show palette:\n{traceback.format_exc()}')


class ShowPaletteCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    # Handle creation of the show palette command.
    def __init__(self):
        super().__init__()
        
    def notify(self, eventArgs):
        try:
            command = eventArgs.command
            execute_handler = ShowPaletteCommandExecuteHandler()
            command.execute.add(execute_handler)
            event_handlers_list.append(execute_handler)
        except Exception as e:
            if ui:
                ui.messageBox(f'Failed to create show palette command:\n{traceback.format_exc()}')


def cleanup_application():
    # Clean up all application resources and remove UI elements.
    global ui, active_palette_instance
    try:
        if ui:
            active_palette_instance = ui.palettes.itemById(BUTTON_PROPERTIES['palette_id'])
            if active_palette_instance:
                active_palette_instance.deleteMe()
                active_palette_instance = None
            command_definition = ui.commandDefinitions.itemById(BUTTON_PROPERTIES['id'])
            if command_definition:
                command_definition.deleteMe()
            addins_panel = ui.allToolbarPanels.itemById('SolidScriptsAddinsPanel')
            if addins_panel:
                control = addins_panel.controls.itemById(BUTTON_PROPERTIES['id'])
                if control:
                    control.deleteMe()
    except Exception as e:
        log(f"Error cleaning up application: {e}")


# -------------------------
# Fusion entry points
# -------------------------
def run(context):
    global VENDOR_ID, PRODUCT_ID, hid_device_path, app, ui, running, hid, device
    global SCALE_X, SCALE_Y, SCALE_Z, SCALE_RX, SCALE_RY, SCALE_RZ, MOTION_MODE

    try:
        log("TrackpuckTools starting...")
        app = adsk.core.Application.get()
        ui = app.userInterface
        log("Fusion app obtained")
        
        if VENDOR_ID is None or PRODUCT_ID is None:
            ui.messageBox("Invalid VENDOR_ID or PRODUCT_ID in config.json. Please check your configuration.")
            return

        saved_prefs = load_prefs()
        if saved_prefs:
            apply_prefs(saved_prefs)
            log(f"Applied saved preferences")

        # Set up palette button first
        cleanup_application()
        show_palette_command_definition = ui.commandDefinitions.itemById(BUTTON_PROPERTIES['id'])
        if not show_palette_command_definition:
            show_palette_command_definition = ui.commandDefinitions.addButtonDefinition(
                BUTTON_PROPERTIES['id'], 
                BUTTON_PROPERTIES['display_name'], 
                BUTTON_PROPERTIES['description'], 
                BUTTON_PROPERTIES['resources']
            )
            command_created_handler = ShowPaletteCommandCreatedHandler()
            show_palette_command_definition.commandCreated.add(command_created_handler)
            event_handlers_list.append(command_created_handler)
        addins_panel = ui.allToolbarPanels.itemById('SolidScriptsAddinsPanel')
        button_control = addins_panel.controls.addCommand(show_palette_command_definition)
        if button_control:
            button_control.isPromotedByDefault = True
            button_control.isPromoted = True

        global process_queue_event_handler
        process_queue_event_handler = ProcessQueueEventHandler()
        custom_event = app.registerCustomEvent(TP_QUEUE_EVENT_ID)
        custom_event.add(process_queue_event_handler)

        if not pull_libs():
            return
        if not import_libs():
            return

        activate_device_read(silent=True)

    except:
        if ui:
            ui.messageBox(traceback.format_exc())


def stop(context):
    log(f"TrackpuckTools stopping...")
    try:
        deactivate_device_read()
        cleanup_application()
    except:
        log(f"Error stopping application: {e}")
    log(f"TrackpuckTools stopped.")
    adsk.terminate()
