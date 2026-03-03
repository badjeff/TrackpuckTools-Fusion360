let darkMode = null;
let defaultConfig = {};
let savedPrefs = {};
let deviceConnected = false;

function sendPaletteReadyWhenAdskAvailable() {
    if (window.adsk && typeof adsk.fusionSendData === 'function') {
        adsk.fusionSendData('paletteReady', '');
    } else {
        setTimeout(sendPaletteReadyWhenAdskAvailable, 50);
    }
}

function updateDeviceButtons() {
    const activateBtn = document.getElementById('activateBtn');
    const deactivateBtn = document.getElementById('deactivateBtn');
    if (activateBtn && deactivateBtn) {
        const activateLed = activateBtn.querySelector('.led');
        const deactivateLed = deactivateBtn.querySelector('.led');
        if (deviceConnected) {
            activateBtn.style.display = 'none';
            deactivateBtn.style.display = '';
            if (deactivateLed) deactivateLed.classList.add('active');
        } else {
            activateBtn.style.display = '';
            deactivateBtn.style.display = 'none';
            if (activateLed) activateLed.classList.remove('active');
        }
    }
}

function loadDefaultConfig() {
    fetch('config.json')
        .then(response => response.json())
        .then(config => {
            defaultConfig = config;
        })
        .catch(() => {
            defaultConfig = {};
        });
}

