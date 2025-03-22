import sqlite3
from sqlite3 import Error
import os

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.create_table()

    def create_connection(self):
        """ Create a database connection to the SQLite database """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            return conn
        except Error as e:
            print(e)
        return conn

    def create_table(self):
        """ Create the faces table if it does not exist """
        conn = self.create_connection()
        sql_create_faces_table = """
        CREATE TABLE IF NOT EXISTS faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            usn TEXT NOT NULL UNIQUE,
            year TEXT NOT NULL,
            branch TEXT NOT NULL,
            image_path TEXT NOT NULL,
            encoding BLOB NOT NULL,  # Add this line for face encoding
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );"""
        
        try:
            c = conn.cursor()
            c.execute(sql_create_faces_table)
        except Error as e:
            print(e)
        finally:
            if conn:
                conn.close()

    def add_face(self, name, usn, year, branch, image_path, encoding):
        """ Insert a new face into the faces table """
        conn = self.create_connection()
        sql_insert_face = """
        INSERT INTO faces (name, usn, year, branch, image_path, encoding)
        VALUES (?, ?, ?, ?, ?, ?);"""
        
        try:
            c = conn.cursor()
            c.execute(sql_insert_face, (name, usn, year, branch, image_path, sqlite3.Binary(encoding)))
            conn.commit()
        except Error as e:
            print(e)
        finally:
            if conn:
                conn.close()

    def get_faces(self):
        """ Query all faces in the faces table """
        conn = self.create_connection()
        sql_select_faces = "SELECT * FROM faces;"
        
        faces = []
        try:
            c = conn.cursor()
            c.execute(sql_select_faces)
            faces = c.fetchall()
        except Error as e:
            print(e)
        finally:
            if conn:
                conn.close()
        return faces

    def get_face_by_usn(self, usn):
        """ Query a face by USN """
        conn = self.create_connection()
        sql_select_face = "SELECT * FROM faces WHERE usn = ?;"
        
        face = None
        try:
            c = conn.cursor()
            c.execute(sql_select_face, (usn,))
            face = c.fetchone()
        except Error as e:
            print(e)
        finally:
            if conn:
                conn.close()
        return face

# Initialize the database
if __name__ == '__main__':
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), '../database/face_data.db')
    db = Database(DATABASE_PATH)
