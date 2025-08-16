class SlideshowApp {
    constructor() {
        console.log('SlideshowApp constructor called');
        this.socket = io();
        this.devices = new Map();
        this.selectedDevices = new Set();
        this.currentAuthDevice = null;
        this.pairingTriggered = false;
        
        this.initializeEventListeners();
        this.initializeSocketListeners();
        this.loadDirectories();
        this.loadDevices();
        console.log('SlideshowApp initialization complete');
    }
    
    initializeEventListeners() {
        console.log('Initializing event listeners');
        // Device scanning
        const scanBtn = document.getElementById('scan-devices-btn');
        if (scanBtn) {
            console.log('Found scan button, adding event listener');
            scanBtn.addEventListener('click', () => {
                console.log('Scan button clicked');
                this.scanDevices();
            });
        } else {
            console.error('scan-devices-btn not found!');
        }
        
        // Configuration form
        document.getElementById('config-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.configureSlideshow();
        });
        
        // Slideshow controls
        document.getElementById('start-btn').addEventListener('click', () => this.startSlideshow());
        document.getElementById('stop-btn').addEventListener('click', () => this.stopSlideshow());
        document.getElementById('next-btn').addEventListener('click', () => this.nextImages());
        document.getElementById('prev-btn').addEventListener('click', () => this.previousImages());
        
        // Directory refresh
        document.getElementById('refresh-directories').addEventListener('click', () => this.loadDirectories());
        
        // Display time updates
        document.getElementById('display-time').addEventListener('change', (e) => {
            if (this.isRunning) {
                this.updateDisplayTime(parseInt(e.target.value));
            }
        });
        
        // Clear log
        document.getElementById('clear-log').addEventListener('click', () => this.clearLog());
        
        // Video mode toggle
        document.getElementById('video-mode').addEventListener('change', (e) => this.toggleVideoMode(e.target.checked));
        
        // PIN authentication
        document.getElementById('submit-pin').addEventListener('click', () => this.submitPin());
        document.getElementById('cancel-pin').addEventListener('click', () => this.cancelPin());
        document.getElementById('pin-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.submitPin();
            }
        });
    }
    
    initializeSocketListeners() {
        this.socket.on('connect', () => {
            this.addLogEntry('Connected to server', 'success');
            this.socket.emit('request_status');
            // Also refresh full state on connection
            setTimeout(() => this.refreshFullStatus(), 500);
        });
        
        this.socket.on('slideshow_status', (data) => {
            this.updateSlideshowStatus(data);
        });
        
        this.socket.on('error', (data) => {
            this.addLogEntry(`Error: ${data.message}`, 'error');
            if (data.device_id) {
                this.updateDeviceStatus(data.device_id, false);
            }
        });
        
        this.socket.on('authentication_required', (data) => {
            console.log('Authentication required for device:', data);
            this.currentAuthDevice = data.device_id;
            this.startPairingProcess(data.device_id);
        });
        
        this.socket.on('video_progress', (data) => {
            this.updateVideoProgress(data);
        });
        
        this.socket.on('slideshow_status', (data) => {
            this.updateSlideshowStatus(data);
            
            // Check if slideshow started but videos failed to stream (indicates pairing needed)
            if (data.type === 'slideshow_started' && !this.pairingTriggered) {
                setTimeout(() => {
                    this.checkForStreamingFailures();
                }, 2000); // Give time for streaming to start
            }
        });
    }
    
    updateVideoProgress(data) {
        const progressSection = document.getElementById('video-progress-section');
        const progressBar = document.getElementById('video-progress-bar');
        const progressText = document.getElementById('video-progress-text');
        
        if (data.stage === 'starting') {
            progressSection.style.display = 'block';
            progressBar.style.width = '0%';
            progressText.textContent = 'Starting video creation...';
            // Disable start button during video creation
            document.getElementById('start-btn').disabled = true;
        } else if (data.stage === 'creating') {
            progressSection.style.display = 'block';
            const percentage = Math.round((data.current_frame / data.total_frames) * 100);
            progressBar.style.width = `${percentage}%`;
            progressText.textContent = `Creating video: ${data.current_frame}/${data.total_frames} frames (${percentage}%)`;
        } else if (data.stage === 'completed') {
            progressBar.style.width = '100%';
            progressText.textContent = 'Video creation completed!';
            // Hide progress after a short delay
            setTimeout(() => {
                progressSection.style.display = 'none';
            }, 2000);
        } else if (data.stage === 'error') {
            progressBar.classList.add('bg-danger');
            progressText.textContent = `Video creation failed: ${data.error}`;
            setTimeout(() => {
                progressSection.style.display = 'none';
                // Re-enable start button on error
                document.getElementById('start-btn').disabled = false;
            }, 3000);
        }
    }
    
    async refreshFullStatus() {
        try {
            const response = await fetch('/api/slideshow-status');
            const data = await response.json();
            
            if (data.success) {
                const status = data.status;
                
                // Restore selected devices from active_devices
                this.selectedDevices.clear();
                if (status.active_devices) {
                    status.active_devices.forEach(deviceId => {
                        this.selectedDevices.add(deviceId);
                    });
                }
                
                // Restore slideshow configuration
                if (status.images_directory) {
                    const directorySelect = document.getElementById('images-directory');
                    if (directorySelect) {
                        directorySelect.value = status.images_directory;
                    }
                }
                
                if (status.display_time) {
                    const displayTimeInput = document.getElementById('display-time');
                    if (displayTimeInput) {
                        displayTimeInput.value = status.display_time;
                    }
                }
                
                // Restore video mode settings
                if (status.video_mode !== undefined) {
                    const videoModeCheckbox = document.getElementById('video-mode');
                    if (videoModeCheckbox) {
                        videoModeCheckbox.checked = status.video_mode;
                        // Trigger the change event to show/hide transition duration
                        this.toggleVideoMode(status.video_mode);
                    }
                }
                
                if (status.transition_duration) {
                    const transitionInput = document.getElementById('transition-duration');
                    if (transitionInput) {
                        transitionInput.value = status.transition_duration;
                    }
                }
                
                // Update device selection checkboxes and display
                this.updateSelectedDevicesDisplay();
                this.updateDevicesDisplay(); // This will check the correct checkboxes
                
                // Add type for consistency with WebSocket messages
                status.type = 'full_status';
                this.updateSlideshowStatus(status);
            }
        } catch (error) {
            console.error('Error refreshing status:', error);
        }
    }
    
    async scanDevices() {
        console.log('scanDevices method called');
        const btn = document.getElementById('scan-devices-btn');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-arrow-repeat spinner-border spinner-border-sm"></i> Scanning...';
        btn.disabled = true;
        
        try {
            console.log('Making API request to /api/scan-devices');
            const response = await fetch('/api/scan-devices', { method: 'POST' });
            const data = await response.json();
            console.log('API response:', data);
            
            if (data.success) {
                console.log(`Found ${data.devices.length} devices`);
                this.addLogEntry(`Found ${data.devices.length} devices`, 'success');
                // Update local devices map with scanned devices
                data.devices.forEach(device => {
                    console.log('Adding device to map:', device.name, device.device_id);
                    this.devices.set(device.device_id, device);
                });
                console.log('Devices map size:', this.devices.size);
                this.updateDevicesDisplay();
            } else {
                console.error('Scan failed:', data.error);
                this.addLogEntry(`Scan failed: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Scan error:', error);
            this.addLogEntry(`Scan error: ${error.message}`, 'error');
        }
        
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
    
    async loadDevices() {
        try {
            const response = await fetch('/api/devices');
            const data = await response.json();
            
            if (data.success) {
                this.devices.clear();
                data.devices.forEach(device => {
                    this.devices.set(device.device_id, device);
                });
                this.updateDevicesDisplay();
            }
        } catch (error) {
            this.addLogEntry(`Error loading devices: ${error.message}`, 'error');
        }
    }
    
    async loadDirectories() {
        try {
            const response = await fetch('/api/directories');
            const data = await response.json();
            
            const select = document.getElementById('images-directory');
            select.innerHTML = '<option value="">Select directory...</option>';
            
            if (data.success) {
                data.directories.forEach(dir => {
                    const option = document.createElement('option');
                    option.value = dir.path;
                    option.textContent = `${dir.name} (${dir.image_count} images)`;
                    select.appendChild(option);
                });
            }
        } catch (error) {
            this.addLogEntry(`Error loading directories: ${error.message}`, 'error');
        }
    }
    
    updateDevicesDisplay() {
        const container = document.getElementById('devices-container');
        
        if (this.devices.size === 0) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <p class="text-muted">No devices found. Click "Scan" to discover AirPlay devices.</p>
                </div>
            `;
            return;
        }
        
        const devicesHtml = Array.from(this.devices.values()).map(device => `
            <div class="device-card card mb-2 ${device.is_active ? 'device-connected' : 'device-disconnected'}" 
                 data-device-id="${device.device_id}">
                <div class="card-body py-2">
                    <div class="row align-items-center">
                        <div class="col-8">
                            <div class="fw-bold">${device.name}</div>
                            <div class="small text-muted">${device.address}</div>
                        </div>
                        <div class="col-4 text-end">
                            <div class="form-check form-switch mb-1">
                                <input class="form-check-input device-select" type="checkbox" 
                                       data-device-id="${device.device_id}"
                                       ${this.selectedDevices.has(device.device_id) ? 'checked' : ''}>
                                <label class="form-check-label small">Select</label>
                            </div>
                            <button class="btn btn-sm ${device.is_active ? 'btn-outline-danger' : 'btn-outline-success'} connect-btn"
                                    data-device-id="${device.device_id}">
                                ${device.is_active ? 'Disconnect' : 'Connect'}
                            </button>
                            <br>
                            <button class="btn btn-sm btn-outline-primary pair-btn mt-1"
                                    data-device-id="${device.device_id}">
                                <i class="bi bi-shield-lock"></i> Pair AirPlay
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
        
        container.innerHTML = devicesHtml;
        
        // Add event listeners
        container.querySelectorAll('.connect-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                console.log('Connect button clicked');
                const deviceId = e.target.getAttribute('data-device-id');
                console.log('Device ID:', deviceId);
                const device = this.devices.get(deviceId);
                console.log('Device:', device);
                if (device && device.is_active) {
                    console.log('Disconnecting device');
                    this.disconnectDevice(deviceId);
                } else {
                    console.log('Connecting device');
                    this.connectDevice(deviceId);
                }
            });
        });
        
        container.querySelectorAll('.device-select').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const deviceId = e.target.getAttribute('data-device-id');
                if (e.target.checked) {
                    this.selectedDevices.add(deviceId);
                } else {
                    this.selectedDevices.delete(deviceId);
                }
                this.updateSelectedDevicesDisplay();
            });
        });
        
        container.querySelectorAll('.pair-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const deviceId = e.target.getAttribute('data-device-id');
                this.startPairingProcess(deviceId);
            });
        });
    }
    
    updateSelectedDevicesDisplay() {
        const container = document.getElementById('selected-devices');
        
        if (this.selectedDevices.size === 0) {
            container.innerHTML = '<div class="text-muted">No devices selected</div>';
            return;
        }
        
        const selectedHtml = Array.from(this.selectedDevices).map(deviceId => {
            const device = this.devices.get(deviceId);
            return `
                <span class="badge bg-primary me-1 mb-1">
                    ${device ? device.name : deviceId}
                    <i class="bi bi-x-circle ms-1" onclick="app.removeSelectedDevice('${deviceId}')" style="cursor: pointer;"></i>
                </span>
            `;
        }).join('');
        
        container.innerHTML = selectedHtml;
    }
    
    removeSelectedDevice(deviceId) {
        this.selectedDevices.delete(deviceId);
        this.updateSelectedDevicesDisplay();
        
        // Update checkbox
        const checkbox = document.querySelector(`input[data-device-id="${deviceId}"]`);
        if (checkbox) {
            checkbox.checked = false;
        }
    }
    
    async connectDevice(deviceId) {
        console.log('connectDevice called with deviceId:', deviceId);
        try {
            console.log('Making connect API request');
            const response = await fetch('/api/connect-device', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device_id: deviceId })
            });
            
            const data = await response.json();
            console.log('Connect API response:', data);
            
            if (data.success) {
                console.log('Connection successful');
                this.addLogEntry(`Connected to device ${deviceId}`, 'success');
                this.updateDeviceStatus(deviceId, true);
            } else {
                console.error('Connection failed:', data.error);
                this.addLogEntry(`Failed to connect to ${deviceId}: ${data.error}`, 'error');
                
                // If connection failed due to pairing requirement, start pairing process
                if (data.error && data.error.includes('pair')) {
                    this.addLogEntry(`Starting pairing process for device ${deviceId}`, 'info');
                    await this.startPairingProcess(deviceId);
                }
            }
        } catch (error) {
            console.error('Connection error:', error);
            this.addLogEntry(`Connection error: ${error.message}`, 'error');
        }
    }
    
    async startPairingProcess(deviceId) {
        try {
            const response = await fetch('/api/start-pairing', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device_id: deviceId })
            });
            
            const data = await response.json();
            console.log('Pairing start response:', data);
            
            if (data.success) {
                const device = this.devices.get(deviceId);
                const deviceName = device ? device.name : deviceId;
                this.showPinModal(deviceId, data.device_provides_pin, deviceName);
            } else {
                this.addLogEntry(`Failed to start pairing: ${data.error}`, 'error');
            }
        } catch (error) {
            this.addLogEntry(`Pairing start error: ${error.message}`, 'error');
        }
    }
    
    showPinModal(deviceId, deviceProvidesPin, deviceName) {
        this.currentAuthDevice = deviceId;
        
        document.getElementById('device-name').textContent = deviceName;
        document.getElementById('pin-input').value = '';
        
        // Update modal content based on PIN flow direction
        const modalBody = document.querySelector('#pinModal .modal-body');
        if (deviceProvidesPin) {
            modalBody.innerHTML = `
                <p>Enter the PIN displayed on your <span id="device-name">${deviceName}</span>:</p>
                <input type="text" id="pin-input" class="form-control" placeholder="Enter 4-digit PIN" maxlength="4">
            `;
        } else {
            // Generate a random 4-digit PIN for the user to enter on their Apple TV
            const generatedPin = Math.floor(1000 + Math.random() * 9000).toString();
            modalBody.innerHTML = `
                <p>Enter this PIN on your <span id="device-name">${deviceName}</span>:</p>
                <div class="text-center">
                    <h2 class="badge bg-primary fs-1">${generatedPin}</h2>
                </div>
                <input type="hidden" id="pin-input" value="${generatedPin}">
            `;
        }
        
        const modal = new bootstrap.Modal(document.getElementById('pinModal'));
        modal.show();
        
        this.addLogEntry(`PIN authentication required for ${deviceName}`, 'info');
    }
    
    async disconnectDevice(deviceId) {
        try {
            const response = await fetch('/api/disconnect-device', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device_id: deviceId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.addLogEntry(`Disconnected from device ${deviceId}`, 'info');
                this.updateDeviceStatus(deviceId, false);
            }
        } catch (error) {
            this.addLogEntry(`Disconnect error: ${error.message}`, 'error');
        }
    }
    
    updateDeviceStatus(deviceId, isActive) {
        const device = this.devices.get(deviceId);
        if (device) {
            device.is_active = isActive;
            this.updateDevicesDisplay();
        }
    }
    
    toggleVideoMode(enabled) {
        const transitionGroup = document.getElementById('transition-duration-group');
        if (enabled) {
            transitionGroup.style.display = 'block';
            this.addLogEntry('Video mode enabled - will create video files with transitions', 'info');
        } else {
            transitionGroup.style.display = 'none';
            this.addLogEntry('Video mode disabled - will stream individual images', 'info');
        }
    }
    
    async configureSlideshow() {
        const imagesDirectory = document.getElementById('images-directory').value;
        const displayTime = parseInt(document.getElementById('display-time').value);
        const videoMode = document.getElementById('video-mode').checked;
        const transitionDuration = parseFloat(document.getElementById('transition-duration').value);
        
        if (!imagesDirectory) {
            this.addLogEntry('Please select an images directory', 'error');
            return;
        }
        
        if (this.selectedDevices.size === 0) {
            this.addLogEntry('Please select at least one device', 'error');
            return;
        }
        
        try {
            const config = {
                images_directory: imagesDirectory,
                devices: Array.from(this.selectedDevices),
                display_time: displayTime,
                video_mode: videoMode
            };
            
            if (videoMode) {
                config.transition_duration = transitionDuration;
            }
            
            const response = await fetch('/api/configure-slideshow', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            const data = await response.json();
            
            if (data.success) {
                const modeText = videoMode ? 'video mode with transitions' : 'image mode';
                this.addLogEntry(`Slideshow configured successfully in ${modeText}`, 'success');
            } else {
                this.addLogEntry(`Configuration failed: ${data.error}`, 'error');
            }
        } catch (error) {
            this.addLogEntry(`Configuration error: ${error.message}`, 'error');
        }
    }
    
    async startSlideshow() {
        try {
            const response = await fetch('/api/start-slideshow', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                this.addLogEntry('Slideshow started', 'success');
            } else {
                this.addLogEntry(`Failed to start slideshow: ${data.error}`, 'error');
            }
        } catch (error) {
            this.addLogEntry(`Start error: ${error.message}`, 'error');
        }
    }
    
    async stopSlideshow() {
        try {
            const response = await fetch('/api/stop-slideshow', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                this.addLogEntry('Slideshow stopped', 'info');
            }
        } catch (error) {
            this.addLogEntry(`Stop error: ${error.message}`, 'error');
        }
    }
    
    async nextImages() {
        try {
            const response = await fetch('/api/next-images', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                this.addLogEntry('Advanced to next images', 'info');
            }
        } catch (error) {
            this.addLogEntry(`Next error: ${error.message}`, 'error');
        }
    }
    
    async previousImages() {
        try {
            const response = await fetch('/api/previous-images', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                this.addLogEntry('Went back to previous images', 'info');
            }
        } catch (error) {
            this.addLogEntry(`Previous error: ${error.message}`, 'error');
        }
    }
    
    async updateDisplayTime(displayTime) {
        try {
            const response = await fetch('/api/update-display-time', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ display_time: displayTime })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.addLogEntry(`Display time updated to ${displayTime} seconds`, 'info');
            }
        } catch (error) {
            this.addLogEntry(`Display time update error: ${error.message}`, 'error');
        }
    }
    
    updateSlideshowStatus(data) {
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('slideshow-status');
        const imagesInfo = document.getElementById('images-info');
        const devicesInfo = document.getElementById('devices-info');
        
        if (data.type === 'full_status' || data.is_running !== undefined) {
            this.isRunning = data.is_running;
            
            statusText.textContent = data.is_running ? 'Running' : 'Stopped';
            statusIndicator.className = `status-indicator ${data.is_running ? 'status-running' : 'status-stopped'}`;
            
            // Update controls
            document.getElementById('start-btn').disabled = data.is_running;
            document.getElementById('stop-btn').disabled = !data.is_running;
            document.getElementById('next-btn').disabled = !data.is_running;
            document.getElementById('prev-btn').disabled = !data.is_running;
            
            // Update info
            imagesInfo.textContent = `${data.images_count || 0} images loaded`;
            devicesInfo.textContent = `${data.active_devices?.length || 0} devices selected`;
            
            // Update statistics
            if (data.stats) {
                document.getElementById('stat-images').textContent = data.stats.images_displayed || 0;
                document.getElementById('stat-cycles').textContent = data.stats.cycles_completed || 0;
                document.getElementById('stat-errors').textContent = data.stats.errors || 0;
            }
            document.getElementById('stat-devices').textContent = data.connected_devices?.length || 0;
        }
        
        // Handle specific status updates
        if (data.type === 'slideshow_started') {
            this.addLogEntry('Slideshow started', 'success');
        } else if (data.type === 'slideshow_stopped') {
            this.addLogEntry('Slideshow stopped', 'info');
        } else if (data.type === 'images_displayed' && data.distribution) {
            const distributionText = Object.entries(data.distribution)
                .map(([device, image]) => `${device}: ${image}`)
                .join(', ');
            this.addLogEntry(`Displaying: ${distributionText}`, 'info');
        } else if (data.type === 'cycle_completed') {
            this.addLogEntry(`Completed cycle ${data.cycles}`, 'success');
        } else if (data.type === 'configuration_updated') {
            const modeText = data.video_mode ? `video mode (${data.transition_duration}s transitions)` : 'image mode';
            this.addLogEntry(`Configuration updated: ${data.images_count} images, ${data.devices_count} devices, ${modeText}`, 'info');
        } else if (data.type === 'video_slideshow_started') {
            this.addLogEntry(`Video slideshow started: ${data.successful_streams}/${data.devices_streaming} devices streaming successfully`, 'success');
        } else if (data.type === 'video_slideshow_running') {
            // Periodic update for video mode - less verbose
        }
    }
    
    async startPairingProcess(deviceId) {
        try {
            this.addLogEntry(`Starting pairing process for device ${deviceId}`, 'info');
            
            const response = await fetch('/api/start-pairing', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device_id: deviceId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentAuthDevice = deviceId;
                this.showPinModal(deviceId, data.device_provides_pin, data.device_name);
            } else {
                this.addLogEntry(`Failed to start pairing: ${data.error}`, 'error');
            }
        } catch (error) {
            this.addLogEntry(`Pairing start error: ${error.message}`, 'error');
        }
    }
    
    showPinModal(deviceId, deviceProvidesPin, deviceName) {
        const device = this.devices.get(deviceId);
        const displayName = deviceName || (device ? device.name : deviceId);
        
        document.getElementById('device-name').textContent = displayName;
        document.getElementById('pin-input').value = '';
        
        // Update modal text based on who provides the PIN
        const modalBody = document.querySelector('#pinModal .modal-body');
        if (deviceProvidesPin) {
            modalBody.innerHTML = `
                <p>Enter the PIN displayed on your <span id="device-name">${displayName}</span>:</p>
                <input type="text" id="pin-input" class="form-control" placeholder="Enter 4-digit PIN" maxlength="4">
            `;
        } else {
            // Generate a random 4-digit PIN for user to enter on device
            const generatedPin = Math.floor(1000 + Math.random() * 9000).toString();
            modalBody.innerHTML = `
                <p>Enter this PIN on your <span id="device-name">${displayName}</span>:</p>
                <div class="text-center my-3">
                    <h2 class="text-primary" id="generated-pin">${generatedPin}</h2>
                </div>
                <input type="hidden" id="pin-input" value="${generatedPin}">
                <p class="text-muted small">Click Submit after entering the PIN on your device</p>
            `;
        }
        
        const modal = new bootstrap.Modal(document.getElementById('pinModal'));
        modal.show();
        
        this.addLogEntry(`Pairing started for device ${displayName}`, 'info');
    }
    
    async submitPin() {
        const pinInput = document.getElementById('pin-input');
        const pin = pinInput.value;
        
        if (!pin || !this.currentAuthDevice) {
            return;
        }
        
        // Validate PIN format
        if (pin.length !== 4 || !/^\d{4}$/.test(pin)) {
            this.addLogEntry('PIN must be exactly 4 digits', 'error');
            return;
        }
        
        try {
            this.addLogEntry(`Completing pairing for device ${this.currentAuthDevice}`, 'info');
            
            // Disable submit button to prevent double submission
            const submitBtn = document.getElementById('submit-pin');
            const originalText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Pairing...';
            
            const response = await fetch('/api/complete-pairing', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    device_id: this.currentAuthDevice,
                    pin: pin
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.addLogEntry('Device paired and connected successfully', 'success');
                const modal = bootstrap.Modal.getInstance(document.getElementById('pinModal'));
                modal.hide();
                this.updateDeviceStatus(this.currentAuthDevice, true);
                this.currentAuthDevice = null;
            } else {
                this.addLogEntry(`Pairing failed: ${data.error}`, 'error');
                // Reset PIN input for retry
                if (pinInput.type !== 'hidden') {
                    pinInput.value = '';
                    pinInput.focus();
                }
            }
            
            // Re-enable submit button
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
            
        } catch (error) {
            this.addLogEntry(`Pairing error: ${error.message}`, 'error');
            
            // Re-enable submit button on error
            const submitBtn = document.getElementById('submit-pin');
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Submit';
        }
    }
    
    async cancelPin() {
        if (this.currentAuthDevice) {
            try {
                const response = await fetch('/api/cancel-pairing', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ device_id: this.currentAuthDevice })
                });
                
                const data = await response.json();
                if (data.success) {
                    this.addLogEntry('Pairing cancelled', 'info');
                } else {
                    this.addLogEntry(`Failed to cancel pairing: ${data.error}`, 'warning');
                }
            } catch (error) {
                this.addLogEntry(`Cancel pairing error: ${error.message}`, 'error');
            }
            
            this.currentAuthDevice = null;
        }
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('pinModal'));
        modal.hide();
    }
    
    addLogEntry(message, type = 'info') {
        const log = document.getElementById('activity-log');
        const timestamp = new Date().toLocaleTimeString();
        
        const entry = document.createElement('div');
        entry.className = `log-entry log-${type}`;
        entry.innerHTML = `<span class="text-muted">[${timestamp}]</span> ${message}`;
        
        log.appendChild(entry);
        log.scrollTop = log.scrollHeight;
        
        // Keep only last 100 entries
        while (log.children.length > 100) {
            log.removeChild(log.firstChild);
        }
    }
    
    clearLog() {
        const log = document.getElementById('activity-log');
        log.innerHTML = '<div class="log-entry log-info">Log cleared...</div>';
    }
    
    async checkForStreamingFailures() {
        // Check activity log for AirPlay streaming failures
        const logEntries = document.querySelectorAll('#activity-log .log-entry');
        const recentEntries = Array.from(logEntries).slice(-10); // Check last 10 entries
        
        for (const entry of recentEntries) {
            const text = entry.textContent.toLowerCase();
            if (text.includes('failed to stream') || 
                text.includes('does not support') || 
                text.includes('not supported') ||
                text.includes('play_url is not supported')) {
                
                this.addLogEntry('Detected AirPlay streaming failure - starting pairing process', 'info');
                this.pairingTriggered = true;
                
                // Get the first selected device and start pairing
                const firstDevice = Array.from(this.selectedDevices)[0];
                if (firstDevice) {
                    await this.startPairingProcess(firstDevice);
                }
                break;
            }
        }
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new SlideshowApp();
});