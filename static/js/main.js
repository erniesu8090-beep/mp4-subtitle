let currentMode = 'hard'; // Default mode is hardburn
let eventSource = null;

// Initialize layout when content is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Make sure elements are set up correctly
    setMode('hard');
    updatePreview();
});

/**
 * Trigger file selection dialog from backend
 * @param {string} mode - 'video', 'srt', or 'output'
 */
async function selectFile(mode) {
    const videoPath = document.getElementById('video-path').value;
    let defaultName = '';
    
    if (mode === 'output' && videoPath) {
        // Extract filename and suggest a new one
        const baseName = videoPath.split(/[\\/]/).pop();
        const lastDot = baseName.lastIndexOf('.');
        if (lastDot !== -1) {
            defaultName = baseName.substring(0, lastDot) + '_sub' + baseName.substring(lastDot);
        } else {
            defaultName = baseName + '_sub.mp4';
        }
    }

    try {
        const response = await fetch('/api/select-file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode, default_name: defaultName })
        });
        
        const result = await response.json();
        
        if (result.path) {
            if (mode === 'video') {
                document.getElementById('video-path').value = result.path;
                
                // Automatically suggest an output path if it's empty
                const outputPathInput = document.getElementById('output-path');
                if (!outputPathInput.value) {
                    const lastDot = result.path.lastIndexOf('.');
                    let suggestedOutput = '';
                    if (lastDot !== -1) {
                        suggestedOutput = result.path.substring(0, lastDot) + '_sub' + result.path.substring(lastDot);
                    } else {
                        suggestedOutput = result.path + '_sub.mp4';
                    }
                    outputPathInput.value = suggestedOutput;
                }
            } else if (mode === 'srt') {
                document.getElementById('srt-path').value = result.path;
            } else if (mode === 'output') {
                document.getElementById('output-path').value = result.path;
            }
        }
    } catch (err) {
        console.error("選擇檔案出錯:", err);
        alert("無法啟動檔案選取視窗，請重試。");
    }
}

/**
 * Toggle embedding mode between hard (burn-in) and soft (muxing)
 * @param {string} mode - 'hard' or 'soft'
 */
function setMode(mode) {
    currentMode = mode;
    
    const hardCard = document.getElementById('mode-hard-card');
    const softCard = document.getElementById('mode-soft-card');
    const styleSection = document.getElementById('style-options-section');
    
    if (mode === 'hard') {
        hardCard.classList.add('active');
        softCard.classList.remove('active');
        styleSection.style.display = 'block'; // Show styling details
        updatePreview();
    } else {
        hardCard.classList.remove('active');
        softCard.classList.add('active');
        styleSection.style.display = 'none'; // Hide styling details as soft subtitles copy streams directly
    }
}

/**
 * Append messages to the mock terminal window
 * @param {string} text - Message content
 * @param {string} className - Line styling ('system-line', 'error-line', 'success-line')
 */
function logToConsole(text, className = '') {
    const consoleBody = document.getElementById('log-console');
    const line = document.createElement('div');
    line.className = `log-line ${className}`;
    line.textContent = text;
    consoleBody.appendChild(line);
    
    // Auto scroll to bottom
    consoleBody.scrollTop = consoleBody.scrollHeight;
}

/**
 * Start the subtitle embedding process
 */
