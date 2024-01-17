# Utilisez l'image de base Python 3.8
FROM python:3.8

# Définissez le répertoire de travail dans le conteneur
WORKDIR /plv-control

# Copiez tous les fichiers Python dans le conteneur
COPY . /plv-control

# Commande par défaut pour exécuter script1.py
CMD ["python3", "app.py"]
