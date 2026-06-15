import os
import re
import sys
import json
import time
import queue
import threading
import subprocess
import webbrowser
from flask import Flask, render_template, jsonify, request, Response

app = Flask(__name__)

# Global job status dictionary to track processing
job_status = {
    'status': 'idle',      # idle, processing, completed, error
    'progress': 0,         # 0 to 100
    'speed': '0x',
    'fps': '0',
    'time': '00:00:00',
    'total_duration': 0.0,
    'error_message': '',
    'log': [],
    'output_path': ''
}

status_lock = threading.Lock()
log_queue = queue.Queue()

def get_video_duration(video_path):
    """Get the video duration in seconds using ffprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print("Error reading video duration:", e)
        return None

def get_video_resolution(video_path):
    """Get the video width and height using ffprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'json',
            video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        info = json.loads(result.stdout)
        if 'streams' in info and len(info['streams']) > 0:
            width = info['streams'][0].get('width')
            height = info['streams'][0].get('height')
            return int(width), int(height)
    except Exception as e:
        print("Error reading video resolution:", e)
    return None, None

def escape_subtitle_path(path):
    """
    Escape the subtitle file path for FFmpeg subtitles filter on Windows.
    1. Convert backslashes to forward slashes.
    2. Escape colons (e.g. C: -> C\:).
    3. Escape single quotes inside file names.
    4. Wrap the path in single quotes.
    """
    p = path.replace('\\', '/')
    p = p.replace(':', '\\:')
    p = p.replace("'", "'\\\\''")
    return f"'{p}'"

def run_ffmpeg_process(cmd, total_duration):
    """Run FFmpeg subprocess and read its output in real-time."""
    global job_status
    
    # Regular expressions for parsing ffmpeg stdout/stderr progress
    time_regex = re.compile(r'time=(\d{2}:\d{2}:\d{2}\.\d{2})')
    fps_regex = re.compile(r'fps=\s*([\d\.]+)')
    speed_regex = re.compile(r'speed=\s*([\d\.]+)x')
    
    try:
        # Start FFmpeg process
        # We redirect stderr because ffmpeg prints its progress logs to stderr
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1
        )
        
        # Read output line by line
        for line in process.stderr:
            line_str = line.strip()
            if not line_str:
                continue
                
            # Log the line
            with status_lock:
                job_status['log'].append(line_str)
                # Keep logs limit to last 200 lines to save memory
                if len(job_status['log']) > 200:
                    job_status['log'].pop(0)
            
            # Try to parse progress stats
            time_match = time_regex.search(line_str)
            fps_match = fps_regex.search(line_str)
            speed_match = speed_regex.search(line_str)
            
            updates = {}
            if time_match and total_duration and total_duration > 0:
                time_str = time_match.group(1)
                updates['time'] = time_str
                # Convert time string HH:MM:SS.xx to seconds
                try:
                    parts = time_str.split(':')
                    hh, mm = int(parts[0]), int(parts[1])
                    ss = float(parts[2])
                    elapsed = hh * 3600 + mm * 60 + ss
                    progress = min(99.0, (elapsed / total_duration) * 100.0)
                    updates['progress'] = round(progress, 1)
                except Exception:
                    pass
            
            if fps_match:
                updates['fps'] = fps_match.group(1)
            if speed_match:
                updates['speed'] = speed_match.group(1) + 'x'
                
            if updates:
                with status_lock:
                    for k, v in updates.items():
                        job_status[k] = v
                        
        # Wait for the process to exit
        process.wait()
        
        with status_lock:
            if process.returncode == 0:
                job_status['status'] = 'completed'
                job_status['progress'] = 100.0
            else:
                job_status['status'] = 'error'
                job_status['error_message'] = f'FFmpeg process exited with code {process.returncode}. Check logs for details.'
                
    except Exception as e:
        with status_lock:
            job_status['status'] = 'error'
            job_status['error_message'] = str(e)

