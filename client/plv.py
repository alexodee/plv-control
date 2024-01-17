import os
import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime

class VideoHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        elif event.src_path.endswith(".mp4"):
            print(f"Nouvelle PLV détectée: {event.src_path}")
            self.process_new_video(event.src_path)

    def process_new_video(self, video_path):
        # Arrêter VLC s'il est en cours d'exécution
        subprocess.run(["pkill", "vlc"])
        print(f"Ancienne PLV stoppée")

        # Supprimer tous les fichiers commencant par "PLV" sur le bureau
        old_files = [f for f in os.listdir("/home/mjc-ac/Desktop") if f.startswith("PLV")]
        for old_file in old_files:
            old_file_path = os.path.join("/home/mjc-ac/Desktop", old_file)
            os.remove(old_file_path)
            print(f"Suppression de l'ancienne PLV")

        # Obtenir la date actuelle (jour/mois)
        current_date = datetime.now().strftime("%d-%m")

        # Construire le nouveau nom de fichier avec la date
        new_video_name = f"PLV_{current_date}.mp4"
        new_video_path = os.path.join("/home/mjc-ac/Desktop", new_video_name)

        # Renommer la nouvelle vidéo
        os.rename(video_path, new_video_path)
        print(f"Renommage de la nouvelle PLV")
        # Lancer la nouvelle vidéo avec VLC de manière asynchrone
        subprocess.Popen(["vlc", "--no-xlib", "--fullscreen", new_video_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Lancement de la nouvelle PLV")
def launch_initial_video():
    # Recherche du fichier commençant par "PLV" sur le bureau
    initial_video = next((f for f in os.listdir("/home/mjc-ac/Desktop") if f.startswith("PLV")), None)
    
    # S'il existe, lancer le fichier avec VLC
    if initial_video:
        initial_video_path = os.path.join("/home/mjc-ac/Desktop", initial_video)
        subprocess.Popen(["vlc", "--no-xlib", "--fullscreen", initial_video_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Lancement de la PLV")
if __name__ == "__main__":
    # Lancer la première vidéo au démarrage
    launch_initial_video()

    # Répertoire à surveiller (le bureau dans ce cas)
    directory_to_watch = "/home/mjc-ac/Desktop"
    
    # Instancier l'observateur et le gestionnaire d'événements
    observer = Observer()
    event_handler = VideoHandler()
    observer.schedule(event_handler, path=directory_to_watch, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