async function startProcess() {
    const videoPath = document.getElementById('video-path').value;
    const srtPath = document.getElementById('srt-path').value;
    const outputPath = document.getElementById('output-path').value;
    
    if (!videoPath || !srtPath || !outputPath) {
        alert("請確認已選擇影片、字幕以及儲存路徑！");
        return;
    }
    
    // UI elements config
    const startBtn = document.getElementById('start-btn');
    const progressPanel = document.getElementById('progress-panel');
    const progressFill = document.getElementById('progress-fill');
    const progressPercent = document.getElementById('progress-percent');
    const statSpeed = document.getElementById('stat-speed');
    const statFps = document.getElementById('stat-fps');
    const statTime = document.getElementById('stat-time');
    const statusMessage = document.getElementById('status-message');
    const completionActions = document.getElementById('completion-actions');
    const logConsole = document.getElementById('log-console');
    
    // Disable start button
    startBtn.disabled = true;
    startBtn.textContent = '處理中...';
    startBtn.style.opacity = '0.6';
    startBtn.style.cursor = 'not-allowed';
    
    // Clear and show progress panel
    progressPanel.style.display = 'block';
    progressFill.style.width = '0%';
    progressPercent.textContent = '0.0%';
    statSpeed.textContent = '0x';
    statFps.textContent = '0';
    statTime.textContent = '00:00:00';
    statusMessage.style.display = 'none';
    completionActions.style.display = 'none';
    
    logConsole.innerHTML = '';
    logToConsole('[系統] 正在驗證檔案並初始化編碼器...', 'system-line');
    
    // Retrieve advanced style parameters
    const fontName = document.getElementById('font-name').value;
    const fontSize = document.getElementById('font-size').value;
    const fontColor = document.getElementById('font-color').value;
    const bgStyle = document.getElementById('bg-style').value;
    const marginV = document.getElementById('margin-v').value;
    
    // Start request
    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                video_path: videoPath,
                srt_path: srtPath,
                output_path: outputPath,
                mode: currentMode,
                font_name: fontName,
                font_size: fontSize,
                font_color: fontColor,
                bg_style: bgStyle,
                margin_v: marginV
            })
        });
        
        const result = await response.json();
        
        if (!result.success) {
            logToConsole(`[系統錯誤] ${result.message}`, 'error-line');
            showStatusAlert(result.message, 'error');
            resetStartButton();
            return;
        }
        
        logToConsole('[系統] 後端轉檔程式啟動成功，建立即時連線中...', 'system-line');
        showStatusAlert('影片處理中，請勿關閉本視窗...', 'info');
        
        // Connect to progress event stream (SSE)
        connectToProgressStream();
        
    } catch (err) {
        console.error("啟動處理程序失敗:", err);
        logToConsole(`[系統錯誤] 無法連接到伺服器處理程序。`, 'error-line');
        showStatusAlert('伺服器連線失敗。', 'error');
        resetStartButton();
    }
}

/**
 * Handle connection to Flask Server-Sent Events stream for real-time tracking
 */
function connectToProgressStream() {
    if (eventSource) {
        eventSource.close();
    }
    
    eventSource = new EventSource('/api/progress-stream');
    
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        // Update stats
        document.getElementById('progress-fill').style.width = `${data.progress}%`;
        document.getElementById('progress-percent').textContent = `${data.progress}%`;
        document.getElementById('stat-speed').textContent = data.speed;
        document.getElementById('stat-fps').textContent = data.fps;
        document.getElementById('stat-time').textContent = data.time;
        
        // Append new logs
        if (data.new_logs && data.new_logs.length > 0) {
            data.new_logs.forEach(log => {
                let cls = '';
                if (log.toLowerCase().includes('error') || log.toLowerCase().includes('failed')) {
                    cls = 'error-line';
                }
                logToConsole(log, cls);
            });
        }
        
        // Handle completed state
        if (data.status === 'completed') {
            eventSource.close();
            logToConsole('[系統] 轉檔作業成功結束！', 'success-line');
            document.getElementById('progress-fill').style.width = '100%';
            document.getElementById('progress-percent').textContent = '100.0%';
            
            showStatusAlert('轉檔處理成功完成！', 'info');
            document.getElementById('status-message').style.display = 'none';
            document.getElementById('completion-actions').style.display = 'block';
            resetStartButton();
        }
        
        // Handle error state
        if (data.status === 'error') {
            eventSource.close();
            logToConsole(`[系統錯誤] ${data.error_message}`, 'error-line');
            showStatusAlert(data.error_message, 'error');
            resetStartButton();
        }
    };
    
    eventSource.onerror = function(err) {
        console.error("SSE Connection error:", err);
        // Do not immediately close because browser automatically tries to reconnect SSE.
        // But if process has error/done, we handle it.
    };
}

