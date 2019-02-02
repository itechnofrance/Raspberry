#! /usr/bin/python
# -*- coding:utf-8 -*-

#
# Permet de gérer des prises de vue à intervalle régulier ou à partir d'une détection de mouvement
#
# Matériel :
#       Raspberry Pi Zero WH avec Raspbian Stretch
#       Caméra NoIR
#
# Version : 1.0 (Février 2019)

import os, time, io, threading, picamera, picamera.array
from flask import Flask, render_template, redirect, url_for, request, Response

# variables pour la détection de mouvement et le TimeLapse
seuil = 10     # Combien de pixels doivent changer d'état
sensibilite = 50  # Combien de fois les pixels ont changé
bouton_status_motion = False  # donne le status des boutons
scan_motion = False
intervalle = 5
duree = 0
bouton_status_timelapse = False  # donne le status des boutons
fct_start = False  # permet de savoir si une fonction est en cours d'exécution

# variables pour la prise de vues
ctr_photo = 0  # compteur pour la création des fichiers
iso = 0  # iso auto
wb = "auto"
exposition = "auto"
resolution_x = 2592
resolution_y = 1944

# Classe pour streamer les images
class MaCamera(object):
    thread = None       # Thread qui capture les images via la caméra
    image = None        # Dernière image capturée par le thread
    dernier_acces = 0   # Date du dernier accès à la camera par un client

    def initialize(self):
        # Initialisation de notre logique de capture
        if MaCamera.thread is None:
            # Démarrage du thread
            MaCamera.thread = threading.Thread(target=self._capture_thread)
            MaCamera.thread.start()
            # On attend tant qu'il n'y a pas d'image disponible
            while self.image is None:
                time.sleep(0)

    def get_image(self):
        # Fonction permettant de récupérer la dernière image capturée
        MaCamera.dernier_acces = time.time()
        self.initialize()
        return self.image

    @classmethod
    def _capture_thread(cls):
        with picamera.PiCamera() as cam:
            # Réglages permettant de changer l'orientation des images capturées
            cam.hflip = False
            cam.vflip = False
            cam.iso = iso
            cam.awb_mode = wb
            cam.exposure_mode = exposition
            stream = io.BytesIO()
            for a in cam.capture_continuous(stream, 'jpeg', use_video_port=True):
                # Lecture d'une image
                stream.seek(0)
                cls.image = stream.read()

                # Reset du stream pour préparer la récupération de la prochaine image
                stream.seek(0)
                stream.truncate()

                # On coupe le thread (et la caméra) si personne n'a
                # accédé à la caméra depuis plus de 2 secondes
                if time.time() - cls.dernier_acces > 2:
                    break
        cls.thread = None

def generateur(camera):
    # Cette fonction représente un générateur d'images
    # Il utilise la fonction "get_image" de notre classe "MaCamera"
    while True:
        img = camera.get_image()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + img + b'\r\n')

# TimeLapse
def traite_timelapse():
    global ctr_photo, fct_start, bouton_status_timelapse
    fct_start = True 
    with picamera.PiCamera() as camera:
        time.sleep(1)
        camera.resolution = (resolution_x, resolution_y)
        camera.iso = iso
        camera.meter_mode = 'matrix'  # mesure matricielle
        time.sleep(2)
        camera.shutter_speed = camera.exposure_speed
        camera.exposure_mode = 'off'  # désactivation mode d'exposition
        g = camera.awb_gains
        camera.awb_mode = 'off'  # désactivation balance des blancs
        camera.awb_gains = g
        debut = time.time()
        while bouton_status_timelapse == True:
            ctr_photo += 1
            camera.capture('./photos/photo' + str(ctr_photo) + '.jpg', format="jpeg", use_video_port=False, quality=100)
            for i in range(0, intervalle*10): 
                time.sleep(0.1)  # temporisation 100 ms
                if bouton_status_timelapse == False: # si appuie sur bouton "Arrêter"
                    break
            fin = time.time()
            if duree > 0:  # si choix d'une durée définit
                temps_ecoule = fin - debut
                if int(temps_ecoule) > duree:
                    bouton_status_timelapse = False
    fct_start = False
    
# Capture une image à faible résolution        
def takeMotionImage(width, height):
    with picamera.PiCamera() as camera:
        time.sleep(1)
        camera.resolution = (width, height)
        with picamera.array.PiRGBArray(camera) as stream:
            camera.exposure_mode = 'auto'
            camera.awb_mode = 'auto'
            camera.capture(stream, format='rgb')
            return stream.array

