import mysql.connector
from constants import VANGUARD_DB_CONNECTION
from mysql.connector.pooling import PooledMySQLConnection, MySQLConnectionPool
from mysql.connector.cursor import MySQLCursor
from errors import http_server_err
from constants import DB_ERR_REST

vdbpool = MySQLConnectionPool(pool_name='vanguard_db', pool_size=10, **VANGUARD_DB_CONNECTION)

class MYSQLQuery:

    def __init__(self, pool_obj: MySQLConnectionPool, on_error: str = DB_ERR_REST) -> None:
        try:
            self.connection: PooledMySQLConnection = pool_obj.get_connection()
            self.cursor: MySQLCursor = self.connection.cursor()
            self.on_error = on_error

        except mysql.connector.Error as dberr:
            print(dberr)
            if on_error == DB_ERR_REST: raise http_server_err()


    def read(self, query: str, params: tuple | list = (), close_conn_on_err = True) -> list:
        try:
            self.cursor.execute(query, params)
            result = self.cursor.fetchall()
            return result if result else []
        
        except mysql.connector.Error as dberr:
            print(dberr)
            if close_conn_on_err:
                if self.on_error == DB_ERR_REST: raise http_server_err()
            else: raise mysql.connector.Error()


    def create(self, query: str, params: tuple | list = (), close_conn_on_err = True) -> int:
        try:
            self.cursor.execute(query, params)
            self.connection.commit()
            return self.cursor.lastrowid

        except mysql.connector.Error as dberr:
            print(dberr)
            if close_conn_on_err:
                if self.on_error == DB_ERR_REST: raise http_server_err()
            else: raise mysql.connector.Error()


    def update(self, query: str, params: tuple | list = (), close_conn_on_err = True) -> None:
        try:
            self.cursor.execute(query, params)
            self.connection.commit()

        except mysql.connector.Error as dberr:
            print(dberr)
            if close_conn_on_err:
                if self.on_error == DB_ERR_REST: raise http_server_err()
            else: raise mysql.connector.Error()

    def delete(self):
        pass


    def __del__(self):
        self.cursor.close()
        self.connection.close()
        print('closed pool')


# igisdb = MYSQL_Query(IGIS_DB_CONNECTION)