def ask_file_dialog(mode, default_name=""):
    """
    Trigger native Tkinter file picker dialog.
    Spawns Tkinter dialog in a separate Python process to ensure thread-safety
    and prevent freezing in multi-threaded Flask requests on Windows.
    """
    # Inline python code to execute
    code = """
import sys
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)

mode = sys.argv[1]
default_name = sys.argv[2] if len(sys.argv) > 2 else ""

path = ""
try:
    if mode == 'video':
        path = filedialog.askopenfilename(
            title="選擇影片檔案",
            filetypes=[("影片檔案 (*.mp4, *.mkv, *.avi, *.mov)", "*.mp4;*.mkv;*.avi;*.mov;*.wmv;*.flv;*.webm"), ("所有檔案 (*.*)", "*.*")]
        )
    elif mode == 'srt':
        path = filedialog.askopenfilename(
            title="選擇字幕檔案",
            filetypes=[("SRT 字幕檔案 (*.srt)", "*.srt"), ("所有檔案 (*.*)", "*.*")]
        )
    elif mode == 'output':
        path = filedialog.asksaveasfilename(
            title="選擇儲存路徑",
            initialfile=default_name,
            filetypes=[("MP4 影片 (*.mp4)", "*.mp4"), ("MKV 影片 (*.mkv)", "*.mkv"), ("所有檔案 (*.*)", "*.*")],
            defaultextension=".mp4"
        )
except Exception as e:
    pass

print(path)
"""
    try:
        # Run python in a subprocess
        cmd = [sys.executable, '-c', code, mode, default_name]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        print("Error running file dialog subprocess:", e)
        return ""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/select-file', methods=['POST'])
def select_file():
    data = request.json or {}
    mode = data.get('mode', 'video')
    default_name = data.get('default_name', '')
    
    # Run the file dialog in a separate thread/way or directly.
    # Tkinter is safe when constructed and destroyed in the same call.
    file_path = ask_file_dialog(mode, default_name)
    
    response_data = {
        'path': file_path,
        'name': os.path.basename(file_path) if file_path else ''
    }
    
    # If a video is selected, check for matching srt files in the same directory
    if mode == 'video' and file_path:
        try:
            video_dir = os.path.dirname(file_path)
            base_name, _ = os.path.splitext(os.path.basename(file_path))
            
            # Common Traditional/Simplified Chinese and English subtitle naming patterns
            suffixes = ['', '.zh', '.zho', '.tw', '.cht', '.tc', '.traditional', '.chi', '.en']
            
            found_srt = ""
            for suffix in suffixes:
                candidate = os.path.join(video_dir, base_name + suffix + '.srt')
                if os.path.exists(candidate):
                    found_srt = candidate
                    break
            
            if found_srt:
                response_data['auto_srt_path'] = found_srt
                response_data['auto_srt_name'] = os.path.basename(found_srt)
        except Exception as e:
            print("Error scanning for matching srt:", e)
            
    return jsonify(response_data)