# Compare 2 images et comptabilise le nbr d'images où des pixels ont été modifiés
def scanMotion(width, height):
    global scan_motion
    scan_motion = True
    motionFound = False
    data1 = takeMotionImage(width, height)
    while not motionFound:
        data2 = takeMotionImage(width, height)
        diffCount = 0L;
        for w in range(0, width):
            if bouton_status_motion == False:
                break;
            for h in range(0, height):
                if bouton_status_motion == False:
                    break;
                # Obtient la différence des pixels
                diff = abs(int(data1[h][w][1]) - int(data2[h][w][1]))
                if  diff > seuil:
                    diffCount += 1
            if diffCount > sensibilite:
                break;
        if diffCount > sensibilite:
            motionFound = True
        else:
            data2 = data1
        if bouton_status_motion == False:
            break;
    scan_motion = False
    return motionFound

def detection_mouvement():
    global scan_motion, ctr_photo, fct_start
    fct_start = True 
    scan_motion = False
    while bouton_status_motion == True:
        if scan_motion == False:
            if scanMotion(224, 160):
                with picamera.PiCamera() as camera:
                    ctr_photo += 1
                    # Réglages prises de vue
                    camera.iso = iso
                    camera.resolution = (resolution_x, resolution_y)
                    camera.awb_mode = wb
                    camera.exposure_mode = exposition
                    camera.capture('./photos/photo' + str(ctr_photo) + '.jpg', format="jpeg", use_video_port=False, quality=100)
    fct_start = False
    
def initialisation():
    if (os.path.isdir('./photos')):
        dirPath = "./photos"
        fileList = os.listdir(dirPath)
        for fileName in fileList:
            os.remove(dirPath + "/" + fileName)
    else:
        os.mkdir('./photos')

# declaration site Web
site = Flask(__name__)
    
# Traitement page principale; les pages html doivent se trouver dans un dossier de nom "templates"
@site.route('/', methods = ['POST', 'GET'])
def index():
    return render_template('index.html') 

# Permet de configurer quelques paramètres de prise de vue        
@site.route('/parametres', methods = ['POST', 'GET'])
def parametres():
    return render_template('parametres.html')

@site.route('/sauve_parametres', methods = ['POST'])
def sauve_parametres():
    global iso, wb, exposition, resolution_x, resolution_y
    if request.method == 'POST':
        if 'save' in request.form:
            iso = int(request.form['iso'])
            wb = request.form['wb']
            exposition = request.form['exposition']
            resolution_str = request.form['resolution']
            if resolution_str == "0":
                resolution_x = 640
                resolution_y = 480
            if resolution_str == "1":
                resolution_x = 800
                resolution_y = 600
            if resolution_str == "2":
                resolution_x = 1024
                resolution_y = 768
            if resolution_str == "3":
                resolution_x = 1920
                resolution_y = 1080
            if resolution_str == "4":
                resolution_x = 2592
                resolution_y = 1944
    return redirect(url_for('index'))
    
# Permet de streamer des photos    
@site.route('/visualisation', methods = ['POST', 'GET'])
def visualisation():
    return render_template('visualisation.html')

# On définit une URL permettant la récupération d'images
@site.route('/image_url')
def image_url():
    # Route générant le flux d'images
    # Doit être appelée depuis l'attribut "src" d'une balise "img"
    return Response(generateur(MaCamera()), mimetype='multipart/x-mixed-replace; boundary=frame')

# Permet de configurer et d'effectuer du TimeLapse
@site.route('/timelapse', methods = ['POST', 'GET'])
def timelapse():
    global intervalle, duree, bouton_status_timelapse
    if request.method == 'POST':
        if 'start' in request.form:
            intervalle = int(request.form['intervalle'])
            duree = int(request.form['duree'])
            bouton_status_timelapse = True
            if not fct_start:
                traite_timelapse()
        if 'stop' in request.form:
            bouton_status_timelapse = False
    return render_template('timelapse.html') 
    
# Permet la prise de vue suite à un mouvement détecté
@site.route('/mouvement', methods = ['POST', 'GET'])
def mouvement():
    global ctr_photo, bouton_status_motion, scan_motion, ctr_start
    if request.method == 'POST':
        if 'start' in request.form:
            bouton_status_motion = True
            if  not fct_start:
                detection_mouvement()
        if 'stop' in request.form:
            bouton_status_motion = False
    return render_template('mouvement.html') 

@site.route('/mouvement_set_seuil', methods = ['POST', 'GET'])
def mouvement_set_seuil():
    global seuil
    seuil = int(request.args.get("seuil"))
    return str(seuil)

@site.route('/mouvement_set_sensibilite', methods = ['POST', 'GET'])
def mouvement_set_sensibilite():
    global sensibilite
    sensibilite = int(request.args.get("sensibilite"))
    return str(sensibilite)
    
# Permet d'arrêter le Raspberry    
@site.route('/halt', methods = ['POST', 'GET'])
def halt_pi():
    os.system('sudo halt')
    
# Traitement page non trouvée, on envoi la page principale   
@site.errorhandler(404)
def nopage(e):
    return redirect(url_for('index'))

if __name__ == '__main__':
    initialisation()
    site.run(host = '0.0.0.0', debug = True, threaded = True, port = 80)