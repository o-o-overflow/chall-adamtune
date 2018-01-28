#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hashlib
import random
import signal
import time
import sys
import os

#pylint:disable=invalid-encoded-data

DOUP="Adam Doupé, the famous cybersecurity professor and hacker"

def check_for_yes(if_no):
	if raw_input().strip().lower() != "yes":
		print if_no
		time.sleep(1)
		disconnect()

def disconnect():
		print "You will now be disconnected. Here is a fun fact about %s:" % DOUP
		time.sleep(1)
		print random.choice(open('adam_facts.txt').readlines()).replace('XXADAMXX', DOUP).replace('Chuck Norris', DOUP)
		sys.exit(1)

os.system("banner Welcome to ADAMTUNE")

print "Setting timeout to 6 minutes."
signal.alarm(6*60)

time.sleep(1)
print "Loading..."
time.sleep(1)
print "... loaded!"
print "Are you %s? " % DOUP
print """
╭━━━━━━━╮
┃● ══   ┃
┃███████┃
┃██Are██┃
┃██you██┃
┃█Adam██┃
┃█Doupé█┃
┃██???██┃
┃███████┃
┃ 　O　 ┃
╰━━━━━━━╯
>"""
check_for_yes("This system is only authorized for use by %s." % DOUP)

print "Processing..."
time.sleep(1)
print "Welcome, suspected %s!" % DOUP
print """
╭━━━━━━━╮
┃● ══   ┃
┃███████┃
┃█HELLO█┃
┃███████┃
┃█ADAM!█┃
┃███████┃
┃███████┃
┃███████┃
┃ 　O　 ┃
╰━━━━━━━╯
"""
print "Would you like to access your tunes?"

check_for_yes("No other functionality is available.")
time.sleep(1)
print """
╭━━━━━━━╮
┃● ══   ┃
┃███████┃
┃PROVIDE┃
┃█VOICE█┃
┃██ID,██┃
┃█ADAM!█┃
┃███████┃
┃███████┃
┃ 　O　 ┃
╰━━━━━━━╯
"""
phrase = random.choice(open('sentences.txt').readlines()).strip()
print "CHALLENGE PHRASE:", phrase
#print "Before voiceprint, please perform this proof of work:"
#if os.system("./powserver.py") != 0:
#	print "POW failed."
#	disconnect()

print "Please make sure that your voiceprint is a high quality record."
print "What is the size of your voiceprint mp3?"
size = int(raw_input().strip())
if size > 300*1024:
	print "This file is too big."
	disconnect()
s = ""
while len(s) != size:
    s += sys.stdin.read(size - len(s))
h = hashlib.md5(s).hexdigest()
ph_file = "submissions/"+h+".txt"
in_file = "submissions/"+h+"-in.mp3"
ou_file = "submissions/"+h+"-ou.mp3"
lo_file = "submissions/"+h+".log"
with open(ph_file, "w") as cf:
	cf.write(phrase)
with open(in_file, "w") as mf:
	mf.write(s)

is_adam = os.system("bash -c 'set -o pipefail; python src/adamtune.py check adam %s %s $(cat %s) | tee -a %s 2>>%s'" % (ou_file, in_file, ph_file, lo_file, lo_file))
if is_adam != 0:
	print "YOU ARE NOT " + DOUP.upper() + "!!!!"
	disconnect()
else:
	print DOUP + " confirmed! Here is your flag. Adjust it to the flag format, inner text lowercase, with underscores joining the words!"
	print open("flag.mp3").read()