function initPalette() {
    sendPaletteReadyWhenAdskAvailable();
    loadDefaultConfig();
    updateDeviceButtons();

    const closeBtn = document.getElementById('closeBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            adsk.fusionSendData('closePalette', JSON.stringify({ action: 'close' }));
        });
    }

    const deactivateBtn = document.getElementById('deactivateBtn');
    if (deactivateBtn) {
        deactivateBtn.addEventListener('click', function() {
            adsk.fusionSendData('deactivateTrackpuck', JSON.stringify({ action: 'deactivate' }));
        });
    }

    const activateBtn = document.getElementById('activateBtn');
    if (activateBtn) {
        activateBtn.addEventListener('click', function() {
            adsk.fusionSendData('activateTrackpuck', JSON.stringify({ action: 'activate' }));
        });
    }

    const savePrefBtn = document.getElementById('savePrefBtn');
    if (savePrefBtn) {
        savePrefBtn.addEventListener('click', function() {
            const prefs = {
                NEAR_DISTANCE: parseFloat(document.getElementById('nearDistance').value),
                FAR_DISTANCE: parseFloat(document.getElementById('farDistance').value),
                NEAR_TRANS_SENSITIVITY: parseFloat(document.getElementById('nearSensitivity').value),
                FAR_TRANS_SENSITIVITY: parseFloat(document.getElementById('farSensitivity').value),
                ROTATION_SENSITIVITY: parseFloat(document.getElementById('rotationSensitivity').value),
                MOTION_MODE: parseInt(document.getElementById('motionModeSelect').value),
                SCALE_X: parseFloat(document.getElementById('scaleX').value),
                SCALE_Y: parseFloat(document.getElementById('scaleY').value),
                SCALE_Z: parseFloat(document.getElementById('scaleZ').value),
                SCALE_RX: parseFloat(document.getElementById('scaleRX').value),
                SCALE_RY: parseFloat(document.getElementById('scaleRY').value),
                SCALE_RZ: parseFloat(document.getElementById('scaleRZ').value)
            };
            adsk.fusionSendData('savePrefs', JSON.stringify(prefs));
        });
    }

    const loadPrefBtn = document.getElementById('loadPrefBtn');
    if (loadPrefBtn) {
        loadPrefBtn.addEventListener('click', function() {
            adsk.fusionSendData('loadPrefs', '');
        });
    }

    const resetAllBtn = document.getElementById('resetAllBtn');
    if (resetAllBtn) {
        resetAllBtn.addEventListener('click', function() {
            const keys = ['NEAR_DISTANCE', 'FAR_DISTANCE', 'NEAR_TRANS_SENSITIVITY', 'FAR_TRANS_SENSITIVITY', 'ROTATION_SENSITIVITY', 'MOTION_MODE', 'SCALE_X', 'SCALE_Y', 'SCALE_Z', 'SCALE_RX', 'SCALE_RY', 'SCALE_RZ'];
            keys.forEach(key => {
                if (defaultConfig[key] !== undefined) {
                    adsk.fusionSendData('updateConfig', JSON.stringify({ key: key, value: defaultConfig[key] }));
                }
            });
            document.getElementById('nearDistance').value = defaultConfig.NEAR_DISTANCE.toFixed(1);
            document.getElementById('farDistance').value = defaultConfig.FAR_DISTANCE.toFixed(1);
            document.getElementById('nearSensitivity').value = defaultConfig.NEAR_TRANS_SENSITIVITY.toFixed(3);
            document.getElementById('farSensitivity').value = defaultConfig.FAR_TRANS_SENSITIVITY.toFixed(3);
            document.getElementById('rotationSensitivity').value = defaultConfig.ROTATION_SENSITIVITY.toFixed(3);
            document.getElementById('motionModeSelect').value = defaultConfig.MOTION_MODE;
            document.getElementById('scaleX').value = defaultConfig.SCALE_X.toFixed(1);
            document.getElementById('scaleY').value = defaultConfig.SCALE_Y.toFixed(1);
            document.getElementById('scaleZ').value = defaultConfig.SCALE_Z.toFixed(1);
            document.getElementById('scaleRX').value = defaultConfig.SCALE_RX.toFixed(1);
            document.getElementById('scaleRY').value = defaultConfig.SCALE_RY.toFixed(1);
            document.getElementById('scaleRZ').value = defaultConfig.SCALE_RZ.toFixed(1);
        });
    }

    const nearDistance = document.getElementById('nearDistance');
    if (nearDistance) {
        nearDistance.addEventListener('change', function() {
            adsk.fusionSendData('updateConfig', JSON.stringify({ key: 'NEAR_DISTANCE', value: parseFloat(this.value) }));
        });
    }

    const farDistance = document.getElementById('farDistance');
    if (farDistance) {
        farDistance.addEventListener('change', function() {
            adsk.fusionSendData('updateConfig', JSON.stringify({ key: 'FAR_DISTANCE', value: parseFloat(this.value) }));
        });
    }

    const nearSensitivity = document.getElementById('nearSensitivity');
    if (nearSensitivity) {
        nearSensitivity.addEventListener('change', function() {
            adsk.fusionSendData('updateConfig', JSON.stringify({ key: 'NEAR_TRANS_SENSITIVITY', value: parseFloat(this.value) }));
        });
    }

    const farSensitivity = document.getElementById('farSensitivity');
    if (farSensitivity) {
        farSensitivity.addEventListener('change', function() {
            adsk.fusionSendData('updateConfig', JSON.stringify({ key: 'FAR_TRANS_SENSITIVITY', value: parseFloat(this.value) }));
        });
    }

    const rotationSensitivity = document.getElementById('rotationSensitivity');
    if (rotationSensitivity) {
        rotationSensitivity.addEventListener('change', function() {
            adsk.fusionSendData('updateConfig', JSON.stringify({ key: 'ROTATION_SENSITIVITY', value: parseFloat(this.value) }));
        });
    }

    const motionModeSelect = document.getElementById('motionModeSelect');
    if (motionModeSelect) {
        motionModeSelect.addEventListener('change', function() {
            adsk.fusionSendData('updateConfig', JSON.stringify({ key: 'MOTION_MODE', value: parseInt(this.value) }));
        });
    }

    const scaleKeys = ['scaleX', 'scaleY', 'scaleZ', 'scaleRX', 'scaleRY', 'scaleRZ'];
    const scalePyKeys = ['SCALE_X', 'SCALE_Y', 'SCALE_Z', 'SCALE_RX', 'SCALE_RY', 'SCALE_RZ'];
    scaleKeys.forEach((id, index) => {
        const elem = document.getElementById(id);
        if (elem) {
            elem.addEventListener('change', function() {
                adsk.fusionSendData('updateConfig', JSON.stringify({ key: scalePyKeys[index], value: parseFloat(this.value) }));
            });
        }
    });
}

