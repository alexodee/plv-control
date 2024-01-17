import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from moviepy.editor import VideoFileClip, concatenate_videoclips
import json
import paramiko
import scp

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'mp4'}

videos = []

def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config

config = load_config()
devices = config.get("devices", [])

current_device = devices[0]  # Appareil par défaut

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def generate_thumbnail(video_path):
    thumbnail_path = f'static/thumbnails/{os.path.splitext(os.path.basename(video_path))[0]}.mp4.png'
    clip = VideoFileClip(video_path)
    clip.save_frame(thumbnail_path, t=clip.duration/2)
    clip.close()
    return thumbnail_path

def save_video_order(video_order):
    with open(current_device['video_order'], 'w') as f:
        json.dump(video_order, f)

def resolve_filename_conflict(filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename

    while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], new_filename)):
        new_filename = f"{base}-{counter}{ext}"
        counter += 1

    if new_filename != filename:
        return new_filename
    else:
        return filename

def export_clips(video_clips, output_path):
    final_clips = []
    generic_video_path = 'static/generique/generique.mp4'

    for clip in video_clips:
        final_clips.append(clip)
        final_clips.append(VideoFileClip(generic_video_path))

    final_clip = concatenate_videoclips(final_clips[:-1])
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    final_clip.close()

def load_video_order():
    video_order_path = current_device['video_order']
    if os.path.exists(video_order_path):
        try:
            with open(video_order_path, 'r') as f:
                video_order = json.load(f)
                if isinstance(video_order, list):
                    return video_order
                else:
                    return []
        except json.JSONDecodeError:
            return []
    return []

def transfer_to_raspberry_pi(local_path, remote_path):
    ssh_username = current_device['username']
    ssh_password = current_device['password']
    ssh_host = current_device['ip']

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(ssh_host, username=ssh_username, password=ssh_password)

    with scp.SCPClient(ssh_client.get_transport()) as scp_client:
        scp_client.put(local_path, remote_path)

    ssh_client.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    global videos
    if request.method == 'POST':
        if 'video' not in request.files:
            return redirect(request.url)

        file = request.files['video']

        if file.filename == '':
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filename = resolve_filename_conflict(filename)  # Utilisez la fonction pour résoudre les conflits
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(video_path)
            thumbnail_path = generate_thumbnail(video_path)
            videos.append({'name': filename, 'path': video_path, 'thumbnail': thumbnail_path})

            video_order = load_video_order()
            video_order.append(filename)
            save_video_order(video_order)

            return redirect(request.url)

    try:
        video_order = load_video_order()
        videos = [{'name': filename, 'path': f'uploads/{filename}', 'thumbnail': f'static/thumbnails/{os.path.splitext(filename)[0]}.mp4.png'} for filename in video_order]
    except Exception as e:
        print(f"Error loading video order: {e}")
        videos = []

    return render_template('index.html', videos=videos, devices=devices, current_device=current_device['name'])

@app.route('/delete_video/<int:index>', methods=['POST'])
def delete_video(index):
    video_order = load_video_order()
    if index < len(video_order):
        deleted_video_name = video_order.pop(index)
        save_video_order(video_order)
        thumbnail_path = f'static/thumbnails/{os.path.splitext(deleted_video_name)[0]}.mp4.png'
        video_path = f'uploads/{deleted_video_name}'  # Chemin vers le fichier vidéo
        os.remove(thumbnail_path)
        os.remove(video_path)  # Supprimer le fichier vidéo
    return redirect(url_for('index'))


@app.route('/export', methods=['POST'])
def export():
    video_order = load_video_order()
    ordered_videos = sorted(videos, key=lambda video: video_order.index(video['name']))

    if not ordered_videos:
        return redirect(url_for('index'))

    video_clips = [VideoFileClip(video['path']) for video in ordered_videos]
    output_path = 'output.mp4'

    export_clips(video_clips, output_path)

    for video_clip in video_clips:
        video_clip.close()

    remote_path = current_device.get('remote_path')
    transfer_to_raspberry_pi(output_path, remote_path)

    update_device = current_device['name']
    return redirect(url_for('index', _anchor='video-list', _append_query=True, device=update_device))

@app.route('/reorder_videos', methods=['POST'])
def reorder_videos():
    start_index = int(request.form['startIndex'])
    end_index = int(request.form['endIndex'])

    video = videos.pop(start_index)
    videos.insert(end_index, video)

    video_order = [video['name'] for video in videos]
    save_video_order(video_order)

    for i, video in enumerate(videos):
        thumbnail_path = generate_thumbnail(video['path'])
        video['thumbnail'] = thumbnail_path

    print(f"Video order after reorder: {video_order}")

    return jsonify(success=True)

@app.route('/save_order', methods=['POST'])
def save_order():
    try:
        video_order = json.loads(request.form['videoOrder'])
        save_video_order(video_order)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e))

@app.route('/change_device', methods=['POST'])
def change_device():
    global current_device
    selected_device = request.form['selectedDevice']
    for device in devices:
        if device['name'] == selected_device:
            current_device = device
            break
    return jsonify(success=True)

if __name__ == '__main__':
    try:
        videos = load_video_order()
    except Exception as e:
        print(f"Error loading video order: {e}")

    # Modifiez la ligne suivante pour spécifier l'adresse IP et le port
    app.run(host='192.168.1.218', port=80, debug=True)
