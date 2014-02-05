#! /usr/bin/env python
import irc.bot
import sqlite3
import feedparser
import threading
import time
import traceback
import ssl

# Boucle de gestion des nouveau flux
def feedLoop(sql,irc):
    while True:
        # Calcul de temps de la boucle
        deb=time.time()
        for row in sql.cursor().execute("SELECT * FROM url"):
            try:
                # Verification du timestamp pour prendre les nouveaux items
                maxi=int(row[2])
                nmaxi=maxi
                for item in feedparser.parse(row[1])["items"]:
                    # Calcul du nouveau timestamp
                    tmax=int("".join(str(i).zfill(2) for i in item['date_parsed']))
                    if tmax > maxi:
                        nmaxi = tmax if tmax > nmaxi else nmaxi
                        # Notification d'un nouveau flux
                        irc.connection.privmsg(irc.channel,item['title']+" - "+item['link'])
                if nmaxi != maxi:
                    # Mise a jour du timestamp
                    sql.cursor().execute("UPDATE url SET lastHash = ? WHERE user = ? and url = ?",(str(nmaxi),row[0],row[1]))
                    sql.commit()
            except Exception as e:
                # Si erreur, on previent l'utilisateur, flood ?
                traceback.print_exc()
                irc.connection.privmsg(row[0],"Erreur avec le flux " + row[1] +": " + str(e) + ". Merci de verifier.")
        fin=time.time()
        # Si ca a dure moins de 30s, on attend avant la prochaine MaJ
        if fin-deb < 29:
            time.sleep(30-int(fin-deb))

class IRssCbot(irc.bot.SingleServerIRCBot):

    # Constructeur
    def __init__(self, channel, nickname, server, port,sslC,password,**options):
        if sslC:
            irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname,connect_factory=irc.connection.Factory(wrapper=ssl.wrap_socket))
        else:
            irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        self.options = options
        self.password = password
        self.conn = sqlite3.connect('db.db', check_same_thread=False)

    # A la connexion, on met un mot de passe (si necessaire)
    def connect(self, *args, **kwargs):
        kwargs.update(self.options)
        self.server_list[0].password=self.password
        print "Go"
        irc.bot.SingleServerIRCBot.connect(self, *args, **kwargs)

    # Si le pseudo existe deja, on reessaie avec un "_" a la fin
    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")

    # A la connection, on rejoin le channel, et on lance le thread
    def on_welcome(self, c, e):
        c.join(self.channel)
        threading.Thread(None, feedLoop, None, (self.conn,self)).start()

    # Gestion des actions
    def on_pubmsg(self, c, e):
        a = e.arguments[0].split(" ", 1)
        if len(a) > 0 and a[0] == "!mine":
            self.do_mine(e)
        if len(a) > 1 and a[0] == "!del":
            self.do_del(e, a[1])
        if len(a) > 1 and a[0] == "!add":
            self.do_add(e, a[1])
        return

    # !mine
    def do_mine(self,e):
        c=self.connection
        cur=self.conn.cursor()
        for row in cur.execute("SELECT * FROM url WHERE user = ?",(e.source.nick,)):
                c.privmsg(e.target,"["+row[0]+"] " + row[1])

    # !del
    def do_del(self,e,url):
        c=self.connection
        self.conn.cursor().execute("DELETE FROM url WHERE user=? and url=?",(e.source.exinick,url))
        c.privmsg(e.target,e.source.nick + " a supprime un flux RSS")
        self.conn.commit()

    # !add
    def do_add(self,e,url):
        c=self.connection
        self.conn.cursor().execute("INSERT INTO url VALUES (?,?,'0')",(e.source.nick,url))
        c.privmsg(e.target,e.source.nick + " a ajoute le RSS " + url)
        self.conn.commit()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 6:
        print "IRssCbot \"server:port\" \"#channel\" \"nickname\" <ssl|clear> \"password\""
        sys.exit(1)

    # Gestion des arguments
    s = sys.argv[1].split(":", 1)
    server = s[0]
    port = int(s[1])
    channel = sys.argv[2]
    nickname = sys.argv[3]
    sslC = True if sys.argv[4]=="ssl" else False
    password = sys.argv[5]

    # Go !!!
    bot = IRssCbot(channel, nickname, server, port,sslC,password)
    bot.start()
