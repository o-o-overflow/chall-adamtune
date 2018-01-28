import pipes
import time
import pwn
import sys
import os

r = pwn.remote(sys.argv[1], int(sys.argv[2]))
try:
    #r = pwn.process("./service.py")
    r.sendline("OOOMAKESTHESAFESTBACKDOORS")
    r.readrepeat(timeout=1)
    r.sendline("yes")
    r.readrepeat(timeout=1)
    r.sendline("yes")
    print r.readuntil("CHALLENGE PHRASE: ")
    challenge = r.readuntil('\n')
    print "CHALLENGE:", challenge
    print time.time()
    cmd = "python src/adamtune.py build_audio adam solution.mp3 " + " ".join(map(pipes.quote, (w for w in challenge.split())))
    print "RUNNING:", cmd
    assert os.system(cmd) == 0
    #raw_input()
    m = open('solution.mp3').read()
    r.sendline(str(len(m)))
    r.send(m)
    print r.readuntil("joining the words!\n")
    print time.time()
    sol = r.readrepeat(timeout=5)
    with open("ff.mp3", "w") as ff:
        ff.write(sol)
except EOFError:
    print r.recvall()
