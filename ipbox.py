#!/usr/bin/env python
# importation des librairies
import smtplib
import urllib
import os.path

# recuperation adresse IP publique
texte = urllib.urlopen("http://www.monip.org").read()
ip_public = texte.split('IP : ')[1].split('<')[0]

# importation des modules email
from email.mime.text import MIMEText

USERNAME = "xxxxx@gmail.com"
PASSWORD = "password"
MAILTO = "xxxxxx@gmail.com"
ip_file = "/etc/ipbox.txt"

if os.path.exists(ip_file):
	ip_box_file = open(ip_file,"r")
	ip_box_line = ip_box_file.readlines()
	old_ip_public = ip_box_line[-1]
	ip_box_file.close()
else:
	old_ip_public = ""
if old_ip_public.strip() <> ip_public:
	ip_box_file = open(ip_file,"w")
	ip_box_file.write(ip_public + "\n")
	ip_box_file.close()
	msg = MIMEText('Nouvelle adresse IP de ma box : ' + ip_public)
	msg['Subject'] = 'Adresse IP de ma box'
	msg['From'] = USERNAME
	msg['To'] = MAILTO
	# parametres necessaires pour utiliser gmail
	server = smtplib.SMTP('smtp.gmail.com:587')
	server.ehlo_or_helo_if_needed()
	server.starttls()
	server.ehlo_or_helo_if_needed()
	server.login(USERNAME,PASSWORD)
	server.sendmail(USERNAME, MAILTO, msg.as_string())
	server.quit()