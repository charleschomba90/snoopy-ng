# -*- coding: utf-8 -*-
from threading import Thread
import threading
from sqlalchemy import *
import logging
from flask import Flask,request
import json
import glob
import os
import random
import string

#logging.basicConfig(filename="snoopy.log",level=logging.DEBUG,format='%(asctime)s %(levelname)s %(filename)s: %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(levelname)s %(filename)s: %(message)s',datefmt='%Y-%m-%d %H:%M:%S')


class webserver():

    @staticmethod
    def manage_drone_account(drone,operation,dbms):
        db = create_engine(dbms)
        metadata = MetaData(db)

        drone_table=Table('drones',metadata,Column('drone', String(40), primary_key=True),Column('key', String(40) ) )

        if not db.dialect.has_table(db.connect(), drone_table.name ):   
            drone_table.create()

        if operation == "create":
            try:
                key=''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(15))
                drone_table.insert().prefix_with("OR REPLACE").execute(drone=drone,key=key)
            except Exception,e:
                logging.exception("Exception whilst attemptign to add drone")
                logging.exception(e)
            else:   
                return key

        elif operation == "delete":
            drone_table.delete().execute(drone=drone)
            return True
        elif operation == "list":
            s=drone_table.select().execute()
                        return(s.fetchall())
        else:
            logging.error("Bad operation '%s' passed to manage_drone_account"%operation)    
            return False

    def __init__(self,dbms="sqlite:///snoopy.db",path="/",srv_port=9001):

        #Database
        self.db = create_engine(dbms)
                self.metadata = MetaData(self.db)
        self.tables={}

        logging.debug("Writing server database: %s"%dbms)
        logging.debug("Listening on port: %d"%srv_port)
        logging.debug("Sync URL path: %s"%path)

                #Load db tables from client modules
        ident_tables=[]
                moduleNames=["plugins." + os.path.basename(f)[:-3] for f in glob.glob("./plugins/*.py") if not os.path.basename(f).startswith('__') and not os.path.basename(f).startswith(__file__)]
        logging.debug("Server loading tables from plugins:%s"%str(moduleNames)) 
                for mod in moduleNames:
                        m=__import__(mod, fromlist="snoop").snoop()
                        for ident in m.get_ident_tables():
                                if ident!=None:
                                        ident_tables.append(ident)
                        tbls=m.get_tables()         

            #Manually add drone table
            tbl_drone=Table('drones',MetaData(),Column('drone', String(40), primary_key=True),Column('key', String(40) ) )
            tbls.append(tbl_drone)

                        for tbl in tbls:
                                tbl.metadata=self.metadata
                                if tbl.name in ident_tables:
                                        tbl.append_column( Column('drone',String(length=20)) )
                                        tbl.append_column( Column('location', String(length=60)) )
                    tbl.append_column( Column('run_id', String(length=11)) )
                self.tables[tbl.name]=tbl
                                if not self.db.dialect.has_table(self.db.connect(), tbl.name):
                                        tbl.create()
    
        logging.debug("Starting webserver")
        self.run_webserver(path,srv_port)


    def write_local_db(self,rawdata):
            """Write server db"""
        for entry in rawdata:
            tbl=entry['table']
            data=entry['data']  
            try:
                self.tables[tbl].insert().prefix_with("OR REPLACE").execute(data)
            except Exception,e:
                logging.exception(e)
            else:
                return True


    def verify_account(self,_drone,_key):
        try:
            drone_table=self.tables['drones']
            s=select([drone_table], and_(drone_table.c.drone==_drone,drone_table.c.key==_key))
            r=self.db.execute(s)
            result=r.fetchone()
                    
            if result:
                logging.debug("Auth granted for %s"%_drone)
                return True
            else:
                logging.debug("Access denied for %s"%_drone)
                return False

        except Exception,e:
            logging.exception(e)
            return False

    #Perhaps make this a module?
    def run_webserver(self,path,srv_port):

        app = Flask(__name__)
        
        @app.route(path,methods=['POST'])
        def catch_data():
                if request.headers['Content-Type'] == 'application/json':
    
                try:
                            jsdata=json.loads(request.data)
                    drone,key=None,None
                    if 'Z-Auth' in request.headers:
                        key=request.headers['Z-Auth']
                    if 'Z-Drone' in request.headers:
                        drone=request.headers['Z-Drone']

                    if self.verify_account(drone,key):
                        logging.debug("WROTE:")
                        logging.debug(jsdata)
                        result=self.write_local_db(jsdata)              
        
                        if result:
                                    return '{"result":"success", "reason":"None"}'
                        else:
                            return '{"result":"failure", "reason":"Check server logs"}'
                    else:
                        return '{"result":"failure","reason":"Access denied"}'

                except Exception,e:
                    logging.exception(e)
        
        #app.debug=True
        app.run(host="0.0.0.0",port=srv_port)


if __name__=="__main__":
    x=webserver()
    x.start()