/**
 * Restore start button state
 */
function resetStartButton() {
    const startBtn = document.getElementById('start-btn');
    startBtn.disabled = false;
    startBtn.textContent = '開始嵌入字幕';
    startBtn.style.opacity = '1';
    startBtn.style.cursor = 'pointer';
}

/**
 * Display a styled status alert message
 * @param {string} text - Message text
 * @param {string} type - 'info' or 'error'
 */
function showStatusAlert(text, type) {
    const alert = document.getElementById('status-message');
    alert.style.display = 'block';
    alert.className = `status-alert ${type}`;
    
    if (type === 'error') {
        alert.textContent = `❌ 錯誤：${text}`;
    } else {
        alert.textContent = `ℹ️ 狀態：${text}`;
    }
}

/**
 * Request backend to open the output directory in Explorer
 */
async function openOutputFolder() {
    const outputPath = document.getElementById('output-path').value;
    if (!outputPath) return;
    
    try {
        const response = await fetch('/api/open-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: outputPath })
        });
        const result = await response.json();
        if (!result.success) {
            alert(`無法打開資料夾：${result.message}`);
        }
    } catch (err) {
        console.error("開啟資料夾出錯:", err);
        alert("連線後端開啟資料夾時出錯。");
    }
}

/**
 * Update the mock subtitle preview styling based on form inputs in real-time
 */
function updatePreview() {
    const fontName = document.getElementById('font-name').value;
    const fontSize = document.getElementById('font-size').value;
    const fontColor = document.getElementById('font-color').value;
    const bgStyle = document.getElementById('bg-style').value;
    const marginV = document.getElementById('margin-v').value;
    
    const previewText = document.getElementById('preview-text');
    if (!previewText) return;
    
    // Map font family
    let fontFamily = 'sans-serif';
    if (fontName === 'Microsoft JhengHei') {
        fontFamily = '"Microsoft JhengHei", "微軟正黑體", sans-serif';
    } else if (fontName === 'PMingLiU') {
        fontFamily = '"PMingLiU", "新細明體", serif';
    } else if (fontName === 'Arial') {
        fontFamily = 'Arial, sans-serif';
    }
    previewText.style.fontFamily = fontFamily;
    
    // Apply font size directly in pixels
    previewText.style.fontSize = fontSize + 'px';
    
    // Map font color
    let colorHex = '#ffffff';
    if (fontColor === 'yellow') colorHex = '#ffff00';
    else if (fontColor === 'cyan') colorHex = '#00ffff';
    else if (fontColor === 'red') colorHex = '#ff4d4d';
    else if (fontColor === 'green') colorHex = '#4dff4d';
    previewText.style.color = colorHex;
    
    // Map background style
    if (bgStyle === 'opaque') {
        previewText.style.background = 'rgba(0, 0, 0, 0.75)';
        previewText.style.textShadow = 'none';
        previewText.style.padding = '4px 12px';
        previewText.style.borderRadius = '4px';
    } else if (bgStyle === 'none') {
        previewText.style.background = 'transparent';
        previewText.style.textShadow = 'none';
        previewText.style.padding = '0';
        previewText.style.borderRadius = '0';
    } else { // outline (default)
        previewText.style.background = 'transparent';
        previewText.style.padding = '0';
        previewText.style.borderRadius = '0';
        // Simulating ASS outline and shadow using text-shadow layers
        previewText.style.textShadow = '1px 1px 2px #000000, -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000';
    }
    
    // Scale bottom margin (0-100 input range maps to 5px to 45px in our 180px high box)
    let scaledBottom = 5 + Math.round((marginV / 100) * 40);
    previewText.style.bottom = scaledBottom + 'px';
}