function savePrefs() {
    const prefs = {};
    adsk.fusionSendData('savePrefs', JSON.stringify(prefs));
}

function loadPrefs(prefs) {
    if (prefs.darkMode !== undefined) {
        darkMode = prefs.darkMode;
        document.documentElement.classList.toggle('dark-mode', darkMode);
    }
}

function handleIncomingData(action, data) {
    try {
        switch (action) {
            case 'loadPrefs':
                loadPrefs(JSON.parse(data));
                break;
            case 'loadSavedPrefs':
                savedPrefs = JSON.parse(data);
                break;
            case 'setTheme':
                const themeData = JSON.parse(data);
                if (themeData.darkMode !== undefined) {
                    darkMode = themeData.darkMode;
                    document.documentElement.classList.toggle('dark-mode', darkMode);
                }
                break;
            case 'updateSensitivity':
                const elem = document.getElementById('dynTransSensitivity');
                if (elem) {
                    elem.value = data;
                }
                break;
            case 'loadConfig':
                const config = JSON.parse(data);
                if (config.NEAR_DISTANCE !== undefined) {
                    const nearDist = document.getElementById('nearDistance');
                    if (nearDist) nearDist.value = config.NEAR_DISTANCE.toFixed(1);
                }
                if (config.FAR_DISTANCE !== undefined) {
                    const farDist = document.getElementById('farDistance');
                    if (farDist) farDist.value = config.FAR_DISTANCE.toFixed(1);
                }
                if (config.NEAR_TRANS_SENSITIVITY !== undefined) {
                    const nearSens = document.getElementById('nearSensitivity');
                    if (nearSens) nearSens.value = config.NEAR_TRANS_SENSITIVITY.toFixed(3);
                }
                if (config.FAR_TRANS_SENSITIVITY !== undefined) {
                    const farSens = document.getElementById('farSensitivity');
                    if (farSens) farSens.value = config.FAR_TRANS_SENSITIVITY.toFixed(3);
                }
                if (config.ROTATION_SENSITIVITY !== undefined) {
                    const rotSens = document.getElementById('rotationSensitivity');
                    if (rotSens) rotSens.value = config.ROTATION_SENSITIVITY.toFixed(3);
                }
                if (config.MOTION_MODE !== undefined) {
                    const motionMode = document.getElementById('motionModeSelect');
                    if (motionMode) motionMode.value = config.MOTION_MODE;
                }
                if (config.SCALE_X !== undefined) {
                    document.getElementById('scaleX').value = config.SCALE_X.toFixed(1);
                    document.getElementById('scaleY').value = config.SCALE_Y.toFixed(1);
                    document.getElementById('scaleZ').value = config.SCALE_Z.toFixed(1);
                    document.getElementById('scaleRX').value = config.SCALE_RX.toFixed(1);
                    document.getElementById('scaleRY').value = config.SCALE_RY.toFixed(1);
                    document.getElementById('scaleRZ').value = config.SCALE_RZ.toFixed(1);
                }
                break;
            case 'deviceState':
                const stateData = JSON.parse(data);
                deviceConnected = stateData.connected;
                updateDeviceButtons();
                break;
            default:
                break;
        }
    } catch (e) {
        console.log(e);
        return 'FAILED';
    }
    return JSON.stringify({ status: 'OK' });
}

window.fusionJavaScriptHandler = {
    handle: function (actionString, dataString) {
        handleIncomingData(actionString, dataString);
    }
};

document.addEventListener('DOMContentLoaded', function () {
    initPalette();
});