@app.route('/api/start', methods=['POST'])
def start_embedding():
    global job_status
    
    with status_lock:
        if job_status['status'] == 'processing':
            return jsonify({'success': False, 'message': '程式正在處理另一個影片，請稍後。'})
            
    data = request.json or {}
    video_path = data.get('video_path')
    srt_path = data.get('srt_path')
    output_path = data.get('output_path')
    mode = data.get('mode', 'hard') # 'hard' or 'soft'
    
    # Advanced options
    font_size = data.get('font_size', '16')
    font_color = data.get('font_color', 'white') # 'white', 'yellow', 'cyan'
    bg_style = data.get('bg_style', 'outline') # 'outline', 'opaque', 'none'
    margin_v = data.get('margin_v', '20')
    font_name = data.get('font_name', 'Microsoft JhengHei')
    hd_optimize = data.get('hd_optimize', False)
    
    if not video_path or not srt_path or not output_path:
        return jsonify({'success': False, 'message': '請填寫所有路徑。'})
        
    if not os.path.exists(video_path):
        return jsonify({'success': False, 'message': f'找不到影片檔案：{video_path}'})
        
    if not os.path.exists(srt_path):
        return jsonify({'success': False, 'message': f'找不到字幕檔案：{srt_path}'})

    # Query video duration
    duration = get_video_duration(video_path)
    if duration is None:
        duration = 0.0

    # Build FFmpeg command
    cmd = ['ffmpeg', '-y', '-i', video_path]
    
    upscale_log_msg = ""
    if mode == 'hard':
        # Escape srt path for filter
        escaped_srt = escape_subtitle_path(srt_path)
        
        # Check if we should upscale for HD subtitle optimization
        scale_filter = ""
        if hd_optimize:
            width, height = get_video_resolution(video_path)
            if width and height:
                if width >= height: # Landscape orientation
                    if width < 1920:
                        scale_filter = "scale=1920:-2:flags=lanczos,"
                        upscale_log_msg = f"偵測到低解析度橫向影片 ({width}x{height})，啟用清晰字幕優化 (升頻至 1920x1080p)..."
                else: # Portrait orientation (Vertical video)
                    if height < 1920:
                        scale_filter = "scale=-2:1920:flags=lanczos,"
                        upscale_log_msg = f"偵測到低解析度縱向影片 ({width}x{height})，啟用清晰字幕優化 (升頻至 1080x1920p)..."
        
        # Color mapping (AABBGGRR - ASS style)
        color_map = {
            'white': '&H00FFFFFF',
            'yellow': '&H0000FFFF',
            'cyan': '&H00FFFF00',
            'red': '&H000000FF',
            'green': '&H0000FF00',
            'blue': '&H00FF0000'
        }
        ass_color = color_map.get(font_color, '&H00FFFFFF')
        
        # Border style mapping
        # 1 = Outline + shadow, 3 = Opaque background box
        if bg_style == 'opaque':
            border_style = 'BorderStyle=3,Outline=0,Shadow=0'
        elif bg_style == 'none':
            border_style = 'BorderStyle=1,Outline=0,Shadow=0'
        else: # outline
            border_style = 'BorderStyle=1,Outline=2,Shadow=1'
            
        style_str = f"FontName={font_name},FontSize={font_size},PrimaryColour={ass_color},{border_style},MarginV={margin_v}"
        
        filter_str = f"{scale_filter}subtitles={escaped_srt}:force_style='{style_str}'"
        
        # Add video encoding settings (libx264, standard fast parameters)
        cmd.extend([
            '-vf', filter_str,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '20',
            '-c:a', 'copy', # Copy audio to save time & preserve quality
            output_path
        ])
    else:
        # Soft Subtitles (muxing)
        cmd.extend(['-i', srt_path])
        
        # Detect extension for subtitle codec
        _, ext = os.path.splitext(output_path.lower())
        sub_codec = 'mov_text' if ext in ['.mp4', '.m4v'] else 'srt'
        
        cmd.extend([
            '-c:v', 'copy', # Copy video stream (no re-encoding, extremely fast!)
            '-c:a', 'copy', # Copy audio stream
            f'-c:s', sub_codec,
            '-metadata:s:s:0', 'language=chi', # Set subtitle language metadata to Chinese
            output_path
        ])
        
    # Reset job status
    with status_lock:
        job_status['status'] = 'processing'
        job_status['progress'] = 0.0
        job_status['speed'] = '0x'
        job_status['fps'] = '0'
        job_status['time'] = '00:00:00'
        job_status['total_duration'] = duration
        job_status['error_message'] = ''
        
        # Build initial log list
        init_logs = [f'啟動處理任務...\n影片時間長度: {duration:.2f} 秒\n']
        if upscale_log_msg:
            init_logs.append(f'[系統] {upscale_log_msg}\n')
        init_logs.append(f'執行指令: {" ".join(cmd)}\n')
        
        job_status['log'] = init_logs
        job_status['output_path'] = output_path
        
    # Launch thread
    thread = threading.Thread(target=run_ffmpeg_process, args=(cmd, duration))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True})

@app.route('/api/status')
def get_status():
    with status_lock:
        return jsonify(job_status)

@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    data = request.json or {}
    path = data.get('path')
    if not path:
        return jsonify({'success': False, 'message': '無效的路徑'})
        
    try:
        if os.path.exists(path):
            # Select the file in explorer
            subprocess.run(['explorer', '/select,', os.path.normpath(path)])
            return jsonify({'success': True})
        else:
            # Fallback to directory
            dir_path = os.path.dirname(path)
            if os.path.exists(dir_path):
                os.startfile(dir_path)
                return jsonify({'success': True})
            return jsonify({'success': False, 'message': '檔案與資料夾皆不存在'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/progress-stream')
def progress_stream():
    """Server-Sent Events (SSE) endpoint to stream progress updates in real-time."""
    def generate():
        last_progress = -1
        last_status = ''
        last_log_len = 0
        
        while True:
            time.sleep(0.2)
            with status_lock:
                current_progress = job_status['progress']
                current_status = job_status['status']
                current_log = job_status['log']
                
                # Check if there is anything new
                if (current_progress != last_progress or 
                    current_status != last_status or 
                    len(current_log) != last_log_len):
                    
                    data = {
                        'status': job_status['status'],
                        'progress': job_status['progress'],
                        'speed': job_status['speed'],
                        'fps': job_status['fps'],
                        'time': job_status['time'],
                        'error_message': job_status['error_message'],
                        'new_logs': current_log[last_log_len:]
                    }
                    
                    yield f"data: {json.dumps(data)}\n\n"
                    
                    last_progress = current_progress
                    last_status = current_status
                    last_log_len = len(current_log)
                    
                if current_status in ['completed', 'error']:
                    break
                    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    # Automatically open local server in browser after a short delay to let flask initialize
    def open_browser():
        time.sleep(1.5)
        webbrowser.open('http://127.0.0.1:5000')
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run server
    app.run(host='127.0.0.1', port=5000, debug=False)
